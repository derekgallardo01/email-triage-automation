// Generates branded portfolio images for the repo.
//
// Reads docs/portfolio-config.json for per-repo content (title, tagline,
// kicker, features, theme colors). Renders a single HTML template at two
// viewport sizes and captures each as a PNG into docs/portfolio/.
//
// Run by .github/workflows/portfolio.yml.

const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const CONFIG_PATH = "docs/portfolio-config.json";
const OUT = "docs/portfolio";

if (!fs.existsSync(CONFIG_PATH)) {
  console.error(`Missing ${CONFIG_PATH}. Add it before running.`);
  process.exit(1);
}

const cfg = JSON.parse(fs.readFileSync(CONFIG_PATH, "utf-8"));

// Sizes to capture: name -> {width, height}.
const SIZES = {
  "01-card-1200x630": { width: 1200, height: 630 },
  "02-hero-1920x1080": { width: 1920, height: 1080 },
};

function renderHtml(size) {
  const primary = cfg.theme.primary;
  const accent = cfg.theme.accent;
  const features = (cfg.features || []).map(
    (f) => `
      <div class="feature">
        <div class="label">${escape(f.label)}</div>
        <div class="value">${escape(f.value)}</div>
      </div>`
  ).join("");

  // Type-scale tuned to the viewport so 1200x630 and 1920x1080 both look good.
  const scale = size.width === 1920 ? 1.45 : 1.0;
  const titleSize = Math.round(56 * scale);
  const taglineSize = Math.round(22 * scale);
  const kickerSize = Math.round(14 * scale);
  const featureLabelSize = Math.round(12 * scale);
  const featureValueSize = Math.round(18 * scale);
  const footerSize = Math.round(14 * scale);
  const pad = Math.round(60 * scale);

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${escape(cfg.title)}</title>
<style>
  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0;
    width: ${size.width}px; height: ${size.height}px;
    overflow: hidden;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  }
  body {
    background: linear-gradient(135deg, ${primary} 0%, ${accent} 100%);
    color: white;
    padding: ${pad}px ${pad + 20}px;
    position: relative;
  }
  .kicker {
    font-size: ${kickerSize}px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 2px;
    opacity: 0.75;
    margin-bottom: 14px;
  }
  .title {
    font-size: ${titleSize}px;
    font-weight: 700;
    margin: 0 0 18px;
    line-height: 1.05;
    letter-spacing: -0.5px;
  }
  .tagline {
    font-size: ${taglineSize}px;
    font-weight: 300;
    opacity: 0.92;
    margin: 0 0 ${Math.round(34 * scale)}px;
    line-height: 1.45;
    max-width: ${Math.round(900 * scale)}px;
  }
  .features {
    display: flex;
    gap: ${Math.round(20 * scale)}px;
    max-width: ${Math.round(1000 * scale)}px;
  }
  .feature {
    flex: 1;
    padding: ${Math.round(18 * scale)}px ${Math.round(22 * scale)}px;
    background: rgba(255,255,255,0.12);
    border-radius: ${Math.round(8 * scale)}px;
    backdrop-filter: blur(4px);
  }
  .feature .label {
    font-size: ${featureLabelSize}px;
    text-transform: uppercase;
    letter-spacing: 1px;
    opacity: 0.7;
    font-weight: 600;
  }
  .feature .value {
    font-size: ${featureValueSize}px;
    font-weight: 600;
    margin-top: 6px;
    line-height: 1.2;
  }
  .footer {
    position: absolute;
    bottom: ${pad - 25}px;
    left: ${pad + 20}px;
    right: ${pad + 20}px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: ${footerSize}px;
    opacity: 0.7;
  }
  .footer .repo { font-family: Consolas, 'SF Mono', Menlo, monospace; }
  .footer .by { font-weight: 600; }
</style>
</head>
<body>
  <div class="kicker">${escape(cfg.kicker)}</div>
  <h1 class="title">${escape(cfg.title)}</h1>
  <p class="tagline">${escape(cfg.tagline)}</p>
  <div class="features">${features}</div>
  <div class="footer">
    <span class="repo">github.com/derekgallardo01/${escape(cfg.repo)}</span>
    <span class="by">Derek Gallardo</span>
  </div>
</body>
</html>`;
}

function escape(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });

  const browser = await chromium.launch();

  for (const [name, size] of Object.entries(SIZES)) {
    const html = renderHtml(size);
    const tmpPath = path.join(OUT, `_${name}.html`);
    fs.writeFileSync(tmpPath, html, "utf-8");

    const ctx = await browser.newContext({
      viewport: { width: size.width, height: size.height },
      deviceScaleFactor: 2,
    });
    const page = await ctx.newPage();
    await page.goto("file://" + path.resolve(tmpPath));
    await page.waitForLoadState("networkidle");

    const file = path.join(OUT, `${name}.png`);
    await page.screenshot({ path: file, fullPage: false });

    fs.unlinkSync(tmpPath);
    await ctx.close();

    console.log(`wrote ${file} (${(fs.statSync(file).size / 1024).toFixed(1)} KB)`);
  }

  await browser.close();
})().catch((err) => { console.error(err); process.exit(1); });
