const puppeteer = require('./carousel-routine/node_modules/puppeteer');
const fs = require('fs');
const path = require('path');
const http = require('http');

const ROOT = __dirname;
const OUTPUT_DIR = path.join(ROOT, 'output');
fs.mkdirSync(OUTPUT_DIR, { recursive: true });
fs.mkdirSync(path.join(ROOT, 'assets'), { recursive: true });

function loadPlan() {
  const planPath = path.join(ROOT, 'daily_post_plan.json');
  if (!fs.existsSync(planPath)) {
    return { post_types: ['NewsCard', 'NewsCard', 'NewsCard', 'SSBCard'] };
  }
  return JSON.parse(fs.readFileSync(planPath, 'utf8'));
}

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function applyHighlights(text, phrases, className = 'highlight') {
  let html = escapeHtml(text);
  for (const phrase of phrases || []) {
    if (!phrase) continue;
    const escaped = escapeHtml(phrase);
    const re = new RegExp(escaped.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    html = html.replace(re, (m) => `<span class="${className}">${m}</span>`);
  }
  return html;
}

function replaceAll(template, replacements) {
  let out = template;
  for (const [key, val] of Object.entries(replacements)) {
    out = out.split(key).join(val ?? '');
  }
  return out;
}

function resolveBgPath(relPath) {
  const normalized = (relPath || '').replace(/^\.\//, '');
  const abs = path.join(ROOT, normalized);
  if (fs.existsSync(abs)) {
    return `/${normalized.replace(/\\/g, '/')}`;
  }
  return '/assets/card-bg_1.svg';
}

function buildNewsCard(num, data) {
  const templatePath = path.join(ROOT, 'instagram-newscard-template.html');
  const template = fs.readFileSync(templatePath, 'utf8');
  const bgUrl = resolveBgPath(data.background_image);
  const headlineHtml = applyHighlights(
    (data.headline || data.title || '').toUpperCase(),
    data.highlight_phrases || []
  );
  const html = replaceAll(template, {
    '{{BACKGROUND_IMAGE}}': bgUrl,
    '{{BADGE}}': escapeHtml(data.badge || 'NEWS'),
    '{{HEADLINE_HTML}}': headlineHtml,
    '{{IMAGE_SOURCE}}': escapeHtml(data.image_source || 'Source: News | @ssb.connect'),
  });
  const outPath = path.join(ROOT, `instagram-newscard_${num}.html`);
  fs.writeFileSync(outPath, html);
  console.log(`Built news card HTML: ${outPath}`);
}

function buildSsbCard(num, data) {
  const templatePath = path.join(ROOT, 'instagram-ssbcard-template.html');
  const template = fs.readFileSync(templatePath, 'utf8');
  const bgUrl = resolveBgPath(data.background_image);
  const headerHtml = applyHighlights(data.header || '', [data.header_highlight].filter(Boolean));
  const detailHtml = applyHighlights(data.detail || '', data.detail_highlights || []);
  const html = replaceAll(template, {
    '{{BACKGROUND_IMAGE}}': bgUrl,
    '{{TOPIC}}': escapeHtml(data.topic || 'SSB'),
    '{{HEADER_HTML}}': headerHtml,
    '{{HEADLINE}}': escapeHtml(data.headline || ''),
    '{{DETAIL_HTML}}': detailHtml,
  });
  const outPath = path.join(ROOT, `instagram-ssbcard_${num}.html`);
  fs.writeFileSync(outPath, html);
  console.log(`Built SSB card HTML: ${outPath}`);
}

function safeJoin(root, urlPath) {
  const decoded = decodeURIComponent(urlPath.split('?')[0]);
  const resolved = path.normalize(path.join(root, decoded));
  if (!resolved.startsWith(root)) return null;
  return resolved;
}

async function renderScreenshots(plan) {
  const postTypes = plan.post_types || [];
  const serverRoot = ROOT;

  const server = http.createServer((req, res) => {
    try {
      const filePath = safeJoin(serverRoot, req.url);
      if (!filePath || !fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
        res.writeHead(404);
        res.end('Not Found');
        return;
      }
      const ext = path.extname(filePath).toLowerCase();
      const types = {
        '.html': 'text/html',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.svg': 'image/svg+xml',
        '.webp': 'image/webp',
      };
      res.writeHead(200, { 'Content-Type': types[ext] || 'application/octet-stream' });
      res.end(fs.readFileSync(filePath));
    } catch {
      res.writeHead(500);
      res.end('Error');
    }
  });

  await new Promise((r) => server.listen(0, r));
  const port = server.address().port;
  console.log(`Asset server on http://localhost:${port}`);

  const chromePaths = [
    process.env.CHROME_PATH,
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    '/usr/bin/google-chrome',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ].filter(Boolean);

  const launchOpts = {
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  };
  for (const p of chromePaths) {
    if (fs.existsSync(p)) {
      launchOpts.executablePath = p;
      console.log(`Using Chrome at: ${p}`);
      break;
    }
  }

  const browser = await puppeteer.launch({ ...launchOpts, timeout: 30000 });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1080, height: 1080, deviceScaleFactor: 2 });

    for (let idx = 0; idx < postTypes.length; idx++) {
      const ptype = postTypes[idx];
      const num = idx + 1;
      const prefix = ptype === 'NewsCard' ? 'newscard' : 'ssbcard';
      const dataPath = path.join(ROOT, `${prefix}_${num}.json`);
      if (!fs.existsSync(dataPath)) {
        console.log(`Skipping post ${num}: ${dataPath} missing`);
        continue;
      }

      const htmlName = ptype === 'NewsCard' ? `instagram-newscard_${num}.html` : `instagram-ssbcard_${num}.html`;
      const pngName = ptype === 'NewsCard' ? `instagram-newscard_${num}.png` : `instagram-ssbcard_${num}.png`;
      const url = `http://localhost:${port}/${htmlName}`;
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await new Promise((r) => setTimeout(r, 500));
      await page.screenshot({ path: path.join(OUTPUT_DIR, pngName), timeout: 15000 });
      console.log(`Captured output/${pngName}`);
    }
  } finally {
    await browser.close().catch(() => {});
    server.close();
  }
}

async function main() {
  const plan = loadPlan();
  const postTypes = plan.post_types || [];

  for (let idx = 0; idx < postTypes.length; idx++) {
    const ptype = postTypes[idx];
    const num = idx + 1;
    const prefix = ptype === 'NewsCard' ? 'newscard' : 'ssbcard';
    const dataPath = path.join(ROOT, `${prefix}_${num}.json`);
    if (!fs.existsSync(dataPath)) {
      console.log(`Warning: ${dataPath} not found`);
      continue;
    }
    const data = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
    if (ptype === 'NewsCard') buildNewsCard(num, data);
    else if (ptype === 'SSBCard') buildSsbCard(num, data);
  }

  await renderScreenshots(plan);
  console.log('All card visuals rendered.');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
