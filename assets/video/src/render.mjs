// Usage: node render.mjs stills 1.0 2.2 ...   |   node render.mjs frames
import { chromium } from "playwright-core";
import { mkdirSync } from "fs";
const [mode, ...rest] = process.argv.slice(2);
const GIF = mode === "gif", FPS = GIF ? 15 : 30, DUR = 20;
const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? `${process.env.HOME}/Library/Caches/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-mac-arm64/chrome-headless-shell`,
});
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto(new URL("composition.html", import.meta.url).href + (GIF ? "?gif" : ""));
await page.evaluate(() => document.fonts.ready);
const shot = async (t, path) => { await page.evaluate((t) => window.render(t), t); await page.screenshot({ path }); };
if (mode === "stills") {
  mkdirSync("stills", { recursive: true });
  for (const t of rest.map(Number)) await shot(t, `stills/t${t.toFixed(2)}.png`);
} else {
  const dir = GIF ? "gifframes" : "frames";
  mkdirSync(dir, { recursive: true });
  for (let f = 0; f < FPS * DUR; f++) await shot(f / FPS, `${dir}/f${String(f).padStart(4, "0")}.png`);
}
await browser.close();
