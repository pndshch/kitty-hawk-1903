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

        # Click START. Then run a press/release rhythm INSIDE the page so the
        # cadence is independent of how long screenshots take. 480ms press /
        # 380ms release flies decently in the new physics.
        await page.click("#startBtn")
        await page.wait_for_timeout(80)
        await page.evaluate("""
          window._stopPulse = false;
          (function pulse(){
            if(window._stopPulse) return;
            S.pressing = true;
            setTimeout(() => {
              if(window._stopPulse) return;
              S.pressing = false;
              setTimeout(pulse, 380);
            }, 480);
          })();
        """)

        # Capture flight — alternating physics keeps the plane bobbing
        for i in range(40):
            await capture(page, 130)
            await page.wait_for_timeout(140)
            phase = await page.evaluate("S.phase")
            if phase == "done":
                break
            # Trigger a visible gust about midway through
            if i == 14:
                await page.evaluate(
                    "S.gustImpending=true; S.gustWarnTime=0.6; "
                    "S.gustStrength=18; S.gustCooldown=8;"
                )

        # Stop the rhythm; let the plane settle / land
        await page.evaluate("window._stopPulse = true; S.pressing = false;")

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
