import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

const snapshots = [];

page.on('response', async (response) => {
  const url = response.url();
  if (!url.includes('/api/chat')) return;
  let body = '';
  try {
    body = await response.text();
  } catch {
    body = '<unreadable>';
  }
  snapshots.push({
    url,
    status: response.status(),
    ok: response.ok(),
    body,
  });
});

await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' });
await page.fill('textarea', '你好');
await page.click('button.send-button');
await page.waitForFunction(() => {
  const rows = Array.from(document.querySelectorAll('.message-row--assistant .message-bubble p'));
  return rows.length >= 2 && !rows.some((el) => el.textContent?.includes('正在思考中...'));
}, { timeout: 120000 });

const successAssistant = await page.locator('.message-row--assistant .message-bubble p').nth(1).textContent();
const successError = await page.locator('.error-text').count();

await page.fill('textarea', '   ');
await page.click('button.send-button');
await page.waitForTimeout(1000);

const afterBlankMessageCount = await page.locator('.message-row').count();
const errorText = await page.locator('.error-text').count() ? await page.locator('.error-text').textContent() : null;

console.log(JSON.stringify({
  snapshots,
  successAssistant,
  successErrorCount: successError,
  afterBlankMessageCount,
  errorText,
}, null, 2));

await browser.close();
