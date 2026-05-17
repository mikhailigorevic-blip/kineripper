#!/usr/bin/env python3
"""
kineripper — download multi-part Kinescope videos from course platforms.

See README.md for the full explanation. Short version:
    1. Open the lesson page in a real Chromium with a saved cookie jar.
    2. Scrub through the entire timeline, programmatically setting
       video.currentTime, to force the Kinescope player to request every
       byte-range chunk of the encrypted fragmented MP4 from the CDN.
    3. Capture all chunk URLs plus the single ClearKey JSON response.
    4. Download each chunk, concatenate raw bytes in start-byte order,
       run mp4decrypt with the captured key, and remux with the (single)
       audio track plus +faststart.

Usage:
    python kineripper.py --url URL --out DIR
    python kineripper.py --list FILE --out DIR
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from playwright.async_api import Frame, Page, async_playwright


# --------------------------------------------------------------------------- #
# Configuration defaults
# --------------------------------------------------------------------------- #

DEFAULT_SESSION = Path.home() / ".kineripper" / "session.json"
DEFAULT_TMP = Path.home() / ".kineripper" / "tmp"
DEFAULT_OUT = Path("downloads")

QUALITY_PRIORITY = ("1080p", "720p", "480p", "360p")

CLEARKEY_HOST_MARKER = "license.kinescope.io"
CDN_HOST_MARKER = "kinescopecdn.net"
HEADERS = {
    "Referer": "https://kinescope.io/",
    "Origin": "https://kinescope.io",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #

VERBOSE = False


def log(msg: str, *, verbose_only: bool = False) -> None:
    if verbose_only and not VERBOSE:
        return
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_SAFE_NAME_RE = re.compile(r'[\\/:*?"<>|]+')
_BYTE_RANGE_RE = re.compile(r"/(\d+)/(\d+)/[^/]+\.mp4$")


def safe_name(s: str, max_len: int = 120) -> str:
    """Return a string safe for filenames on every supported OS."""
    return _SAFE_NAME_RE.sub("_", s).strip(" .")[:max_len] or "video"


def parse_byte_range(url_path: str) -> tuple[int, int] | None:
    """Pull the (start_byte, end_byte) tuple out of a Kinescope CDN URL path."""
    m = _BYTE_RANGE_RE.search(url_path)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def run_cmd(
    cmd: list[str], *, timeout: int = 900, check: bool = False
) -> tuple[int, str]:
    """Run a subprocess, return (returncode, combined_stdout_stderr)."""
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    out = (r.stdout or "") + (r.stderr or "")
    if check and r.returncode != 0:
        raise RuntimeError(f"command failed ({r.returncode}): {' '.join(cmd[:3])}\n{out[:500]}")
    return r.returncode, out


def which_or_die(name: str) -> str:
    p = shutil.which(name)
    if not p:
        sys.exit(
            f"error: '{name}' is required and was not found on PATH. "
            f"See INSTALL.md for instructions."
        )
    return p


def ffprobe_duration(path: Path) -> float:
    rc, out = run_cmd(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1",
            str(path),
        ]
    )
    try:
        return float(out.strip())
    except ValueError:
        return 0.0


def filename_from_url(url: str) -> str:
    """Derive a default filename stem from a URL's last meaningful segment."""
    p = urlparse(url)
    parts = [seg for seg in p.path.split("/") if seg]
    return safe_name(parts[-1] if parts else "video")


# --------------------------------------------------------------------------- #
# Capture: open the lesson, scrub, collect URLs and ClearKey
# --------------------------------------------------------------------------- #


@dataclass
class CaptureResult:
    keys: list[tuple[str, str]]              # list of (kid_hex, key_hex)
    cdn_urls: dict[str, str]                 # path-without-query -> full URL
    duration: float                          # seconds
    title: str | None                        # page <title>


async def _find_video_frame(page: Page, timeout_s: int = 20) -> Frame | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for f in page.frames:
            if "kinescope.io" in f.url:
                try:
                    if await f.evaluate("!!document.querySelector('video')"):
                        return f
                except Exception:
                    pass
        await page.wait_for_timeout(500)
    return None


async def capture_lesson(
    page: Page,
    lesson_url: str,
    *,
    seek_step: int,
    autoplay_wait_s: int = 45,
    seek_wait_ms: int = 2000,
) -> CaptureResult | None:
    keys: list[tuple[str, str]] = []
    cdn_seen: dict[str, str] = {}

    async def on_resp(resp) -> None:
        url = resp.url
        if CLEARKEY_HOST_MARKER in url and "clearkey" in url:
            try:
                data = json.loads(await resp.body())
                for k in data.get("keys", []):
                    try:
                        kid_b = base64.urlsafe_b64decode(k["kid"] + "==")
                        key_b = base64.urlsafe_b64decode(k["k"] + "==")
                    except Exception:
                        continue
                    if len(kid_b) != 16 or len(key_b) != 16:
                        continue
                    kk = (kid_b.hex(), key_b.hex())
                    if kk not in keys:
                        keys.append(kk)
            except Exception:
                pass
        elif CDN_HOST_MARKER in url and ".mp4" in url and "poster" not in url:
            path = url.split("?")[0]
            if path not in cdn_seen:
                cdn_seen[path] = url

    page.on("response", on_resp)
    try:
        await page.goto(lesson_url, wait_until="domcontentloaded")

        # locate the Kinescope iframe
        try:
            await page.wait_for_selector(
                'iframe[src*="kinescope"]', timeout=20000
            )
        except Exception:
            log("  iframe not found — lesson may not contain a video")
            return None

        await page.wait_for_timeout(2500)
        title = (await page.title()) or None

        # encourage playback to start
        try:
            ifr = page.locator('iframe[src*="kinescope"]').first
            box = await ifr.bounding_box()
            if box:
                cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                await page.mouse.click(cx, cy)
                await page.wait_for_timeout(400)
                await page.mouse.click(cx, cy)
        except Exception:
            pass

        kf = await _find_video_frame(page)
        if not kf:
            log("  <video> element not found inside Kinescope iframe")
            return None

        duration = 0.0
        for _ in range(autoplay_wait_s):
            try:
                ct = await kf.evaluate(
                    "document.querySelector('video')?.currentTime || 0"
                )
                dur = await kf.evaluate(
                    "document.querySelector('video')?.duration || 0"
                )
            except Exception:
                ct, dur = 0, 0
            if ct and ct > 0.5 and dur and dur > 0:
                duration = float(dur)
                break
            # nudge: unmute + play
            await kf.evaluate(
                "() => { const v = document.querySelector('video'); "
                "if (v) { v.muted = true; v.play().catch(()=>{}); } }"
            )
            await page.wait_for_timeout(1000)

        if not duration:
            log("  playback did not start within %d s — session expired?" % autoplay_wait_s)
            return None

        log(f"  duration: {duration:.0f}s ({duration / 60:.1f} min)", verbose_only=True)

        # walk the entire timeline
        positions = list(range(0, int(duration), seek_step))
        if not positions or positions[-1] < duration - 30:
            positions.append(max(0, int(duration) - 30))

        for pos in positions:
            await kf.evaluate(
                "(t) => { const v = document.querySelector('video'); "
                "if (v) { v.currentTime = t; v.play().catch(()=>{}); } }",
                pos,
            )
            await page.wait_for_timeout(seek_wait_ms)

        await page.wait_for_timeout(2000)

        return CaptureResult(
            keys=keys, cdn_urls=cdn_seen, duration=duration, title=title
        )
    finally:
        try:
            page.remove_listener("response", on_resp)
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Assemble: pick parts, download, concat, decrypt, mux
# --------------------------------------------------------------------------- #


def select_video_paths(
    cdn_urls: dict[str, str], preferred_quality: str
) -> list[str]:
    """Return CDN paths for the chosen quality, sorted by start byte.

    `preferred_quality` is 'auto' or a literal '1080p'/'720p'/...
    Auto picks the highest quality that yields at least one part.
    """
    candidates: dict[str, list[str]] = {}
    for path in cdn_urls:
        if "audio" in path.lower():
            continue
        for q in QUALITY_PRIORITY:
            if q in path:
                candidates.setdefault(q, []).append(path)
                break

    if not candidates:
        return []

    if preferred_quality == "auto":
        for q in QUALITY_PRIORITY:
            if q in candidates:
                return sorted(candidates[q], key=_sort_key)
        return []
    return sorted(candidates.get(preferred_quality, []), key=_sort_key)


def _sort_key(path: str) -> tuple[int, int]:
    rng = parse_byte_range(path)
    return rng if rng else (10**18, 10**18)


def select_audio_path(cdn_urls: dict[str, str]) -> str | None:
    for path in cdn_urls:
        if "audio" in path.lower():
            return path
    return None


def curl_download(
    url: str, dst: Path, *, expected_size: int | None = None
) -> bool:
    """Download with retries. Verify Content-Length match if provided."""
    if dst.exists():
        dst.unlink()
    rc, _ = run_cmd(
        [
            "curl", "-sS", "-L",
            "--retry", "5",
            "--retry-all-errors",
            "--retry-delay", "2",
            "-o", str(dst),
            *[a for h, v in HEADERS.items() for a in ("-H", f"{h}: {v}")],
            url,
        ],
        timeout=900,
    )
    if rc != 0 or not dst.exists() or dst.stat().st_size == 0:
        return False
    if expected_size is not None and dst.stat().st_size != expected_size:
        return False
    return True


def curl_content_length(url: str) -> int | None:
    rc, out = run_cmd(
        [
            "curl", "-sI", "-L",
            *[a for h, v in HEADERS.items() for a in ("-H", f"{h}: {v}")],
            url,
        ]
    )
    if rc != 0:
        return None
    for line in out.splitlines():
        if line.lower().startswith("content-length:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def assemble(
    capture: CaptureResult,
    out_file: Path,
    *,
    tmp_dir: Path,
    preferred_quality: str,
    keep_temp: bool,
) -> tuple[bool, str]:
    if not capture.keys:
        return False, "no ClearKey captured (session expired?)"
    if not capture.cdn_urls:
        return False, "no CDN URLs captured"

    video_paths = select_video_paths(capture.cdn_urls, preferred_quality)
    if not video_paths:
        return False, "no video chunks found for the requested quality"

    audio_path = select_audio_path(capture.cdn_urls)
    if not audio_path:
        return False, "no audio URL captured"

    # verify byte-range continuity
    expected_start = 0
    sizes: list[int] = []
    for path in video_paths:
        rng = parse_byte_range(path)
        if not rng:
            return False, f"unparseable video URL: {path}"
        start, end = rng
        if start != expected_start:
            return False, (
                f"gap in video byte ranges (expected next chunk to start at "
                f"{expected_start}, got {start})"
            )
        sizes.append(end - start)
        expected_start = end

    total = sum(sizes)
    log(f"  parts: {len(video_paths)} video ({total / 1024 / 1024:.1f} MB), 1 audio")

    tmp_dir.mkdir(parents=True, exist_ok=True)

    # download all video parts straight into one concatenated encrypted file
    enc_video = tmp_dir / "video_enc.mp4"
    if enc_video.exists():
        enc_video.unlink()
    with enc_video.open("wb") as f_out:
        for i, path in enumerate(video_paths):
            url = capture.cdn_urls[path]
            chunk_dst = tmp_dir / f"chunk_{i + 1:02d}.bin"
            if not curl_download(url, chunk_dst, expected_size=sizes[i]):
                actual = chunk_dst.stat().st_size if chunk_dst.exists() else 0
                return False, (
                    f"chunk {i + 1} size mismatch (got {actual}, "
                    f"expected {sizes[i]})"
                )
            with chunk_dst.open("rb") as f_in:
                shutil.copyfileobj(f_in, f_out, length=8 * 1024 * 1024)
            chunk_dst.unlink()

    log(f"  concatenated encrypted video: {enc_video.stat().st_size / 1024 / 1024:.1f} MB",
        verbose_only=True)

    # decrypt video
    which_or_die("mp4decrypt")
    kid, key = capture.keys[0]
    dec_video = tmp_dir / "video_dec.mp4"
    if dec_video.exists():
        dec_video.unlink()
    rc, out = run_cmd(
        ["mp4decrypt", "--key", f"{kid}:{key}", str(enc_video), str(dec_video)],
        timeout=600,
    )
    if rc != 0 or not dec_video.exists():
        return False, f"mp4decrypt failed on video (rc={rc}): {out[:200]}"

    dur_v = ffprobe_duration(dec_video)
    if dur_v < capture.duration * 0.9:
        return False, (
            f"decrypted video too short ({dur_v:.0f}s vs expected "
            f"{capture.duration:.0f}s) — scrubber probably missed a chunk"
        )
    log(f"  video decrypted: {dec_video.stat().st_size / 1024 / 1024:.1f} MB, "
        f"{dur_v:.0f}s", verbose_only=True)

    # download + decrypt audio
    enc_audio = tmp_dir / "audio_enc.mp4"
    if not curl_download(capture.cdn_urls[audio_path], enc_audio):
        return False, "audio download failed"

    dec_audio = tmp_dir / "audio_dec.mp4"
    if dec_audio.exists():
        dec_audio.unlink()
    rc, out = run_cmd(
        ["mp4decrypt", "--key", f"{kid}:{key}", str(enc_audio), str(dec_audio)],
        timeout=600,
    )
    if rc != 0 or not dec_audio.exists():
        return False, f"mp4decrypt failed on audio (rc={rc}): {out[:200]}"

    # mux
    which_or_die("ffmpeg")
    if out_file.exists():
        out_file.unlink()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    rc, out = run_cmd(
        [
            "ffmpeg", "-v", "error",
            "-i", str(dec_video),
            "-i", str(dec_audio),
            "-c", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-movflags", "+faststart",
            "-y", str(out_file),
        ],
        timeout=600,
    )
    if rc != 0 or not out_file.exists():
        return False, f"ffmpeg mux failed (rc={rc}): {out[:200]}"

    if not keep_temp:
        for f in (enc_video, dec_video, enc_audio, dec_audio):
            try:
                f.unlink()
            except FileNotFoundError:
                pass

    final_dur = ffprobe_duration(out_file)
    log(f"  done: {out_file.name} ({out_file.stat().st_size / 1024 / 1024:.0f} MB, "
        f"{final_dur:.0f}s)")
    return True, "ok"


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #


def load_urls(args: argparse.Namespace) -> list[str]:
    if args.url:
        return [args.url]
    urls: list[str] = []
    with open(args.list, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
    return urls


def output_path(out_dir: Path, url: str, title: str | None, use_title: bool) -> Path:
    stem = (
        safe_name(title) if (use_title and title) else filename_from_url(url)
    )
    return out_dir / f"{stem}.mp4"


async def main_async(args: argparse.Namespace) -> int:
    global VERBOSE
    VERBOSE = bool(args.verbose)

    which_or_die("ffmpeg")
    which_or_die("mp4decrypt")
    which_or_die("curl")

    session_path: Path = args.session
    if not session_path.exists():
        sys.exit(
            f"error: session file {session_path} does not exist. "
            f"Run save_session.py first."
        )

    urls = load_urls(args)
    if not urls:
        sys.exit("error: no URLs to process")

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir: Path = args.tmp
    tmp_dir.mkdir(parents=True, exist_ok=True)

    log(f"to process: {len(urls)} lesson(s)")

    ok = fail = skipped = 0
    failures: list[tuple[str, str]] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=bool(args.headless),
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--mute-audio",
            ],
        )
        ctx = await browser.new_context(
            storage_state=str(session_path),
            viewport={"width": 1280, "height": 800},
            user_agent=HEADERS["User-Agent"],
        )
        page = await ctx.new_page()

        for i, url in enumerate(urls, 1):
            log(f"[{i}/{len(urls)}] {url}")
            tentative_out = output_path(out_dir, url, None, False)
            if tentative_out.exists() and tentative_out.stat().st_size > 5 * 1024 * 1024:
                if ffprobe_duration(tentative_out) > 60:
                    log("  already present, skipping")
                    skipped += 1
                    continue

            try:
                capture = await capture_lesson(
                    page, url, seek_step=args.seek_step
                )
            except Exception as exc:
                fail += 1
                failures.append((url, f"capture exception: {exc}"))
                log(f"  failed: {exc}")
                continue

            if capture is None:
                fail += 1
                failures.append((url, "capture failed"))
                continue

            final_out = output_path(out_dir, url, capture.title, args.name_from_title)
            success, msg = assemble(
                capture,
                final_out,
                tmp_dir=tmp_dir,
                preferred_quality=args.quality,
                keep_temp=bool(args.keep_temp),
            )
            if success:
                ok += 1
            else:
                fail += 1
                failures.append((url, msg))
                log(f"  failed: {msg}")

        await browser.close()

    print()
    log("=== summary ===")
    log(f"  ok:      {ok}")
    log(f"  skipped: {skipped}")
    log(f"  failed:  {fail}")
    if failures:
        print()
        log("failures:")
        for url, msg in failures:
            log(f"  {url}: {msg}")
    log(f"output: {out_dir}")
    return 0 if fail == 0 else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="kineripper",
        description="Download multi-part Kinescope videos from a course platform.",
        epilog=(
            "You must run save_session.py first to capture browser cookies. "
            "See README.md for the full explanation of what this tool does."
        ),
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="single lesson URL to download")
    src.add_argument(
        "--list",
        type=Path,
        help="text file with one lesson URL per line",
    )
    p.add_argument(
        "--out", type=Path, default=DEFAULT_OUT,
        help=f"output directory (default: {DEFAULT_OUT})",
    )
    p.add_argument(
        "--session", type=Path, default=DEFAULT_SESSION,
        help=f"session JSON path (default: {DEFAULT_SESSION})",
    )
    p.add_argument(
        "--quality",
        choices=("auto", "1080p", "720p", "480p", "360p"),
        default="auto",
        help="preferred quality (default: auto = best available)",
    )
    p.add_argument(
        "--seek-step", type=int, default=60,
        help="scrubbing step in seconds (default: 60)",
    )
    p.add_argument(
        "--headless", action="store_true",
        help="run Chromium headless (may break autoplay on some sites)",
    )
    p.add_argument(
        "--name-from-title", action="store_true",
        help="use the lesson page <title> for the output filename",
    )
    p.add_argument(
        "--keep-temp", action="store_true",
        help="keep intermediate encrypted/decrypted files for inspection",
    )
    p.add_argument(
        "--tmp", type=Path, default=DEFAULT_TMP,
        help=f"working directory for temporary files (default: {DEFAULT_TMP})",
    )
    p.add_argument(
        "-v", "--verbose", action="store_true",
        help="more log output",
    )
    return p.parse_args()


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    sys.exit(main())
