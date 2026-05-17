# Installation

`kineripper` runs on Python 3.10+ and depends on three native programs:

| Program      | Purpose                                                 |
|--------------|---------------------------------------------------------|
| `ffmpeg`     | Final mux of decrypted video + audio, `+faststart`      |
| `mp4decrypt` | CENC ClearKey decryption (provided by [Bento4](https://www.bento4.com/)) |
| Chromium     | Real browser used by Playwright to discover chunk URLs  |

Chromium is installed automatically by Playwright. `ffmpeg` and `mp4decrypt` you install via your OS package manager.

---

## macOS

```bash
# 1. system tools
brew install python@3.11 ffmpeg bento4

# 2. project
git clone https://github.com/YOUR-USERNAME/kineripper.git
cd kineripper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. browser for Playwright
playwright install chromium
```

Verify:

```bash
ffmpeg -version | head -1
mp4decrypt 2>&1 | head -1     # should print "mp4decrypt - version X.Y.Z"
python -c "from playwright.sync_api import sync_playwright; print('ok')"
```

If you get `xattr` quarantine errors on `mp4decrypt`, clear them:

```bash
xattr -dr com.apple.quarantine "$(which mp4decrypt)"
```

---

## Linux (Debian / Ubuntu)

```bash
# 1. system tools
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg unzip curl

# 2. Bento4 — no apt package, install from the official release
BENTO4_URL="https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-641.x86_64-unknown-linux.zip"
curl -L "$BENTO4_URL" -o /tmp/bento4.zip
sudo unzip -o /tmp/bento4.zip -d /opt
sudo ln -sf /opt/Bento4-SDK-*/bin/mp4decrypt /usr/local/bin/mp4decrypt

# 3. project
git clone https://github.com/YOUR-USERNAME/kineripper.git
cd kineripper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. browser for Playwright + system libs
playwright install chromium
playwright install-deps      # installs libnss3, libatk-1.0-0, etc.
```

### Other Linux distributions

- **Fedora / RHEL**: `sudo dnf install python3 python3-pip ffmpeg`, then Bento4 manually as above.
- **Arch**: `sudo pacman -S python python-pip ffmpeg`. Bento4 is in AUR as `bento4`.
- **Alpine**: known issues with Playwright system libraries. Use a glibc-based distro instead.

### Headless servers

If you intend to run on a headless Linux server (no display):

```bash
# install Xvfb to provide a virtual display
sudo apt install -y xvfb
# wrap your invocation:
xvfb-run -a python kineripper.py --list lessons.txt --out ./downloads
```

Or pass `--headless` to `kineripper.py`. Headless works on most platforms but not all — if the player refuses to autoplay headless, you must use the Xvfb approach.

---

## Windows

The cleanest path is **Chocolatey** for system packages and a regular Python install.

### Chocolatey route

```powershell
# 1. install Chocolatey (skip if you already have it)
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 2. system tools
choco install -y python ffmpeg

# 3. Bento4 — manual download (no Chocolatey package)
#    Get latest release ZIP from https://www.bento4.com/downloads/
#    Extract to e.g. C:\Tools\Bento4
#    Add C:\Tools\Bento4\bin to your PATH (System Properties → Environment Variables)
```

### Project setup

```powershell
git clone https://github.com/YOUR-USERNAME/kineripper.git
cd kineripper
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### Verify

```powershell
ffmpeg -version | Select-Object -First 1
mp4decrypt
python -c "from playwright.sync_api import sync_playwright; print('ok')"
```

### Notes for Windows users

- Long file names: paths under `%USERPROFILE%\Downloads\…` may exceed Windows' 260-char limit if module/lesson titles are long. Either use a shorter `--out` path (e.g. `C:\K\`) or enable long paths in the Group Policy editor (`Local Computer Policy → Computer Configuration → Administrative Templates → System → Filesystem → Enable Win32 long paths`).
- Default session file path: `%USERPROFILE%\.kineripper\session.json`.
- `python` vs `py`: if `python` is not on PATH after the Chocolatey install, use the `py` launcher: `py -3 kineripper.py …`.

---

## Verifying the install

After installation on any OS, run:

```bash
python kineripper.py --help
```

You should see the CLI reference. If you get `ModuleNotFoundError: No module named 'playwright'`, your virtualenv is not activated.

To verify the decrypt toolchain end-to-end without a real session, you can't — it requires a logged-in browser. The smallest real test is:

1. `python save_session.py https://learn.example.com`
2. `python kineripper.py --url <single-lesson-url> --out ./test --verbose`

A successful run prints the chunk list, byte-range continuity check, decrypt success, and final mp4 duration.

---

## Updating

```bash
cd kineripper
git pull
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium       # update Chromium if Playwright was upgraded
```
