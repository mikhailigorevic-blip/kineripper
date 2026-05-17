# kineripper

<table>
<tr>
<td width="50%" valign="top">

**English**

Download multi-part Kinescope videos from course platforms (GetCourse and similar) where standard HLS/DASH rippers produce files in which the **audio is longer than the video stream**.

If you ran a stream recorder or `yt-dlp` against a Kinescope embed and got a file where the picture freezes after ~16 minutes but the sound keeps going — this tool fixes that.

</td>
<td width="50%" valign="top">

**Русский**

Загрузчик многочастных видео Kinescope для платформ онлайн-курсов (GetCourse и аналоги), когда стандартные стрим-рипперы выдают файл, в котором **аудио длиннее видеоряда** — картинка замирает через несколько минут, а звук продолжает играть.

Если ты запускал `yt-dlp` или другой стрим-риппер против Kinescope-эмбеда и получил файл, где картинка обрывается на ~16-й минуте, а звук идёт до конца — этот инструмент чинит ровно эту проблему.

</td>
</tr>
</table>

---

## Why it exists / Зачем

<table>
<tr>
<td width="50%" valign="top">

Kinescope serves long videos as **byte-range chunks** of a single encrypted fragmented MP4. The URLs are named after the byte range itself:

</td>
<td width="50%" valign="top">

Kinescope режет один зашифрованный fragmented MP4 на байтовые куски. Имя URL'а буквально содержит диапазон байт:

</td>
</tr>
</table>

```
edge-msk-1.kinescopecdn.net/.../assets/<uuid>/0/78848150/720p.mp4
edge-msk-1.kinescopecdn.net/.../assets/<uuid>/78848150/157659039/720p.mp4
edge-msk-1.kinescopecdn.net/.../assets/<uuid>/157659039/235941954/720p.mp4
...
```

<table>
<tr>
<td width="50%" valign="top">

A 60-minute lesson is usually split into 4–5 chunks of ~75 MB each. The player requests the next chunk **only when playback reaches that part of the timeline**. Common tools watch network traffic for 10–30 seconds and capture only the **first chunk** — exactly the long-audio / short-video result you may have seen.

`kineripper` forces the player to reveal **all** chunks by programmatically scrubbing through the entire timeline at 60-second intervals (`video.currentTime = X`). It collects every URL, sorts them by start byte, verifies they form one contiguous file, downloads each chunk, concatenates the bytes, decrypts with the ClearKey the player also requested, and remuxes with the audio track.

</td>
<td width="50%" valign="top">

60-минутный урок — это обычно 4–5 кусков по ~75 МБ. Плеер запрашивает следующий кусок **только когда воспроизведение туда доходит**. Стандартные риппери ловят первый кусок за 10–30 секунд и решают, что это весь файл — отсюда тот самый файл с короткой картинкой и длинным звуком.

`kineripper` заставляет плеер показать **все** куски: программно проматывает таймлайн с шагом 60 секунд (`video.currentTime = X`), ловит каждый URL, сортирует по start-byte, проверяет непрерывность, скачивает, склеивает сырые байты, расшифровывает одним ключом ClearKey (тоже перехваченным) и мукс с аудиодорожкой.

</td>
</tr>
</table>

## When this is the right tool / Когда это подходит

<table>
<tr>
<td width="50%" valign="top">

✅ Use it when **all** of the following are true:

- You have **legitimate paid access** to a course you want to back up locally
- The course pages are protected by **login** (cookies)
- The videos are embedded as Kinescope iframes (`kinescope.io/embed/...`)
- Standard rippers produce a file where **video duration < audio duration**
- The course's Terms of Service do not forbid personal backups

❌ Do **not** use it for:

- Content you have not paid for / do not have permission to copy
- Mass-distribution or re-uploading of someone else's course
- Bypassing region locks or DRM that is not ClearKey

You are solely responsible for compliance with the course's Terms of Service, copyright law, and any other applicable rules in your jurisdiction. The authors of `kineripper` provide this tool for the technical task of reassembling multi-part encrypted MP4s and assume no responsibility for how you choose to use it.

</td>
<td width="50%" valign="top">

✅ Только если **все** пункты ниже верны:

- У тебя **легально оплачен** курс, который ты хочешь сохранить локально
- Страницы курса требуют **логина** (cookies)
- Видео встроены через `iframe` на `kinescope.io/embed/...`
- Обычные риппери дают файл, где видео короче аудио
- Условия использования курса не запрещают резервные копии для личного использования

❌ Нельзя для:

- Контента, на который у тебя нет легального доступа
- Массового распространения чужих материалов
- Обхода защит, не относящихся к ClearKey

Ответственность за соблюдение лицензии курса и применимого законодательства лежит **только на тебе**. Авторы `kineripper` предоставляют инструмент для технической задачи пересборки многочастных зашифрованных MP4 и не отвечают за то, как ты им воспользуешься.

</td>
</tr>
</table>

## What you need to provide / Что нужно ввести

<table>
<tr>
<td width="50%" valign="top">

When you run the tool, you supply:

1. **The login URL of your course platform** (e.g. `https://learn.example.com`). One-time, used for the session-save step.
2. **Your username and password** — typed **directly into the browser** that the tool opens. They never go through `kineripper`, are never written to disk, and there is no `--password` flag. The only thing saved locally is the resulting browser cookie file at `~/.kineripper/session.json`.
3. **The list of lesson URLs** you want to download — either one URL at a time on the command line, or as a plain text file with one URL per line.
4. **An output directory** for the finished `.mp4` files.

That's the entire input surface. No API keys, no DRM tokens, no special configuration.

</td>
<td width="50%" valign="top">

При запуске ты задаёшь:

1. **URL входа на платформу курса** (например `https://learn.example.com`). Используется один раз — на шаге сохранения сессии.
2. **Логин и пароль** — вводятся **в браузере**, который открывает скрипт. Они не проходят через `kineripper`, не пишутся на диск, флага `--password` не существует. Локально остаётся только файл cookies в `~/.kineripper/session.json`.
3. **Список URL'ов уроков** — либо по одному в командной строке, либо текстовым файлом с одной строкой на URL.
4. **Папка для сохранения** готовых `.mp4`.

Это весь ввод. Никаких API-ключей, токенов, конфигов.

</td>
</tr>
</table>

## Installation / Установка

See [INSTALL.md](INSTALL.md) for per-OS instructions (macOS, Linux, Windows). / Подробные инструкции по ОС — в [INSTALL.md](INSTALL.md).

Quick version / Кратко:

```bash
# 1. system dependencies — ffmpeg and Bento4 (provides mp4decrypt)
#    системные зависимости: ffmpeg + Bento4 (даёт mp4decrypt) — см. INSTALL.md

# 2. Python dependencies / Python-зависимости
python3 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Python 3.10 or newer is required. / Нужен Python ≥ 3.10.

## Usage / Использование

### Step 1 — save your session (one time) / Шаг 1 — сохранить сессию (один раз)

```bash
python save_session.py https://learn.example.com
```

<table>
<tr>
<td width="50%" valign="top">

A visible Chromium window opens at the URL you supplied. Inside the browser:

1. Log in normally with your username and password.
2. Open any one lesson with a video and press Play. Let it play for at least 10 seconds so the Kinescope cookies get set.
3. Close the browser window.

The cookies are saved to `~/.kineripper/session.json`. The script never reads your credentials — only the resulting cookies.

If your session ever expires (typically after a few weeks of inactivity), repeat this step.

</td>
<td width="50%" valign="top">

Откроется видимое окно Chromium на указанном URL. В браузере:

1. Залогинься обычным способом — логин и пароль.
2. Открой любой урок с видео и нажми Play. Дай ему поиграть минимум 10 секунд — чтобы Kinescope выставил свои cookies.
3. Закрой окно браузера.

Cookies сохранятся в `~/.kineripper/session.json`. Скрипт не читает твои учётные данные — только итоговые cookies.

Если сессия со временем протухнет (обычно через несколько недель неактивности), повтори этот шаг.

</td>
</tr>
</table>

### Step 2 — download / Шаг 2 — скачивание

**Single lesson / Один урок:**

```bash
python kineripper.py --url "https://learn.example.com/lesson/123" --out ./downloads
```

**Batch from a file / Пачкой из файла:**

```bash
cat > lessons.txt <<'EOF'
https://learn.example.com/lesson/123
https://learn.example.com/lesson/124
https://learn.example.com/lesson/125
EOF

python kineripper.py --list lessons.txt --out ./downloads
```

<table>
<tr>
<td width="50%" valign="top">

Each finished file is named after the URL's last path segment by default. Use `--name-from-title` to use the lesson page `<title>` instead.

The tool resumes automatically — if a destination file already exists and is longer than 60 seconds, that lesson is skipped.

</td>
<td width="50%" valign="top">

По умолчанию имя файла — последний сегмент URL'а. Флаг `--name-from-title` использует `<title>` страницы урока.

Скрипт сам пропускает уже скачанные уроки: если в папке вывода уже лежит `.mp4` длительностью больше 60 секунд — урок пропускается.

</td>
</tr>
</table>

### CLI reference / Справка по CLI

```
python kineripper.py [options]

  --url URL                 Download one lesson at URL
  --list FILE               Download every URL in FILE (one per line)
  --out DIR                 Output directory (default: ./downloads)
  --session FILE            Session JSON path (default: ~/.kineripper/session.json)
  --quality Q               Preferred quality: 1080p, 720p, 480p, 360p, or auto (default: auto)
  --seek-step SECONDS       Scrubbing step in seconds (default: 60)
  --headless                Run Chromium headless. Some pages will not autoplay headless.
  --name-from-title         Use the lesson page <title> for the output filename
  --keep-temp               Do not delete intermediate encrypted/decrypted chunks
  --tmp DIR                 Temporary working directory (default: ~/.kineripper/tmp)
  -v, --verbose             More log output
  -h, --help                Show this message and exit
```

## How it works / Как это работает

<table>
<tr>
<td width="50%" valign="top">

The Kinescope embed protects videos with **W3C Common Encryption (CENC) with ClearKey** key delivery — *not* DRM in the Widevine/PlayReady sense. The key is fetched from:

```
license.kinescope.io/v1/vod/<id>/acquire/clearkey
```

That endpoint returns a real 16-byte AES key only to a **logged-in browser session**. Anonymous requests get a dummy/random key.

The encrypted video itself is one fragmented MP4 split into byte ranges on the CDN. The URL path encodes the start and end bytes of each chunk:

```
.../assets/<uuid>/<start>/<end>/720p.mp4
```

Each chunk is served with the correct `Content-Length`, but only the **first** chunk has the `moov` atom — the others are pure `moof` + `mdat` continuations and ffprobe alone refuses to parse them. Concatenating the raw bytes in start-byte order produces a valid encrypted fMP4 with proper `moov`, which `mp4decrypt` decrypts in one pass.

The audio track is delivered as a single MP4 file (e.g. `audio_0.mp4`) — no chunking — and decrypts with the same key.

The discovery of the chunk URLs is the actual problem. The player loads only what it needs as the user watches, so a passive network sniff catches only the first chunk. `kineripper` opens the lesson in a real Chromium with the saved cookie jar, finds the `<video>` element inside the Kinescope iframe, reads `duration`, and walks the timeline by setting `video.currentTime = T` for `T = 0, 60, 120, … duration`. Each seek triggers a fresh CDN request for the chunk containing that timestamp. After the walk, the response listener has every chunk URL and the single ClearKey response. From there: download, concatenate, decrypt, mux.

</td>
<td width="50%" valign="top">

Шифрование — W3C Common Encryption (CENC) с доставкой ключа через ClearKey, **не Widevine/PlayReady**. Endpoint:

```
license.kinescope.io/v1/vod/<id>/acquire/clearkey
```

Возвращает 16-байтный AES-ключ только залогиненной сессии. Анонимный запрос получает dummy.

Видео — один fragmented MP4, разрезанный на байтовые куски. Имя URL = диапазон:

```
.../assets/<uuid>/<start>/<end>/720p.mp4
```

Каждый кусок отдаётся с правильным `Content-Length`, но только **первый** содержит `moov`-атом (init-сегмент); остальные — чистые `moof`+`mdat`-продолжения, ffprobe их в одиночку не парсит. Сырая конкатенация в правильном порядке по start-byte даёт валидный encrypted fMP4 с `moov`, который `mp4decrypt` декриптит одним проходом.

Аудиодорожка — один файл (`audio_0.mp4`), не режется, расшифровывается тем же ключом.

Главная задача — обнаружить URL'ы кусков. Плеер подгружает только то, что нужно зрителю, поэтому пассивный сниф ловит только первый. `kineripper` открывает урок в настоящем Chromium с сохранёнными куками, находит `<video>` внутри iframe Kinescope, читает `duration` и шагает по таймлайну: `video.currentTime = T` для `T = 0, 60, 120, … duration`. Каждая перемотка триггерит свежий CDN-запрос на кусок, содержащий этот тайм-код. После прохода у listener'а есть все URL'ы кусков и единственный ответ ClearKey. Дальше: скачать, склеить, расшифровать, мукс.

</td>
</tr>
</table>

## Limitations / Ограничения

<table>
<tr>
<td width="50%" valign="top">

- The player only stores chunk URLs in memory while open, so each lesson requires opening a browser tab and scrubbing once. Expect **2–4 minutes per lesson** end-to-end.
- Kinescope **burns the viewer's email into the video pixels as a watermark**. This is not metadata — it is in the raster — and `kineripper` does not and cannot remove it.
- Headless mode is supported via `--headless`, but some hosting platforms refuse to start playback under headless Chromium. If you see "playback did not start" errors, drop the flag and run headed.
- Quality availability depends on the upload. If the video was uploaded as 720p only, you will not get 1080p.
- If the course platform's lesson page is not a Kinescope iframe (e.g. native HTML5 video, Vimeo, JW Player), `kineripper` is the wrong tool.

</td>
<td width="50%" valign="top">

- На каждый урок уходит **2–4 минуты**: открытие браузера, скраббинг таймлайна, скачка частей, decrypt, mux.
- Kinescope **впечатывает email зрителя прямо в пиксели видео** как водяной знак. Это не метаданные, это растр. `kineripper` его не убирает и не может убрать.
- Headless-режим (`--headless`) работает не на всех платформах — иногда плеер не стартует без видимого окна. Если получаешь «playback did not start» — запускай без `--headless`.
- Качество ограничено тем, что загружено автором курса. Если есть только 720p — больше не достанешь.
- Если страница урока — не Kinescope-iframe (нативный HTML5-видео, Vimeo, JW Player и т.п.), `kineripper` тут не поможет.

</td>
</tr>
</table>

## Troubleshooting / Решение проблем

<table>
<tr>
<td width="50%" valign="top">

**"No iframe found"** — the lesson is text-only or uses a different player. Skip it.

**"Playback did not start within 45 seconds"** — your session may have expired. Re-run `save_session.py`. If that doesn't help, drop `--headless` and click Play manually inside the browser window.

**"Part N size mismatch"** — the CDN dropped the connection mid-download. The script retries up to 5 times automatically; if it still fails, your connection is unstable or the CDN is rate-limiting. Wait and retry.

**"Decryption produced shorter video than expected"** — the scrubber missed one or more chunks. Try a smaller `--seek-step 30` and re-run.

**"trun track id unknown, no tfhd was found" (ffprobe on intermediate file)** — this is **expected** and benign. The intermediate concatenated encrypted file is not parseable by ffprobe; the final decrypted file is.

</td>
<td width="50%" valign="top">

**«No iframe found»** — у урока нет видео (текстовый) или плеер не Kinescope. Пропусти.

**«Playback did not start within 45 seconds»** — сессия могла протухнуть. Перезапусти `save_session.py`. Если не помогло — убери `--headless` и нажми Play руками в окне браузера.

**«Part N size mismatch»** — CDN оборвал соединение. Скрипт автоматически делает до 5 ретраев; если падает дальше — соединение нестабильно или CDN рейт-лимитит. Подожди и перезапусти.

**«Decryption produced shorter video than expected»** — скраббер пропустил один или несколько кусков. Попробуй `--seek-step 30` (меньший шаг) и перезапусти.

**«trun track id unknown, no tfhd was found» (ffprobe на промежуточном файле)** — **ожидаемо** и безвредно. Промежуточный склеенный зашифрованный файл ffprobe не парсит; финальный расшифрованный — парсит.

</td>
</tr>
</table>

## Contributing / Вклад

<table>
<tr>
<td width="50%" valign="top">

Issues and PRs welcome. If you find another course platform where this technique works (or a different chunking pattern that needs new logic), please open an issue with a small example.

</td>
<td width="50%" valign="top">

Issues и PR'ы приветствуются. Если ты нашёл другую платформу, где эта техника тоже работает (или новый паттерн нарезки, требующий другой логики), — открой issue с небольшим примером.

</td>
</tr>
</table>

## License / Лицензия

MIT — see [LICENSE](LICENSE) / см. [LICENSE](LICENSE).
