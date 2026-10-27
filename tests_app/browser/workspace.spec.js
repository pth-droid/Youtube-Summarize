const {test, expect} = require('@playwright/test');
const fs = require('node:fs/promises');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

test.beforeEach(async ({page}) => {
  await page.goto('/#library');
  await expect(page.getByRole('heading', {name: 'Your learning library'})).toBeVisible();
  await expect(page.locator('.page-card').first()).toBeVisible();
});

test('change library folder preserves saved pages and worker processing', async ({page, request}) => {
  await page.locator('.nav-item[data-view="settings"]').click();
  await expect(page.locator('#library-folder')).toBeVisible();
  const original = await page.locator('#library-folder').inputValue();
  const selected = path.join(path.dirname(original), 'selected-library');
  await page.locator('#library-folder').fill(selected);
  await page.getByRole('button', {name: 'Change library folder', exact: true}).click();
  await expect(page.locator('#storage-details')).toContainText(selected);
  await page.reload();
  await page.locator('.nav-item[data-view="settings"]').click();
  await expect(page.locator('#library-folder')).toHaveValue(selected);
  const settings = await (await request.get('/api/settings')).json();
  expect(settings.storage.path).toBe(selected);
  const library = await (await request.get('/api/library')).json();
  expect(library.generations.length).toBeGreaterThan(0);
  const exported = await request.get(`/api/generations/${library.generations[0].id}/export`);
  expect(exported.ok()).toBeTruthy();
  expect(await exported.text()).toContain('<html');
  await page.locator('.nav-item[data-view="new"]').click();
  await page.getByRole('button', {name: 'Transcript file', exact: true}).click();
  await page.locator('#source-file').setInputFiles({name: 'relocated.srt', mimeType: 'text/plain', buffer: Buffer.from('1\n00:00:10,000 --> 00:00:15,000\nHeating affects reaction speed.\n\n2\n00:00:20,000 --> 00:00:25,000\nDevelopment time changes aroma.\n')});
  await page.locator('#import-title').fill('After library folder change');
  await page.getByRole('button', {name: 'Create interactive page'}).click();
  await expect(page.locator('#job-detail')).toContainText('Your learning page is ready.', {timeout: 20000});
  await page.locator('.nav-item[data-view="library"]').click();
  await expect(page.locator('.page-card').filter({hasText: 'After library folder change'})).toBeVisible();
  expect((await fs.stat(path.join(original, 'library.sqlite3'))).isFile()).toBeTruthy();
  expect((await fs.stat(path.join(selected, 'library.sqlite3'))).isFile()).toBeTruthy();
});

test('saved visual reader has evidence, branches, timeline and offline HTML export', async ({page, context}, testInfo) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const card = page.locator('.page-card').filter({hasText: 'Reader interaction fixture'});
  await expect(card).toBeVisible();
  await page.screenshot({path: '.feasibility/screenshots/library-desktop.png', fullPage: true});
  await card.getByRole('button', {name: 'Explore'}).click();
  const reader = page.frameLocator('#reader-frame');
  await expect(reader.locator('#reader')).toBeVisible();
  await reader.locator('[data-unit-id="u2"]').first().click();
  await expect(reader.locator('#detail-content')).toContainText('development time');
  await expect(reader.locator('#selected-evidence blockquote')).toContainText('Development time changes aroma');
  await reader.getByText('Khám phá sâu · 1 ý tưởng đã lưu', {exact: true}).click();
  await reader.getByRole('button', {name: /Origin changes the result/}).click();
  await expect(reader.locator('#detail-content h2')).toHaveText('Origin changes the result');
  await reader.getByRole('button', {name: 'Xem trong bản chép lời', exact: true}).click();
  await expect(reader.locator('.source-row.highlight')).toContainText('Development time changes aroma');
  await expect(reader.locator('.timeline')).toContainText('1:00');
  await expect(reader.locator('.source-row.highlight a')).toHaveAttribute('href', /&t=60s$/);
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', {name: 'Export HTML', exact: true}).click();
  const download = await downloadPromise;
  const target = testInfo.outputPath('learning-export.html');
  await download.saveAs(target);
  const html = await fs.readFile(target, 'utf8');
  expect(html).not.toContain('<script src=');
  expect(html).not.toContain('<link');
  await context.setOffline(true);
  const offline = await context.newPage();
  const external = [];
  offline.on('request', request => {if(/^https?:/.test(request.url()))external.push(request.url());});
  await offline.goto(pathToFileURL(target).href);
  await offline.locator('[data-unit-id="u1"]').first().click();
  await expect(offline.locator('#selected-evidence blockquote')).toContainText('Heat starts the roasting process');
  await offline.screenshot({path: '.feasibility/screenshots/reader-offline-desktop.png', fullPage: true});
  expect(external).toEqual([]);
  expect(errors).toEqual([]);
  await offline.close();
  await context.setOffline(false);
});

test('import source through the form, process it in the worker and save to the library', async ({page}) => {
  await page.locator('.nav-item[data-view="new"]').click();
  await page.getByRole('button', {name: 'Transcript file', exact: true}).click();
  await page.locator('#source-file').setInputFiles({name: 'source.srt', mimeType: 'text/plain', buffer: Buffer.from('1\n00:00:10,000 --> 00:00:15,000\nHeating affects reaction speed.\n\n2\n00:00:20,000 --> 00:00:25,000\nDevelopment time changes aroma.\n')});
  await page.locator('#import-title').fill('Browser import contract');
  await page.getByText('Options for this page', {exact: true}).click();
  await page.locator('#new-language').selectOption('en');
  await page.getByRole('button', {name: 'Create interactive page'}).click();
  await expect(page.locator('#job-detail')).toContainText('Your learning page is ready.', {timeout: 20000});
  await page.getByText('Generation details', {exact: true}).click();
  await expect(page.locator('#job-detail')).toContainText('Subscription allowance: unknown');
  await page.locator('.nav-item[data-view="library"]').click();
  await page.locator('#library-search').fill('Browser import contract');
  const card = page.locator('.page-card').filter({hasText: 'Browser import contract'});
  await expect(card).toBeVisible();
  await card.getByRole('button', {name: 'Explore'}).click();
  const reader = page.frameLocator('#reader-frame');
  await expect(reader.locator('#transcript-list')).toContainText('Heating affects reaction speed');
  await expect(reader.locator('#transcript-list')).toContainText('0:10');
});

test('caption failure asks for audio consent and cancellation prevents processing', async ({page}) => {
  await page.locator('.nav-item[data-view="new"]').click();
  await page.locator('#video-url').fill('https://www.youtube.com/watch?v=0qqW3vxOC-g');
  await page.getByRole('button', {name: 'Create interactive page'}).click();
  await expect(page.getByRole('heading', {name: 'Approve audio transcription'})).toBeVisible({timeout: 15000});
  await expect(page.locator('#audio-consent')).not.toBeChecked();
  await expect(page.locator('#paid-audio-confirm')).not.toBeChecked();
  await expect(page.locator('.job-approval')).toContainText('Labelled automatically');
  await page.getByRole('button', {name: 'Continue with Soniox'}).click();
  await expect(page.locator('#notice')).toContainText('Approve audio processing for this source');
  await page.getByRole('button', {name: 'Cancel processing'}).click();
  await expect(page.locator('#job-detail .job-stage strong')).toHaveText('Cancelled');
});

test('diagnostic details stay open when job polling changes the record', async ({page}) => {
  let revision = 0;
  await page.route('**/api/jobs', route => route.fulfill({json: {jobs: [{
    id: 'diagnostic-fixture', state: 'failed', created_at: '2026-10-05T00:00:00Z',
    input: {title: 'Diagnostic fixture', preferences: {provider: 'deepseek', language: 'vi', knowledge_level: 'balanced'}},
    progress: {message: 'Stopped ' + revision++},
    error: {message: 'Fixture error', diagnostics: {rule: 'literal_error'}}
  }]}}));
  await page.goto('/#jobs');
  await page.locator('[data-job="diagnostic-fixture"]').click();
  const details = page.locator('#job-detail details.advanced').filter({hasText: 'Diagnostic details'});
  await details.locator('summary').click();
  await page.waitForTimeout(5500);
  await expect(details).toHaveAttribute('open', '');
  await expect(details.locator('pre')).toBeVisible();
});

test('mobile library, genuine semantic page, settings persistence and backup', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: '.feasibility/screenshots/library-mobile.png', fullPage: true});
  const real = page.locator('.page-card').filter({hasText: 'Real Codex source sample'});
  if(await real.count()) {
    await real.getByRole('button', {name: 'Explore'}).click();
    const reader = page.frameLocator('#reader-frame');
    await expect(reader.locator('[data-unit-id]').first()).toBeVisible();
    await reader.locator('[data-unit-id]').first().click();
    await expect(reader.locator('#detail-panel')).toHaveClass(/active/);
    const frame = page.frames().find(frame => frame.url().includes('/page'));
    expect(await frame.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({path: '.feasibility/screenshots/real-reader-mobile.png', fullPage: true});
  }
  await page.getByRole('button', {name: 'Menu', exact: true}).click();
  await page.locator('.nav-item[data-view="settings"]').click();
  await page.locator('#settings-language').selectOption('en');
  await page.getByRole('button', {name: 'Save preferences'}).click();
  await expect(page.locator('#notice')).toContainText('Preferences saved');
  await page.reload();
  await expect(page.locator('#settings-language')).toHaveValue('en');
  const pending = page.waitForEvent('download');
  await page.getByRole('button', {name: 'Download library backup'}).click();
  const backup = await pending;
  expect(backup.suggestedFilename()).toMatch(/distill-.*.zip/);
  await page.screenshot({path: '.feasibility/screenshots/settings-mobile.png', fullPage: true});
});
