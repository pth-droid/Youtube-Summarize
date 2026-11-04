const {test, expect} = require('@playwright/test');
const fs = require('node:fs');

const srt = '1\n00:00:10,000 --> 00:00:15,000\nHeating affects reaction speed.\n\n2\n00:01:20,000 --> 00:01:25,000\nDevelopment time changes aroma.\n';
const browsers = [process.env.DISTILL_BROWSER, 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', 'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'].filter(Boolean);

async function makeDeck(page, label) {
  const title = `${label} ${Date.now()}`;
  await page.goto('/#new');
  await expect(page.locator('#create-button')).toBeEnabled();
  await page.getByRole('button', {name: 'Lecture slides', exact: true}).click();
  await page.getByRole('button', {name: 'Transcript file', exact: true}).click();
  await page.locator('#source-file').setInputFiles({name: 'deck.srt', mimeType: 'text/plain', buffer: Buffer.from(srt.replace('Heating', `Heating (${title})`))});
  await page.locator('#import-title').fill(title);
  await page.getByRole('button', {name: 'Create lecture slides'}).click();
  await expect(page.locator('#job-detail')).toContainText('Your lecture slides are ready.', {timeout: 20000});
  await page.getByRole('button', {name: 'Present lecture slides'}).click();
  return title;
}

test('slide editor: rail, hide, undo, duplicate, add, drag to reorder, change layout, delete', async ({page}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  // A tall window keeps the whole rail in view: a drag that has to scroll the rail is a browser matter, not this editor's.
  await page.setViewportSize({width: 1500, height: 1500});
  await makeDeck(page, 'Structure deck');
  const deck = page.frameLocator('#reader-frame');
  await expect(deck.locator('#counter')).toHaveText(/^1 \//);
  const shown = await deck.locator('.slide-frame').count();
  await page.getByRole('button', {name: 'Edit slides'}).click();
  await expect(deck.locator('html')).toHaveClass(/editing/);

  // The rail shows a thumbnail for every slide, and a copy of a slide never carries its editing marks.
  const rail = deck.locator('.rail-item'), slides = deck.locator('.rail-slide');
  await expect(rail).toHaveCount(shown);
  await expect(deck.locator('.rail-shot .slide').first()).toBeVisible();
  await expect(deck.locator('.rail-shot [data-field]')).toHaveCount(0);
  const first = await slides.count();
  expect(first).toBeGreaterThanOrEqual(2);
  const titles = async () => deck.locator('.rail-slide .rail-title').allTextContents();
  const before = await titles();

  // Hide: the slide stays in the editor, dimmed, and leaves the deck.
  await slides.nth(1).locator('.rail-open').click();
  await expect(deck.locator('.tools-name')).toHaveText(/Slide \d+ · part 1/);
  await deck.locator('[data-tool="hide"]').click();
  await expect(page.locator('#notice')).toContainText('Slide hidden');
  await expect(deck.locator('.rail-item.is-hidden')).toHaveCount(1);
  await expect(deck.locator('.rail-slide.is-current .rail-tag')).toHaveText('Hidden');
  await expect(deck.locator('[data-tool="hide"]')).toHaveText('Show');
  await expect(deck.locator('.slide-frame[data-hidden]')).toHaveCount(1);
  await expect(deck.locator('[data-tool="undo"]')).toHaveText('Undo (1)');
  // Undo and redo go through the same record the deck is drawn from.
  await deck.locator('[data-tool="undo"]').click();
  await expect(deck.locator('.rail-item.is-hidden')).toHaveCount(0);
  await expect(deck.locator('[data-tool="redo"]')).toBeEnabled();
  await deck.locator('[data-tool="redo"]').click();
  await expect(deck.locator('.rail-item.is-hidden')).toHaveCount(1);
  // The shown deck leaves the hidden slide out.
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', {name: 'Cancel', exact: true}).click();
  await expect(deck.locator('.slide-frame')).toHaveCount(shown - 1);
  // The deck does not count the hidden slide, so the slide in view keeps its place in the deck's own numbering.
  await expect(deck.locator('#counter')).toHaveText(new RegExp(`^5 / ${shown - 1}`));
  await page.getByRole('button', {name: 'Edit slides'}).click();
  await expect(deck.locator('.slide-frame')).toHaveCount(shown);
  await slides.nth(1).locator('.rail-open').click();
  await deck.locator('[data-tool="hide"]').click();
  await expect(deck.locator('.rail-item.is-hidden')).toHaveCount(0);

  // Duplicate and add keep the part's slides in order; the new slide is blank text ready to write.
  await slides.nth(0).locator('.rail-open').click();
  await deck.locator('[data-tool="duplicate"]').click();
  await expect(slides).toHaveCount(first + 1);
  expect((await titles())[1]).toBe(before[0]);
  await deck.locator('[data-tool="add"]').click();
  await expect(slides).toHaveCount(first + 2);
  await expect(deck.locator('.rail-slide.is-current .rail-title')).toHaveText(/New slide|Slide mới/);
  await expect(deck.locator('.slide-frame.is-current [data-field$=".points.0"]')).toHaveText(/Type your point here|Nhập ý/);

  // Drag the last slide above the first in the rail.
  const order = await titles();
  await slides.nth(order.length - 1).dragTo(slides.nth(0), {targetPosition: {x: 40, y: 4}});
  await expect(page.locator('#notice')).toContainText('Slide moved');
  await expect.poll(titles).toEqual([order[order.length - 1], ...order.slice(0, -1)]);

  // Change a layout with a preview, and see what it cuts before applying it.
  await slides.nth(1).locator('.rail-open').click();
  await deck.locator('[data-tool="layout"]').click();
  const dialog = page.locator('#layout-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('.layout-option')).toHaveCount(10);
  await expect(dialog.locator('.layout-option:disabled').first()).toContainText(/\w/);
  await expect(page.locator('#layout-apply')).toBeDisabled();
  const choice = dialog.locator('.layout-option:not(:disabled)').filter({hasNotText: 'current'}).first();
  const layout = await choice.getAttribute('data-layout');
  await choice.click();
  await expect(page.locator('#layout-apply')).toBeEnabled();
  const preview = page.frameLocator('#layout-frame');
  await expect(preview.locator('.slide-frame.is-current .slide')).toBeVisible();
  // The preview is the slide on the canvas, not the stacked list a narrow window gets.
  await expect(preview.locator('.slide-frame.is-current .slide')).toHaveCSS('border-radius', '0px');
  await expect(preview.locator('.slide-frame.is-current .slide')).toHaveCSS('width', '1280px');
  await expect(preview.locator('.slide-frame:visible')).toHaveCount(1);
  await page.locator('#layout-apply').click();
  await expect(page.locator('#notice')).toContainText('Layout changed');
  const saved = await page.evaluate(async id => (await (await fetch(`/api/generations/${id}/page`)).text()), await page.evaluate(() => state.readerId));
  expect(saved).toContain('kind-');
  await deck.locator('.rail-slide').nth(1).locator('.rail-open').click();
  await deck.locator('[data-tool="undo"]').click();
  await expect(deck.locator('[data-tool="redo"]')).toBeEnabled();

  // Delete: Undo brings the slide back. A part cannot lose its last slide.
  const count = await slides.count();
  await slides.nth(count - 1).locator('.rail-open').click();
  await deck.locator('[data-tool="delete"]').click();
  await expect(slides).toHaveCount(count - 1);
  await deck.locator('[data-tool="undo"]').click();
  await expect(slides).toHaveCount(count);
  expect(layout).toBeTruthy();
  expect(errors).toEqual([]);
});

test('export dialog: a PDF with a page for each shown slide and PNG pictures at 1, 2 and 3 times', async ({page}) => {
  test.skip(!browsers.some(path => fs.existsSync(path)), 'Needs Edge or Chrome on this computer.');
  test.setTimeout(120000);
  await makeDeck(page, 'Export deck');
  const deck = page.frameLocator('#reader-frame');
  await expect(deck.locator('#counter')).toHaveText(/^1 \//);
  const shown = await deck.locator('.slide-frame').count();
  await deck.locator('#next').click();
  await deck.locator('#next').click();
  await expect(deck.locator('#counter')).toHaveText(new RegExp(`^3 / ${shown}`));
  await page.getByRole('link', {name: 'Export'}).click();
  const dialog = page.locator('#export-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('#export-current')).toHaveText('This slide (3)');
  await expect(page.locator('#export-scale-group')).toBeHidden();

  const download = async () => {
    const wait = page.waitForEvent('download', {timeout: 90000});
    await page.locator('#export-go').click();
    const file = await wait;
    const path = test.info().outputPath(file.suggestedFilename());
    await file.saveAs(path);
    return {name: file.suggestedFilename(), data: fs.readFileSync(path)};
  };
  // All slides as a PDF: one page of 1280x720 px (960x540 pt) for each slide shown.
  await dialog.getByLabel('All slides').check();
  const pdf = await download();
  expect(pdf.name).toMatch(/\.pdf$/);
  expect(pdf.data.subarray(0, 5).toString()).toBe('%PDF-');
  const text = pdf.data.toString('latin1');
  expect((text.match(/\/Type\s*\/Page[^s]/g) || []).length).toBe(shown);
  expect(new Set(text.match(/\/MediaBox\s*\[[^\]]*\]/g)).size).toBe(1);
  expect(text).toContain('[0 0 960 540]');
  // One slide as a PNG at 2x: exactly 2560x1440 pixels.
  await page.getByRole('link', {name: 'Export'}).click();
  await dialog.getByLabel(/PNG pictures/).check();
  await dialog.getByLabel('This slide').check();
  await dialog.getByLabel(/^2×/).check();
  const png = await download();
  expect(png.name).toMatch(/slide-03\.png$/);
  expect(png.data.subarray(1, 4).toString()).toBe('PNG');
  expect([png.data.readUInt32BE(16), png.data.readUInt32BE(20)]).toEqual([2560, 1440]);
  // Every slide as PNG pictures arrives as one ZIP.
  await page.getByRole('link', {name: 'Export'}).click();
  await dialog.getByLabel(/PNG pictures/).check();
  await dialog.getByLabel('All slides').check();
  await dialog.getByLabel(/^1×/).check();
  const zip = await download();
  expect(zip.name).toMatch(/slides\.zip$/);
  expect(zip.data.subarray(0, 2).toString()).toBe('PK');
  expect(zip.data.toString('latin1').match(/PK\x03\x04/g).length).toBe(shown);
});
