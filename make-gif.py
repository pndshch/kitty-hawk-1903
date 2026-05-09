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

        # Click START. Then drive S.pressing directly so we get a clean rhythm
        # demo (canvas pointer events are flaky in headless).
        await page.click("#startBtn")
        await page.wait_for_timeout(80)

        # Rail acceleration — pressing not yet engaged
        for _ in range(4):
            await capture(page, 130)
            await page.wait_for_timeout(120)

        # Once airborne, alternate press/release. Slight press-bias keeps the
        # plane gently climbing for visible bobbing.
        async def pulse(pressed: bool, frames: int, frame_ms: int = 120):
            await page.evaluate(f"S.pressing = {'true' if pressed else 'false'}")
            for _ in range(frames):
                await capture(page, 130)
                await page.wait_for_timeout(frame_ms)
                phase = await page.evaluate("S.phase")
                if phase == "done":
                    return True
            return False

        # 4 rhythm cycles: ~500ms press / ~400ms release
        for _ in range(4):
            if await pulse(True, 4): break
            if await pulse(False, 3): break

        # Trigger a visible gust late in the demo
        await page.evaluate(
            "S.gustImpending=true; S.gustWarnTime=0.6; "
            "S.gustStrength=18; S.gustCooldown=8;"
        )
        if not await pulse(True, 3):
            if not await pulse(False, 4):
                # Final descent
                await page.evaluate("S.pressing = false;")
                for _ in range(15):
                    await capture(page, 130)
                    await page.wait_for_timeout(140)
                    phase = await page.evaluate("S.phase")
                    if phase == "done":
                        break

        # End screen
        await page.wait_for_timeout(400)
        for _ in range(6):
            await capture(page, 160)
            await page.wait_for_timeout(100)

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
