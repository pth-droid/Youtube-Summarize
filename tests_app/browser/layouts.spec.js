const {test, expect} = require('@playwright/test');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

// Four authored decks start the layout rotation at each of the four variants (tests_app/variant_fixture.py).
const deck = name => pathToFileURL(path.resolve(`.feasibility/variant-fixtures/${name}.html`)).href;

test.beforeAll(() => {
  execFileSync(path.resolve('.venv/Scripts/python.exe'), ['-m', 'tests_app.variant_fixture'], {stdio: 'pipe'});
});

// Each look brings its own type (Bahnschrift, Palatino, Candara...), so every look is measured, not only its colours.
const LOOKS = ['forest', 'maroon', 'navy', 'contrast', 'editorial', 'slate', 'workshop'];
for (const look of LOOKS) for (const first of [0, 1, 2, 3]) {
  test(`layouts: every slide of gallery deck ${first} fits its canvas, fully built, in the ${look} look`, async ({page}) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewportSize({width: 1366, height: 800});
    await page.goto(deck(`gallery-${first}-${look}`));
    const total = await page.locator('.slide-frame').count();
    const problems = [];
    for (let n = 1; n <= total; n++) {
      await page.evaluate(k => { location.hash = `#slide-${k}`; }, n);
      const issue = await page.evaluate(() => {
        const slide = document.querySelector('.slide-frame.is-current .slide');
        slide.querySelectorAll('.build-pending').forEach(item => item.classList.remove('build-pending'));
        for (const animation of document.getAnimations()) animation.finish();  // measure parts where they land
        const box = slide.getBoundingClientRect(), out = [];
        for (const node of slide.querySelectorAll('h1, h2, .slide-content *')) {
          const r = node.getBoundingClientRect();
          if (r.width && (r.left < box.left - 2 || r.right > box.right + 2 || r.bottom > box.bottom + 2)) out.push(node.tagName.toLowerCase());
        }
        return slide.scrollHeight > slide.clientHeight + 1 || out.length ? `${slide.className}: ${out.slice(0, 3).join(',') || 'scrolls'}` : '';
      });
      if (issue) problems.push(`#${n} ${issue}`);
    }
    expect(problems).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test('layouts: a phone reads every slide as a stacked list with no sideways scroll', async ({page}) => {
  await page.setViewportSize({width: 390, height: 800});
  await page.goto(deck('gallery-0-forest'));
  await expect(page.locator('.slide-frame').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  // The fixed canvas belongs to presenting and print only.
  expect(await page.locator('.slide').first().evaluate(slide => slide.getBoundingClientRect().width)).toBeLessThan(400);
});
