# PicSize Downloader Bypass

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

An automated downloader for PicSize galleries that bypasses download restrictions, allowing you to download all photos from a gallery as a ZIP file with original quality — even when the photographer has disabled the download option.

## How the Bypass Works

PicSize galleries have a `download_all` flag that controls whether clients can download photos. However, this restriction is **only enforced client-side** in the React frontend — the server-side API does not validate it. This script calls the ZIP generation API directly, bypassing the UI check entirely.

```
Frontend (React):
  if (!homeState.front.download_all) {
      return navigate(`/${hash}`)  // Redirects away from download page
  }

Server API (no check):
  GET /gallery/{hash}/zip?generate=true  // Always accepts if authenticated
```

## Features

- **Automatic Login** - Automatically logs into galleries via Playwright
- **Auto Signup** - Registers the email if not yet registered on the gallery
- **ZIP Download** - Downloads all gallery photos at once as a ZIP
- **Progress Tracking** - Shows download progress with percentage
- **Resume Download** - Doesn't re-download existing files
- **Headless Browser** - Runs without graphical interface (optional)
- **Cross-platform** - Works on Windows, Linux and macOS

## Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/leonardo-spy/picsize-downloader-bypass.git
cd picsize-downloader-bypass
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install chromium
```

## Configuration

Edit the settings in the `main.py` file:

```python
# Configuration
GALLERY_URL = "https://yourdomain.picsize.com.br/galleryHash"
EMAIL = "your@email.com"
PASSWORD = "your_password"
OUTPUT_DIR = "downloads"
```

### Available Parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `GALLERY_URL` | PicSize gallery URL | `https://photographer.picsize.com.br/aB1cD2eF3g` |
| `EMAIL` | Login email | `user@example.com` |
| `PASSWORD` | Gallery password | `mypassword123` |
| `OUTPUT_DIR` | Download destination folder | `downloads` |

## How to Use

1. Configure your credentials in `main.py`

2. Run the script:
```bash
python main.py
```

3. Wait for the process:
   - Script will open a headless browser
   - Will log in automatically (or signup if needed)
   - Will extract the auth token from cookies
   - Will trigger server-side ZIP generation
   - Will poll until the ZIP is ready
   - Will download the ZIP file

### Example Output:
```
==================================================
  PicSize Downloader Bypass
==================================================
Target: https://photographer.picsize.com.br/aB1cD2eF3g

[1/4] Launching browser...
[1/4] Navigating to https://selecao.picsize.com.br/aB1cD2eF3g/select
[1/4] Login page detected. Filling credentials...
[1/4] Auth token obtained successfully.
[2/4] Triggering ZIP generation for gallery 'aB1cD2eF3g'...
[2/4] ZIP generation started: 266 photos, ~33.97 MB
[3/4] Waiting for server to finish ZIP compression...
[3/4] Status: generating - waiting 5s...
[3/4] ZIP ready! 266 photos, 33.97 MB
[4/4] Downloading ZIP...
[4/4] Progress: 100.0% (34787 KB / 34787 KB)
[4/4] Saved to downloads/aB1cD2eF3g.zip

All done!
```

## Project Structure

```
picsize-downloader-bypass/
├── main.py                 # Main script
├── requirements.txt        # Project dependencies
├── README.md               # This file
└── downloads/              # Folder where ZIP files are saved
```

## Technical Details

### Authentication Flow

1. **Navigation**: Playwright navigates to the gallery home page, then to the login page with `?callback=select_mode`
2. **Login/Signup**: The script fills in credentials (or registers if the email isn't found)
3. **Redirect**: After login, PicSize redirects through the gallery home to `selecao.picsize.com.br/{hash}/select`, setting the HttpOnly `customer-client-auth-token` JWT cookie
4. **Browser-side API calls**: Since the cookie is HttpOnly (not accessible via `document.cookie` or `context.cookies()`), the script uses `page.evaluate()` to call `fetch()` with `credentials: 'include'` directly from the authenticated browser context

### The Bypass (API Calls)

All API calls are made from within the Playwright browser context, which automatically sends the HttpOnly auth cookie:

1. **Trigger**: `GET https://gallery-api.s2.picsize.com.br/gallery/{hash}/zip?generate=true`
   - Requires: `customer-client-auth-token` cookie + `Origin: https://selecao.picsize.com.br`
   - Server starts compressing all original photos into a ZIP

2. **Poll**: `GET https://gallery-api.s2.picsize.com.br/gallery/{hash}/zip`
   - Returns `zip_status: "generating"` while processing
   - Returns `zip_status: "complete"` with `zip_url` when done

3. **Download**: `GET {zip_url}` (direct from Backblaze cloud, no auth needed — downloaded via `requests`)

### Key API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `gallery-api.s2.picsize.com.br/home/data?hash={hash}` | Gallery metadata |
| `gallery-api.s2.picsize.com.br/home/front/data?hash={hash}` | Frontend config (download_all flag) |
| `c.api.picsize.com.br/select/selection/{hash}` | Full gallery data with photo IDs |
| `gallery-api.s2.picsize.com.br/gallery/{hash}/zip?generate=true` | **ZIP generation trigger (the bypass)** |
| `gallery-api.s2.picsize.com.br/gallery/{hash}/zip` | ZIP status polling |

### Protection Mechanisms Bypassed

| Protection | Type | Bypassed? |
|------------|------|-----------|
| `download_all: false` | Client-side only | Yes |
| `single_download: false` | Client-side only | Yes |
| `anti_copy: true` | JavaScript overlay | Yes |
| JWT-signed image URLs | Server-side | Yes (ZIP uses originals) |
| Watermark on previews | Server-side rendering | Yes (ZIP has no watermark) |

## Known Limitations

- Requires the gallery to be accessible (not deleted or expired)
- The email must be able to register/login on the gallery
- May not work if PicSize changes their API structure
- ZIP generation time depends on the number and size of photos

## Customization

### Disable headless mode (see the browser):
```python
browser = await p.chromium.launch(headless=False)
```

### Change output directory:
```python
OUTPUT_DIR = "my_photos"
```

## Important Notes

- **Ethical Use**: This script is for educational purposes and personal backups
- **Respect Rights**: Don't use to download copyrighted content without permission
- **Updates**: PicSize may change its API, requiring script updates

## Disclaimer

This software is provided "as is", without any warranties. Using this script to download content without authorization may violate PicSize's terms of service and copyright laws. The user is solely responsible for the use of this tool.

## Acknowledgments

- Playwright team for excellent browser automation
- [AlboomPro Downloader Bypass](https://github.com/leonardo-spy/alboompro-downloader-bypass) - The original project that inspired this one

---

**See also:** [AlboomPro Downloader Bypass](https://github.com/leonardo-spy/alboompro-downloader-bypass) - Similar tool for AlboomPro galleries
