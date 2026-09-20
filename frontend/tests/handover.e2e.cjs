// Run with a local Vite server and Playwright installed; all API data is isolated.
const { chromium, expect } = require('playwright/test');
const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let records = [], failSave = true, modelUnavailable = false;
    const sources = [1, 2].map(id => ({ event_id: `event-${id}`, bed_id: '103', patient_name: '測試病人',
      resolved_at: `2026-09-20T0${id}:00:00Z`, completed_actions: `處理內容 ${id}`, follow_up: `交班事項 ${id}`, notes: `備註 ${id}` }));
    await page.route('http://localhost:8000/**', async route => {
      const path = new URL(route.request().url()).pathname;
      let body, status = 200;
      if (path === '/api/beds') body = [{ bed_id: '103', patient_name: '測試病人', gender: 'male', age: 70, diagnosis: '測試', priority: 'green' }];
      else if (path.endsWith('/handover-sources')) body = sources.map(s => ({ ...s, included_in_handover: records.length > 0 }));
      else if (path.endsWith('/events/history') || path.endsWith('/events')) body = [];
      else if (path.endsWith('/handovers')) body = records;
      else if (path.endsWith('/handover-drafts')) {
        if (modelUnavailable) { status = 503; body = { detail: 'AI 摘要服務尚未啟用，請先完成模型設定' }; }
        else {
          const request = route.request().postDataJSON();
          assert.equal(request.source_event_ids.length, 2);
          body = { ...request, id: 'draft-1', completed_actions: 'AI 已完成摘要', follow_up: 'AI 交班事項', notes: 'AI 備註' };
        }
      } else if (path.endsWith('/submit')) {
        if (failSave) { status = 500; body = { detail: '儲存失敗，請重試' }; failSave = false; }
        else {
          body = { ...route.request().postDataJSON(), id: 'draft-1', source_event_ids: ['event-1', 'event-2'], submitted_at: '2026-09-20T12:00:00Z' };
          records = [body];
        }
      } else { status = 404; body = {}; }
      await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    });
    await page.goto(process.env.FRONTEND_URL || 'http://localhost:5173/room/103');
    await page.getByRole('button', { name: '產生交班紀錄' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('combobox', { name: '病人', exact: true })).toHaveCount(0);
    await expect(dialog.getByRole('textbox', { name: '病人', exact: true })).toHaveAttribute('readonly', '');
    await expect(dialog.getByRole('checkbox')).toHaveCount(2);
    await expect(dialog.getByRole('checkbox').first()).toBeChecked();
    await dialog.getByLabel('交班日期').fill('2026-09-20');
    await dialog.getByLabel('班別').selectOption('night');
    await dialog.getByRole('button', { name: 'AI 整理', exact: true }).click();
    await expect(dialog.getByRole('textbox', { name: '已完成的處理', exact: true })).toHaveValue('AI 已完成摘要');
    await dialog.getByRole('textbox', { name: '已完成的處理', exact: true }).fill('人工確認：協助回床並完成評估');
    await dialog.getByRole('textbox', { name: '備註', exact: true }).fill('人工補充備註');
    await dialog.getByRole('button', { name: '送出', exact: true }).click();
    await expect(dialog.getByRole('alert')).toHaveText('儲存失敗，請重試');
    await expect(dialog.getByRole('textbox', { name: '已完成的處理', exact: true })).toHaveValue('人工確認：協助回床並完成評估');
    await dialog.getByRole('button', { name: '送出', exact: true }).click();
    await expect(dialog).toHaveCount(0);
    const history = page.locator('.handover-panel');
    await expect(history).toContainText('2026-09-20・大夜班');
    await expect(history).toContainText('人工確認：協助回床並完成評估');
    await expect(history).toContainText('人工補充備註');
    await page.reload();
    await expect(history).toContainText('人工確認：協助回床並完成評估');
    await page.screenshot({ path: path.join(os.tmpdir(), 'ward-handover-desktop.png'), fullPage: true });
    await page.getByRole('button', { name: '產生交班紀錄' }).click();
    await expect(dialog.getByRole('checkbox').first()).not.toBeChecked();
    await dialog.getByRole('checkbox').first().check();
    await dialog.getByRole('checkbox').last().check();
    await dialog.getByRole('button', { name: 'AI 整理', exact: true }).click();
    await expect(dialog.getByRole('button', { name: '送出', exact: true })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(os.tmpdir(), 'ward-handover-editor.png'), fullPage: true });
    await dialog.getByRole('button', { name: '取消', exact: true }).click();
    assert.equal(records.length, 1);
    modelUnavailable = true;
    await page.getByRole('button', { name: '產生交班紀錄' }).click();
    await dialog.getByRole('checkbox').first().check();
    await dialog.getByRole('checkbox').last().check();
    await dialog.getByRole('button', { name: 'AI 整理', exact: true }).click();
    await expect(dialog.getByRole('alert')).toContainText('AI 摘要服務尚未啟用');
    await expect(dialog.getByRole('checkbox').first()).toBeChecked();
    await dialog.getByRole('button', { name: '取消', exact: true }).click();
    assert.deepEqual(errors, []);
    console.log('PASS: select, summarize, edit, failed-save retry, submit, reload, cancel, previous-source selection, mobile dialog, unavailable model');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
