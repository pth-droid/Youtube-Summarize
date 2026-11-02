const {test, expect} = require('@playwright/test');

const cards = page => page.locator('.settings-section:visible');
const tab = (page, section) => page.locator(`.settings-nav a[data-section="${section}"]`);

test('settings show one section card at a time, routed through the address', async ({page}) => {
  await page.goto('/#settings');
  await expect(page.locator('#storage-details')).not.toBeEmpty();
  // Settings alone opens the first card, marked in the nav.
  await expect(cards(page)).toHaveCount(1);
  await expect(page.locator('#settings-defaults')).toBeVisible();
  await expect(tab(page, 'defaults')).toHaveAttribute('aria-current', 'page');
  await expect(tab(page, 'defaults')).toHaveClass(/active/);

  await tab(page, 'ai').click();
  await expect(page).toHaveURL(/#settings\/ai$/);
  await expect(cards(page)).toHaveCount(1);
  await expect(page.locator('#settings-ai')).toBeVisible();
  await expect(tab(page, 'ai')).toHaveAttribute('aria-current', 'page');
  await expect(page.locator('.settings-nav a[aria-current]')).toHaveCount(1);
  await tab(page, 'library').click();
  await expect(page.locator('#settings-library')).toBeVisible();

  // Back and forward walk the cards.
  await page.goBack();
  await expect(page).toHaveURL(/#settings\/ai$/);
  await expect(page.locator('#settings-ai')).toBeVisible();
  await expect(page.locator('#settings-library')).toBeHidden();
  await page.goForward();
  await expect(page.locator('#settings-library')).toBeVisible();

  // A loaded address opens its card; an unknown one falls back to the first.
  await page.goto('/#settings/audio');
  await expect(page.locator('#settings-audio')).toBeVisible();
  await expect(cards(page)).toHaveCount(1);
  await page.goto('/#settings/nowhere');
  await expect(page.locator('#settings-defaults')).toBeVisible();
});

test('an unsaved change keeps its save bar while another card is open', async ({page}) => {
  await page.goto('/#settings/defaults');
  await expect(page.locator('#storage-details')).not.toBeEmpty();
  await expect(page.locator('#settings-form')).toBeHidden();
  const level = await page.locator('#settings-level').inputValue();
  await page.locator('#settings-level').selectOption(level === 'advanced' ? 'beginner' : 'advanced');
  await expect(page.locator('#settings-form')).toBeVisible();
  await tab(page, 'looks').click();
  await expect(page.locator('#settings-defaults')).toBeHidden();
  await expect(page.locator('#settings-form')).toBeVisible();
  await page.getByRole('button', {name: 'Discard', exact: true}).click();
  await expect(page.locator('#settings-form')).toBeHidden();
  await expect(page.locator('#settings-level')).toHaveValue(level);
});

test('the look editor still opens from its address and returns to the looks card', async ({page}) => {
  await page.goto('/#settings/looks/maroon');
  await expect(page.getByRole('heading', {name: 'Maroon and beige', level: 1})).toBeVisible();
  await expect(page.locator('#view-settings')).toBeHidden();
  await page.getByRole('navigation', {name: 'Breadcrumb'}).getByRole('link', {name: 'Slide looks'}).click();
  await expect(page).toHaveURL(/#settings\/looks$/);
  await expect(page.locator('#settings-looks')).toBeVisible();
  await expect(cards(page)).toHaveCount(1);
  await expect(tab(page, 'looks')).toHaveAttribute('aria-current', 'page');
});

test('on a phone the sections are a row of tabs and the page never scrolls sideways', async ({page}) => {
  await page.setViewportSize({width: 375, height: 812});
  for (const section of ['defaults', 'looks', 'ai', 'audio', 'library']) {
    await page.goto(`/#settings/${section}`);
    await expect(page.locator(`#settings-${section}`)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
  }
  const boxes = await page.locator('.settings-nav a').evaluateAll(links => links.map(link => link.getBoundingClientRect().top));
  expect(new Set(boxes.map(Math.round)).size).toBe(1);
  await expect(tab(page, 'library')).toBeInViewport();
});
