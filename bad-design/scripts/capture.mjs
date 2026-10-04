#!/usr/bin/env node
// bad-design screenshot capture.
// Captures screens x states x themes x widths with Playwright and writes a manifest.json.
//
// Usage:
//   node capture.mjs --config bad-design.screens.json [--out DIR] [--only NAME] [--dry-run]
//   node capture.mjs --url http://localhost:3000/settings --name settings [--widths 375,1440] [--themes light]
//
// Exit codes: 0 all captured, 2 some captures failed (see manifest), 1 fatal error.

import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const DEFAULTS = {
  widths: [375, 768, 1440],
  themes: ['light', 'dark'],
  fullPage: true,
  scale: 1,
  timeoutMs: 30000,
  settleMs: 5000,
  mask: [],
};

// ---------- args ----------
function parseArgs(argv) {
  const a = {};
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (!k.startsWith('--')) continue;
    const key = k.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith('--')) a[key] = true;
    else { a[key] = next; i++; }
  }
  return a;
}
const list = (v) => String(v).split(',').map((s) => s.trim()).filter(Boolean);
const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'x';
const today = () => new Date().toISOString().slice(0, 10);

async function loadConfig(args) {
  let cfg = {};
  if (args.config) {
    const raw = await fs.readFile(args.config, 'utf8');
    cfg = JSON.parse(raw);
  } else if (args.url) {
    const u = new URL(args.url);
    cfg = {
      baseUrl: u.origin,
      screens: [{ name: args.name || slug(u.pathname) || 'home', path: u.pathname + u.search }],
    };
  } else {
    throw new Error('Pass --config <file> or --url <url>.');
  }
  cfg = { ...DEFAULTS, ...cfg };
  if (args.widths) cfg.widths = list(args.widths).map(Number);
  if (args.themes) cfg.themes = list(args.themes);
  if (args['no-full-page']) cfg.fullPage = false;
  if (args.base) cfg.baseUrl = args.base;
  if (!cfg.baseUrl) throw new Error('Config needs "baseUrl" (or pass --base).');
  if (!Array.isArray(cfg.screens) || cfg.screens.length === 0) throw new Error('Config needs a non-empty "screens" array.');
  if (args.only) cfg.screens = cfg.screens.filter((s) => list(args.only).includes(s.name));
  cfg.out = args.out || cfg.out || path.join('design-reviews', 'shots', today());
  return cfg;
}

function plan(cfg) {
  const jobs = [];
  for (const screen of cfg.screens) {
    const states = screen.states?.length ? screen.states : [{ name: 'default' }];
    for (const state of states) {
      for (const theme of cfg.themes) {
        for (const width of cfg.widths) {
          const base = `${slug(screen.name)}-${slug(state.name)}-${slug(theme)}-${width}`;
          jobs.push({ screen, state, theme, width, base });
        }
      }
    }
  }
  return jobs;
}

// ---------- playwright ----------
async function loadPlaywright() {
  // Resolve from the project (cwd) first, so the skill can live outside the repo.
  const req = createRequire(path.join(process.cwd(), 'noop.js'));
  for (const name of ['playwright', '@playwright/test']) {
    try { return await import(pathToFileURL(req.resolve(name)).href); } catch {}
    try { return await import(name); } catch {}
  }
  throw new Error(
    'Playwright not found. Install it in the project:\n' +
    '  npm i -D playwright && npx playwright install chromium'
  );
}

function viewportHeight(width) {
  if (width < 600) return 812;
  if (width < 1024) return 1024;
  return 900;
}

const withTimeout = (p, ms) => Promise.race([p, new Promise((r) => setTimeout(r, ms))]);

async function applyMocks(page, mocks = []) {
  for (const m of mocks) {
    await page.route(m.url, async (route) => {
      if (m.hang) return; // never resolves: keeps the UI in its loading state
      if (m.delayMs) await new Promise((r) => setTimeout(r, m.delayMs));
      if (m.status || m.json !== undefined || m.body !== undefined) {
        return route.fulfill({
          status: m.status ?? 200,
          contentType: m.json !== undefined ? 'application/json' : (m.contentType ?? 'text/plain'),
          body: m.json !== undefined ? JSON.stringify(m.json) : (m.body ?? ''),
        });
      }
      return route.continue();
    });
  }
}

async function runSteps(page, steps = [], cfg) {
  for (const step of steps) {
    const [action, arg] = Object.entries(step)[0] ?? [];
    const sel = typeof arg === 'string' ? arg : arg?.selector;
    switch (action) {
      case 'goto': await page.goto(new URL(arg, cfg.baseUrl).href, { waitUntil: 'domcontentloaded' }); break;
      case 'reload': await page.reload({ waitUntil: 'domcontentloaded' }); break;
      case 'click': await page.locator(sel).first().click(); break;
      case 'hover': await page.locator(sel).first().hover(); break;
      case 'focus': await page.locator(sel).first().focus(); break;
      case 'fill': await page.locator(arg.selector).first().fill(String(arg.value)); break;
      case 'check': await page.locator(sel).first().check(); break;
      case 'select': await page.locator(arg.selector).first().selectOption(arg.value); break;
      case 'press':
        if (typeof arg === 'string') await page.keyboard.press(arg);
        else await page.locator(arg.selector).first().press(arg.key);
        break;
      case 'waitFor': await page.locator(sel).first().waitFor({ state: arg?.state ?? 'visible' }); break;
      case 'waitForUrl': await page.waitForURL(arg); break;
      case 'waitMs': await page.waitForTimeout(Number(arg)); break;
      case 'scroll':
        if (arg === 'bottom') await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        else await page.locator(sel).first().scrollIntoViewIfNeeded();
        break;
      case 'setLocalStorage':
        await page.evaluate((kv) => { for (const [k, v] of Object.entries(kv)) localStorage.setItem(k, v); }, arg);
        break;
      default: throw new Error(`Unknown step "${action}"`);
    }
  }
}

async function settle(page, cfg, hasHang) {
  if (!hasHang) {
    try { await page.waitForLoadState('networkidle', { timeout: cfg.settleMs }); } catch {}
  }
  await withTimeout(page.evaluate(() => document.fonts?.ready.then(() => true)), 3000).catch(() => {});
  await page.waitForTimeout(250);
}

async function capture(browser, cfg, job, outDir) {
  const { screen, state, theme, width, base } = job;
  const rec = {
    file: `${base}.png`, screen: screen.name, state: state.name, theme, width,
    url: null, ok: false, fullFile: null, pageHeight: null, consoleErrors: [], failedRequests: [], error: null,
  };
  const mobile = width < 600;
  const context = await browser.newContext({
    viewport: { width, height: viewportHeight(width) },
    deviceScaleFactor: cfg.scale,
    isMobile: mobile,
    hasTouch: mobile,
    colorScheme: theme === 'dark' ? 'dark' : 'light',
    reducedMotion: 'reduce',
    storageState: cfg.storageState || undefined,
    locale: cfg.locale || undefined,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(cfg.timeoutMs);
  page.on('console', (m) => { if (m.type() === 'error') rec.consoleErrors.push(m.text().slice(0, 300)); });
  page.on('requestfailed', (r) => rec.failedRequests.push(`${r.method()} ${r.url()} ${r.failure()?.errorText ?? ''}`.slice(0, 300)));
  try {
    const mocks = [...(screen.mocks ?? []), ...(state.mocks ?? [])];
    await applyMocks(page, mocks);
    const target = new URL(state.path ?? screen.path ?? '/', cfg.baseUrl).href;
    rec.url = target;
    await page.goto(target, { waitUntil: 'domcontentloaded' });
    const hasHang = mocks.some((m) => m.hang);
    await settle(page, cfg, hasHang);
    await runSteps(page, cfg.themeSteps?.[theme], cfg);
    await runSteps(page, screen.steps, cfg);
    await runSteps(page, state.steps, cfg);
    await settle(page, cfg, hasHang);

    const mask = [...cfg.mask, ...(screen.mask ?? []), ...(state.mask ?? [])].map((s) => page.locator(s));
    const opts = { animations: 'disabled', caret: 'hide', mask };
    await page.screenshot({ ...opts, path: path.join(outDir, rec.file) });

    rec.pageHeight = await page.evaluate(() => document.documentElement.scrollHeight);
    const fullWanted = state.fullPage ?? screen.fullPage ?? cfg.fullPage;
    if (fullWanted && rec.pageHeight > viewportHeight(width) * 1.2) {
      rec.fullFile = `${base}-full.png`;
      await page.screenshot({ ...opts, fullPage: true, path: path.join(outDir, rec.fullFile) });
    }
    rec.ok = true;
  } catch (e) {
    rec.error = String(e?.message ?? e).split('\n')[0];
    try { await page.screenshot({ path: path.join(outDir, `${base}-FAILED.png`) }); rec.failedFile = `${base}-FAILED.png`; } catch {}
  } finally {
    await context.close();
  }
  return rec;
}

// ---------- main ----------
async function main() {
  const args = parseArgs(process.argv.slice(2));
  const cfg = await loadConfig(args);
  const jobs = plan(cfg);

  if (args['dry-run']) {
    console.log(`Would capture ${jobs.length} screenshot(s) into ${cfg.out}:`);
    for (const j of jobs) console.log(`  ${j.base}.png  <- ${new URL(j.state.path ?? j.screen.path ?? '/', cfg.baseUrl).href}`);
    return 0;
  }

  const pw = await loadPlaywright();
  const chromium = pw.chromium ?? pw.default?.chromium;
  if (!chromium) throw new Error('Playwright loaded but chromium is missing; run: npx playwright install chromium');
  await fs.mkdir(cfg.out, { recursive: true });
  const browser = await chromium.launch();
  const results = [];
  try {
    for (const job of jobs) {
      const rec = await capture(browser, cfg, job, cfg.out);
      console.log(`${rec.ok ? 'ok  ' : 'FAIL'} ${rec.file}${rec.fullFile ? ` (+ ${rec.fullFile})` : ''}${rec.error ? `  ${rec.error}` : ''}`);
      results.push(rec);
    }
  } finally {
    await browser.close();
  }

  const manifest = {
    capturedAt: new Date().toISOString(),
    baseUrl: cfg.baseUrl,
    widths: cfg.widths,
    themes: cfg.themes,
    total: results.length,
    failed: results.filter((r) => !r.ok).length,
    captures: results,
  };
  await fs.writeFile(path.join(cfg.out, 'manifest.json'), JSON.stringify(manifest, null, 2));
  console.log(`\n${results.length - manifest.failed}/${results.length} captured. Manifest: ${path.join(cfg.out, 'manifest.json')}`);
  return manifest.failed ? 2 : 0;
}

main().then((code) => process.exit(code)).catch((e) => {
  console.error(`capture: ${e.message}`);
  process.exit(1);
});
