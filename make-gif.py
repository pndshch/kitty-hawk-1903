#!/usr/bin/env python3
"""Capture Kitty Hawk 1903 gameplay -> GIF via playwright + Pillow."""
import asyncio
import io
from pathlib import Path
from PIL import Image
from playwright.async_api import async_playwright

URL = "https://pndshch.github.io/kitty-hawk-1903/"
OUT = Path("/tmp/pndshch-hub/assets/kitty-hawk-1903.gif")
W, H = 375, 720
SCALE = 0.55
COLORS = 32
FRAME_STRIDE = 2

frames: list[Image.Image] = []
durations: list[int] = []


async def capture(page, ms=140):
    png = await page.screenshot(type="png")
    img = Image.open(io.BytesIO(png)).convert("RGB")
    frames.append(img)
    durations.append(ms)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": W, "height": H}, device_scale_factor=2
        )
        page = await ctx.new_page()
        await page.goto(URL, wait_until="networkidle")
        await page.wait_for_timeout(400)

        # Title screen — show start menu briefly
        for _ in range(6):
            await capture(page, 130)
            await page.wait_for_timeout(60)

        # Click START
        await page.click("#startBtn")
        await page.wait_for_timeout(300)

        # On rail (engine warm-up, plane accelerates) — capture some frames
        for _ in range(5):
            await capture(page, 110)
            await page.wait_for_timeout(50)

        # Strategy: hold press while plane climbs, then alternate to keep airborne.
        # We script S.pressing directly because canvas mouse events are flaky in headless.
        # 1) Hold press for 1.5s — plane climbs from rail to ceiling.
        await page.evaluate("S.pressing = true;")
        for _ in range(15):
            await capture(page, 80)
            await page.wait_for_timeout(35)

        # 2) Quick alternation: release/press cycles for sustained flight + visible bobbing
        for cycle in range(3):
            await page.evaluate("S.pressing = false;")
            for _ in range(4):
                await capture(page, 80)
                await page.wait_for_timeout(35)
            await page.evaluate("S.pressing = true;")
            for _ in range(5):
                await capture(page, 80)
                await page.wait_for_timeout(35)

        # 3) Final descent toward landing
        await page.evaluate("S.pressing = false;")
        for _ in range(25):
            await capture(page, 90)
            await page.wait_for_timeout(40)
            phase = await page.evaluate("S.phase")
            if phase == "done":
                break

        # Show end screen briefly
        await page.wait_for_timeout(250)
        for _ in range(8):
            await capture(page, 140)
            await page.wait_for_timeout(80)

        await browser.close()


asyncio.run(main())

# Stride down frames
kept = list(range(0, len(frames), FRAME_STRIDE))
frames = [frames[i] for i in kept]
new_durations = []
for i, k in enumerate(kept):
    end = kept[i + 1] if i + 1 < len(kept) else len(durations)
    new_durations.append(sum(durations[k:end]))
durations = new_durations

out_w = int(W * SCALE)
out_h = int(H * SCALE)
small = [
    f.resize((out_w, out_h), Image.LANCZOS).convert("P", palette=Image.ADAPTIVE, colors=COLORS)
    for f in frames
]
print(f"frames: {len(small)}  total ms: {sum(durations)}")
OUT.parent.mkdir(parents=True, exist_ok=True)
small[0].save(
    OUT,
    save_all=True,
    append_images=small[1:],
    duration=durations,
    loop=0,
    optimize=True,
    disposal=2,
)
print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.1f} KB)")
