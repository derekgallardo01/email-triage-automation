const { chromium } = require("playwright");
const fs = require("fs");

const BASE = process.env.DEMO_BASE;
if (!BASE) { console.error("DEMO_BASE env var is required."); process.exit(1); }

const OUT = "docs/screenshots";

// Single-page demo with 5 cards stacked. Full-page captures everything;
// hero is the viewport-only first-screen shot for inline embedding.
const CAPTURES = [
  { path: "/", name: "01-overview-fullpage", fullPage: true },
  { path: "/", name: "02-hero", fullPage: false },
];

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 2,
  });
  const page = await ctx.newPage();

  for (const c of CAPTURES) {
    const url = BASE + c.path;
    const file = `${OUT}/${c.name}.png`;
    console.log(`-> ${url}`);
    await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
    await page.screenshot({ path: file, fullPage: c.fullPage });
    console.log(`   wrote ${file} (${(fs.statSync(file).size / 1024).toFixed(1)} KB)`);
  }

  await browser.close();
})().catch((err) => { console.error(err); process.exit(1); });
