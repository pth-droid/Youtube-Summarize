const {test, expect} = require('@playwright/test');

const srt = '1\n00:00:10,000 --> 00:00:15,000\nHeating affects reaction speed.\n\n2\n00:01:20,000 --> 00:01:25,000\nDevelopment time changes aroma.\n';
const crumbs = page => page.getByRole('navigation', {name: 'Breadcrumb'});
const hex = (page, name) => page.getByRole('textbox', {name: `${name} hex code`, exact: true});

test('settings: linked sections, a save bar for unsaved defaults, and look cards that open the look editor', async ({page}) => {
  await page.goto('/#settings');
  await expect(page.locator('#storage-details')).not.toBeEmpty();
  // Five sections, linked beside them; a link scrolls to its section and the address names it.
  await expect(page.locator('.settings-nav a')).toHaveText([/Defaults$/, /Slide looks$/, /AI providers$/, /Transcription$/, /Library and tools$/]);
  await page.locator('.settings-nav a[data-section="audio"]').click();
  await expect(page).toHaveURL(/#settings\/audio$/);
  await expect(page.locator('#settings-audio')).toBeInViewport();
  await expect(page.locator('.settings-nav a[data-section="audio"]')).toHaveClass(/active/);
  // Nothing to save until a default changes, and the save bar can put it back.
  await expect(page.locator('#settings-form')).toBeHidden();
  await page.locator('#transcribe-video').selectOption('groq');
  await expect(page.locator('#settings-form')).toBeVisible();
  await page.getByRole('button', {name: 'Discard', exact: true}).click();
  await expect(page.locator('#settings-form')).toBeHidden();
  await expect(page.locator('#transcribe-video')).toHaveValue('soniox');
  // Looks: seven cards, the default marked, each with its editor a link away.
  const cards = page.locator('#settings-look-grid .look-card');
  await expect(cards).toHaveCount(7);
  await expect(page.locator('input[name="settings-look"][value="forest"]')).toBeChecked();
  await expect(cards.first().locator('.look-default')).toBeVisible();
  await expect(cards.nth(1).locator('.look-default')).toBeHidden();
  await page.getByRole('link', {name: 'Customize Maroon and beige'}).click();
  await expect(page).toHaveURL(/#settings\/looks\/maroon$/);
  await expect(page.getByRole('heading', {name: 'Maroon and beige', level: 1})).toBeVisible();
  await expect(page.locator('.nav-item[data-view="settings"]')).toHaveClass(/active/);
  await crumbs(page).getByRole('link', {name: 'Slide looks'}).click();
  await expect(page).toHaveURL(/#settings\/looks$/);
  await expect(page.locator('#settings-looks')).toBeInViewport();
});

test('look editor: change a look, see how readable it is, preview it on a deck and save it for every deck', async ({page, request}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  // A deck in maroon to preview the look on. Its own words, so the library does not offer another deck.
  const title = `Look editor deck ${Date.now()}`;
  await page.goto('/#new');
  await expect(page.locator('#create-button')).toBeEnabled();
  await page.getByRole('button', {name: 'Lecture slides', exact: true}).click();
  await page.getByRole('button', {name: 'Maroon and beige', exact: true}).click();
  await page.getByRole('button', {name: 'Transcript file', exact: true}).click();
  const words = srt.replace('Heating affects reaction speed.', `Colour carries the room (${title}).`);
  await page.locator('#source-file').setInputFiles({name: 'look.srt', mimeType: 'text/plain', buffer: Buffer.from(words)});
  await page.locator('#import-title').fill(title);
  await page.getByRole('button', {name: 'Create lecture slides'}).click();
  await expect(page.locator('#job-detail')).toContainText('Your lecture slides are ready.', {timeout: 20000});
  const deckId = await page.locator('#job-detail button[data-open]').getAttribute('data-open');
  try {
    await page.goto('/#settings/looks/maroon');
    await expect(page.locator('#look-checks li')).toHaveCount(18);
    await expect(page.locator('#look-save')).toBeDisabled();
    await expect(page.locator('#look-reset')).toBeDisabled();
    await page.locator('#look-preview-source').selectOption(deckId);
    // The deck draws itself in the look, sandboxed like the reader, in the mode being edited.
    const deck = page.frameLocator('#look-frame');
    const deckToken = name => deck.locator('html').evaluate((root, name) => getComputedStyle(root).getPropertyValue(name).trim(), name);
    await expect(deck.locator('html')).toHaveAttribute('data-look', 'maroon');
    await expect(deck.locator('html')).toHaveAttribute('data-theme', 'light');
    // A colour typed as a hex code shows on the deck at once and marks its row.
    await hex(page, 'Accent').fill('#1f4e8c');
    await expect.poll(() => deckToken('--accent')).toBe('#1f4e8c');
    await expect(page.locator('[data-row="accent"]')).toHaveClass(/changed/);
    await expect(page.locator('#look-save')).toBeEnabled();
    await expect(page.locator('#look-lede')).toContainText('unsaved changes');
    // Faint text is called out in words, not colour alone, and the row's button puts the colour back.
    await hex(page, 'Text').fill('#eeeeee');
    await expect(page.locator('.check-row', {hasText: 'Text on the slide'})).toContainText('Too faint');
    await expect(page.locator('#checks-summary')).toContainText('too faint');
    await page.getByRole('button', {name: 'Put text back to the original', exact: true}).click();
    await expect(hex(page, 'Text')).toHaveValue('#2f1418');
    await expect(page.locator('#checks-summary')).toContainText('every pair reads well');
    // Dark keeps its own colours, and the deck follows the editor into dark.
    await page.getByRole('button', {name: '☾ Dark'}).click();
    await expect(hex(page, 'Slide background')).toHaveValue('#2a1217');
    await expect(deck.locator('html')).toHaveAttribute('data-theme', 'dark');
    await hex(page, 'Slide background').fill('#111111');
    await expect.poll(() => deckToken('--surface')).toBe('#111111');
    // Other type reloads the deck with it, so the deck fits its text to the type; colours being tried come back.
    await page.locator('#look-display').selectOption('din');
    await expect.poll(() => deckToken('--display')).toMatch(/^Bahnschrift/);
    await expect.poll(() => deckToken('--surface')).toBe('#111111');
    // Sample slides show the look without a deck.
    await page.locator('#look-preview-source').selectOption('');
    await expect(page.locator('#look-sample .sample-feature')).toHaveCSS('background-color', 'rgb(122, 31, 45)');
    await expect(page.locator('#look-sample .sample-title')).toHaveCSS('background-color', 'rgb(17, 17, 17)');

    await page.getByRole('button', {name: 'Save look'}).click();
    await expect(page.locator('#notice')).toContainText('Maroon and beige is saved');
    await expect(page.locator('#look-save')).toBeDisabled();
    const saved = (await (await request.get('/api/looks')).json()).looks.find(look => look.id === 'maroon');
    expect(saved.changes).toEqual({light: {accent: '#1f4e8c'}, dark: {surface: '#111111'}, display: 'din'});
    // Every deck in the look shows it, decks made before the change included.
    expect(await (await request.get(`/api/generations/${deckId}/page`)).text()).toContain('--accent:#1f4e8c');
    // Settings marks the look as customized, and its card shows the new accent.
    await crumbs(page).getByRole('link', {name: 'Slide looks'}).click();
    const card = page.locator('.look-card', {hasText: 'Maroon and beige'});
    await expect(card.locator('.badge')).toHaveText('Customized');
    await expect(card.locator('.look-preview .eyebrow')).toHaveCSS('background-color', 'rgb(31, 78, 140)');

    // Unsaved changes ask before leaving; staying keeps them.
    await page.getByRole('link', {name: 'Customize Maroon and beige'}).click();
    await hex(page, 'Accent').fill('#000000');
    page.once('dialog', dialog => dialog.dismiss());
    await crumbs(page).getByRole('link', {name: 'Settings', exact: true}).click();
    await expect(page).toHaveURL(/#settings\/looks\/maroon$/);
    await expect(page.locator('#view-look')).toBeVisible();
    await expect(hex(page, 'Accent')).toHaveValue('#000000');
    // Reset to original, then save, puts the look back as designed.
    await page.getByRole('button', {name: 'Reset to original'}).click();
    await expect(hex(page, 'Accent')).toHaveValue('#7a1c2a');
    await page.getByRole('button', {name: 'Save look'}).click();
    await expect(page.locator('#notice')).toContainText('back to its original design');
    expect((await (await request.get('/api/looks')).json()).looks.find(look => look.id === 'maroon').changes).toEqual({});
    expect(errors).toEqual([]);
  } finally {
    // Other browser checks expect maroon as designed, even after a failure.
    await page.evaluate(() => fetch('/api/looks/maroon', {method: 'DELETE', headers: {'x-distill': document.querySelector('meta[name="distill-token"]').content}}));
  }
});
