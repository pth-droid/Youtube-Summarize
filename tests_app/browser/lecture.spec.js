const {test, expect} = require('@playwright/test');

const srt = '1\n00:00:10,000 --> 00:00:15,000\nHeating affects reaction speed.\n\n2\n00:01:20,000 --> 00:01:25,000\nDevelopment time changes aroma.\n';

test('lecture slides: choose the output, present and take notes', async ({page, request}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const title = `Roasting lecture ${Date.now()}`;
  await page.goto('/#new');
  // Saved settings set the format when they arrive; choose after they have loaded.
  await expect(page.locator('#create-button')).toBeEnabled();
  await page.getByRole('button', {name: 'Lecture slides', exact: true}).click();
  await expect(page.getByRole('button', {name: 'Lecture slides', exact: true})).toHaveAttribute('aria-pressed', 'true');
  // The format is the first choice, above the source; the saved default carries a tag.
  expect(await page.locator('.make-choice').evaluate(choice => choice.compareDocumentPosition(document.getElementById('new-form')) & Node.DOCUMENT_POSITION_FOLLOWING)).toBeTruthy();
  await expect(page.locator('#make-page-default')).toBeVisible();
  await expect(page.locator('#make-lecture-default')).toBeHidden();
  await expect(page.locator('#defaults-label')).toHaveText('Using options for this page');
  await page.getByRole('button', {name: 'Transcript file', exact: true}).click();
  await page.locator('#source-file').setInputFiles({name: 'roasting.srt', mimeType: 'text/plain', buffer: Buffer.from(srt)});
  await page.locator('#import-title').fill(title);
  await page.getByRole('button', {name: 'Create lecture slides'}).click();
  await expect(page.locator('#job-detail')).toContainText('Your lecture slides are ready.', {timeout: 20000});
  await expect(page.locator('#job-detail .job-source')).toContainText('Lecture slides');
  await page.getByRole('button', {name: 'Present lecture slides'}).click();

  const deck = page.frameLocator('#reader-frame');
  await expect(deck.locator('.slide-frame.is-current')).toContainText(`Lecture: ${title}`);
  const total = await deck.locator('.slide-frame').count();
  expect(total).toBeGreaterThanOrEqual(7);
  await expect(deck.locator('#counter')).toHaveText(`1 / ${total}`);
  // The deck takes focus when it opens; F asks the workspace to put the reader frame in full screen, F again leaves it.
  await expect(deck.locator('#fullscreen-button')).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.activeElement?.id)).toBe('reader-frame');
  await page.keyboard.press('f');
  await expect.poll(() => page.evaluate(() => document.fullscreenElement?.id || null)).toBe('reader-frame');
  await page.keyboard.press('f');
  await expect.poll(() => page.evaluate(() => document.fullscreenElement?.id || null)).toBe(null);
  await deck.locator('#next').click();
  await expect(deck.locator('.slide-frame.is-current')).toContainText('Explain the source model.');
  // A click on the slide moves on, like a presenter remote; the arrow keys go both ways.
  await deck.locator('.slide-frame.is-current .slide h2').click();
  await expect(deck.locator('#counter')).toHaveText(`3 / ${total}`);
  await page.keyboard.press('ArrowLeft');
  await expect(deck.locator('#counter')).toHaveText(`2 / ${total}`);
  await page.keyboard.press('ArrowRight');
  await expect(deck.locator('#counter')).toHaveText(`3 / ${total}`);
  await page.keyboard.press('End');
  await expect(deck.locator('#counter')).toHaveText(`${total} / ${total}`);
  // The deck is presented to a group: it ends with limits and the source, never a quiz.
  await expect(deck.locator('.slide-frame.is-current .slide')).toHaveClass(/kind-limits/);
  await expect(deck.locator('.kind-quiz, .option')).toHaveCount(0);
  // Hidden slides cannot take keyboard focus while one slide is presented.
  expect(await deck.locator('.slide-frame:not(.is-current)').evaluateAll(frames => frames.every(frame => frame.inert))).toBeTruthy();

  await deck.locator('#notes-toggle').click();
  await expect(deck.locator('#notes-toggle')).toHaveAttribute('aria-pressed', 'true');
  await deck.locator('#outline-button').click();
  await deck.locator('#outline').getByRole('button', {name: 'What does the source explain?'}).click();
  const question = deck.locator('.slide-frame.is-current');
  await expect(question.locator('.slide')).toHaveClass(/kind-question/);
  await expect(question.locator('.notes')).toBeVisible();

  // The slide canvas keeps its 16:9 shape inside the workspace frame.
  const box = await deck.locator('.slide-frame.is-current .slide-box').boundingBox();
  expect(Math.abs(box.width / box.height - 16 / 9)).toBeLessThan(0.02);

  await page.locator('.nav-item[data-view="library"]').click();
  const card = page.locator('.page-card').filter({hasText: title});
  await expect(card).toContainText('SLIDES');
  await expect(card.getByRole('button', {name: 'Present'})).toBeVisible();
  const library = await (await request.get('/api/library')).json();
  const lecture = library.generations.find(item => item.title === title);
  const exported = await request.get(`/api/generations/${lecture.id}/export`);
  expect(exported.headers()['content-disposition']).toContain('lecture-slides-');
  expect(errors).toEqual([]);
});

test('lecture slides read as stacked cards on a phone and print one slide per page', async ({page, request}) => {
  const library = await (await request.get('/api/library')).json();
  let lecture = library.generations.find(item => item.metadata?.output_format === 'lecture');
  test.skip(!lecture, 'Runs after the lecture creation test');
  await page.setViewportSize({width: 390, height: 800});
  await page.goto(`/api/generations/${lecture.id}/page`);
  const frames = page.locator('.slide-frame');
  await expect(frames.nth(0)).toBeVisible();
  await expect(frames.nth(1)).toBeVisible();
  await expect(page.locator('.deck-nav')).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.setViewportSize({width: 1280, height: 800});
  await page.emulateMedia({media: 'print'});
  await expect(page.locator('.deck-bar')).toBeHidden();
  const sizes = await frames.evaluateAll(items => items.map(item => item.querySelector('.slide').getBoundingClientRect()).map(rect => [Math.round(rect.width), Math.round(rect.height)]));
  expect(sizes.every(([width, height]) => width === 1280 && height === 720)).toBeTruthy();
  // One printed page per slide, with no trailing blank page.
  const pdf = (await page.pdf({preferCSSPageSize: true, printBackground: true})).toString('latin1');
  expect(pdf.match(/\/Type\s*\/Page[^s]/g).length).toBe(sizes.length);
});

test('share to phone: a phone copy that presents the slide alone, sideways or upright', async ({page, browser, request}) => {
  const library = await (await request.get('/api/library')).json();
  const lecture = library.generations.find(item => item.metadata?.output_format === 'lecture');
  test.skip(!lecture, 'Runs after the lecture creation test');
  await page.goto('/#library');
  await page.locator('.page-card').filter({hasText: lecture.title}).getByRole('button', {name: 'Present'}).click();
  await page.getByRole('button', {name: 'Share to phone'}).click();
  const dialog = page.locator('#share-dialog');
  await expect(dialog).toBeVisible();
  // A tailnet link with its QR code when Tailscale serves this app, otherwise the one command that sets it up.
  await expect(dialog.locator('#share-ready:visible, #share-setup:visible')).toHaveCount(1);
  await expect(dialog.getByRole('link', {name: 'Download phone HTML'})).toHaveAttribute('href', `/api/generations/${lecture.id}/share/download`);
  const download = await request.get(`/api/generations/${lecture.id}/share/download`);
  expect(download.headers()['content-disposition']).toContain('lecture-slides-phone-');
  await dialog.getByRole('button', {name: 'Done'}).click();
  await expect(dialog).toBeHidden();

  // An iPhone 14 Pro held sideways shows 734x343 CSS pixels: below the computer deck's 761px canvas, so the copy forces it.
  const {devices} = require('@playwright/test');
  const sideways = await browser.newContext({...devices['iPhone 14 Pro landscape']});
  const phone = await sideways.newPage();
  const errors = [];
  phone.on('pageerror', error => errors.push(error.message));
  await phone.goto(`/share/${lecture.id}`);
  const total = await phone.locator('.slide-frame').count();
  // Only the slide shows, the full height of the screen; mirroring puts exactly this on the TV.
  await expect(phone.locator('.deck-bar')).toBeHidden();
  await expect(phone.locator('.deck-nav')).toBeHidden();
  const box = await phone.locator('.slide-frame.is-current .slide-box').boundingBox();
  expect(Math.round(box.height)).toBe(343);
  expect(Math.abs(box.width / box.height - 16 / 9)).toBeLessThan(0.02);
  await expect(phone.locator('.rotate-hint')).toBeHidden();
  // A tap moves on, a tap on the left edge goes back; notes never open.
  await phone.mouse.click(600, 170);
  await expect(phone.locator('#counter')).toHaveText(`2 / ${total}`);
  await phone.mouse.click(120, 170);
  await expect(phone.locator('#counter')).toHaveText(`1 / ${total}`);
  await phone.keyboard.press('n');
  await expect(phone.locator('body')).not.toHaveClass(/show-notes/);
  await expect(phone.locator('.notes')).toHaveCount(total);
  await expect(phone.locator('.notes:visible')).toHaveCount(0);
  // The corner button lays the controls over the slide and takes them away again.
  await phone.locator('#controls-toggle').click();
  await expect(phone.locator('#controls-toggle')).toHaveAttribute('aria-expanded', 'true');
  await expect(phone.locator('.deck-bar')).toBeVisible();
  await expect(phone.locator('#outline-button')).toBeVisible();
  await expect(phone.locator('#notes-toggle')).toBeHidden();
  await phone.locator('#controls-toggle').click();
  await expect(phone.locator('.deck-nav')).toBeHidden();
  expect(errors).toEqual([]);
  await sideways.close();

  // Upright, the slide keeps its shape across the width and asks to turn the phone.
  const upright = await browser.newContext({...devices['iPhone 14 Pro']});
  const portrait = await upright.newPage();
  await portrait.goto(`/share/${lecture.id}`);
  await expect(portrait.locator('.rotate-hint')).toBeVisible();
  const narrow = await portrait.locator('.slide-frame.is-current .slide-box').boundingBox();
  expect(Math.round(narrow.width)).toBe(393);
  await upright.close();
});

test('slide look: choose maroon and beige on the start view, and keep a default in settings', async ({page}) => {
  const title = `Maroon lecture ${Date.now()}`;
  await page.goto('/#new');
  await expect(page.locator('#create-button')).toBeEnabled();
  try {
    // Only slides have a look; it sits under the format cards and starts from the saved default.
    await expect(page.locator('#look-row')).toBeHidden();
    await page.getByRole('button', {name: 'Lecture slides', exact: true}).click();
    await expect(page.locator('#look-row')).toBeVisible();
    const forest = page.getByRole('button', {name: 'Forest green', exact: true});
    const maroon = page.getByRole('button', {name: 'Maroon and beige', exact: true});
    await expect(forest).toHaveAttribute('aria-pressed', 'true');
    // Seven looks, each a small slide in its own light colours, named with what it suits.
    await expect(page.locator('#look-options .look-option')).toHaveCount(7);
    await expect(page.getByRole('button', {name: 'High contrast', exact: true})).toHaveAccessibleDescription('Bright rooms, weak projectors');
    await expect(page.locator('[data-look="navy"] .look-preview')).toHaveCSS('background-color', 'rgb(252, 250, 245)');
    await expect(page.locator('[data-look="navy"] .look-preview .feature')).toHaveCSS('background-color', 'rgb(23, 42, 79)');
    await maroon.click();
    await expect(maroon).toHaveAttribute('aria-pressed', 'true');
    await expect(forest).toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('#defaults-summary')).toContainText('Maroon and beige slides');
    await page.getByRole('button', {name: 'Transcript file', exact: true}).click();
    // Its own words, so the library does not offer the deck made by the first test.
    const words = srt.replace('Heating affects reaction speed.', `Heat moves into the beans (${title}).`);
    await page.locator('#source-file').setInputFiles({name: 'maroon.srt', mimeType: 'text/plain', buffer: Buffer.from(words)});
    await page.locator('#import-title').fill(title);
    await page.getByRole('button', {name: 'Create lecture slides'}).click();
    await expect(page.locator('#job-detail')).toContainText('Your lecture slides are ready.', {timeout: 20000});
    await expect(page.locator('#job-detail .job-source')).toContainText('Lecture slides · Maroon and beige');
    await page.getByRole('button', {name: 'Present lecture slides'}).click();

    const deck = page.frameLocator('#reader-frame');
    await expect(deck.locator('html')).toHaveAttribute('data-look', 'maroon');
    await expect(deck.locator('.slide-frame.is-current .slide')).toHaveClass(/kind-title/);
    // The title's composition rotates with the deck, so the look is checked through its tokens and the deck bar.
    const token = name => deck.locator('html').evaluate((root, name) => getComputedStyle(root).getPropertyValue(name).trim(), name);
    // Maroon follows the Lighthouse brand, set in Bricolage Grotesque, which the deck carries inside itself.
    await expect(deck.locator('.slide-frame.is-current h1, .slide-frame.is-current h2').first()).toHaveCSS('font-family', /^"Bricolage Grotesque"/);
    expect(await deck.locator('html').evaluate(() => document.fonts.check('600 40px "Bricolage Grotesque"', 'Pha cà phê'))).toBe(true);
    // Dark mode: the brand's warm dark tone, deep maroon with cream text; filled slides in the brand's maroon.
    await expect(deck.locator('.deck-bar')).toHaveCSS('background-color', 'rgb(40, 17, 15)');
    expect(await token('--feature')).toBe('#7b131b');
    expect(await token('--ink')).toBe('#f5edd8');
    // Light mode: antique cream, ruby accents and warm slate secondary text.
    await deck.locator('#theme-toggle').click();
    await expect(deck.locator('.deck-bar')).toHaveCSS('background-color', 'rgb(250, 246, 238)');
    expect(await token('--accent')).toBe('#a21c21');
    await expect(deck.locator('.deck-title')).toHaveCSS('color', 'rgb(98, 86, 80)');

    // A saved default look starts the choice on the next visit.
    await page.goto('/#settings');
    await expect(page.locator('#storage-details')).not.toBeEmpty();
    await expect(page.locator('input[name="settings-look"][value="forest"]')).toBeChecked();
    await expect(page.locator('#settings-look-grid .look-card')).toHaveCount(7);
    await page.locator('#settings-look-grid label', {hasText: 'Maroon and beige'}).click();
    await page.getByRole('button', {name: 'Save preferences'}).click();
    await expect(page.locator('#notice')).toContainText('Preferences saved');
    await page.reload();
    await expect(page.locator('#storage-details')).not.toBeEmpty();
    await expect(page.locator('input[name="settings-look"][value="maroon"]')).toBeChecked();
    await page.locator('.nav-item[data-view="new"]').click();
    await page.getByRole('button', {name: 'Lecture slides', exact: true}).click();
    await expect(maroon).toHaveAttribute('aria-pressed', 'true');
  } finally {
    // Restore the look that other browser checks expect, even after a failure.
    await page.evaluate(() => fetch('/api/settings', {method: 'PUT', headers: {'x-distill': document.querySelector('meta[name="distill-token"]').content, 'Content-Type': 'application/json'},
      body: JSON.stringify({slide_theme: 'forest'})}));
  }
});

test('settings choose a transcription service for each kind of recording', async ({page}) => {
  await page.goto('/#settings');
  // Wait for saved settings; they replace the form's initial values when they arrive.
  await expect(page.locator('#storage-details')).not.toBeEmpty();
  try {
    await expect(page.locator('#transcribe-meeting')).toHaveValue('soniox');
    await expect(page.locator('#transcribe-lecture')).toHaveValue('soniox');
    await expect(page.locator('#transcribe-video')).toHaveValue('soniox');
    // The downloader reports its version without asking PyPI until Check for update is selected.
    await expect(page.locator('#ytdlp-status')).toContainText(/^yt-dlp \d{4}\./);
    await page.locator('#transcribe-lecture').selectOption('groq');
    await page.locator('label', {has: page.locator('input[name="settings-output"][value="lecture"]')}).click();
    await page.getByRole('button', {name: 'Save preferences'}).click();
    await expect(page.locator('#notice')).toContainText('Preferences saved');
    await page.reload();
    await expect(page.locator('#storage-details')).not.toBeEmpty();
    await expect(page.locator('#transcribe-lecture')).toHaveValue('groq');
    await expect(page.locator('#transcribe-meeting')).toHaveValue('soniox');
    await expect(page.locator('input[name="settings-output"][value="lecture"]')).toBeChecked();

    await page.locator('.nav-item[data-view="new"]').click();
    await expect(page.getByRole('button', {name: 'Create lecture slides'})).toBeVisible();
    await expect(page.locator('#make-lecture-default')).toBeVisible();
    await expect(page.locator('#make-page-default')).toBeHidden();
    await page.getByRole('button', {name: 'Audio file', exact: true}).click();
    await expect(page.locator('#recording-row')).toBeVisible();
    await expect(page.locator('#import-help')).toContainText('approve sending it to Soniox');
    await page.getByRole('button', {name: 'Lecture or talk', exact: true}).click();
    await expect(page.locator('#import-help')).toContainText('approve sending it to Groq');
    await page.locator('#source-file').setInputFiles({name: 'talk.wav', mimeType: 'audio/wav', buffer: Buffer.from('AUTHORED TEST NOT REAL AUDIO')});
    await page.getByRole('button', {name: 'Create lecture slides'}).click();
    await expect(page.locator('#job-detail')).toContainText('Lecture or talk · set in Settings');
    await expect(page.locator('#job-detail')).toContainText('Continue with Groq');
  } finally {
    // Restore the defaults that other browser checks expect, even after a failure.
    await page.evaluate(() => fetch('/api/settings', {method: 'PUT', headers: {'x-distill': document.querySelector('meta[name="distill-token"]').content, 'Content-Type': 'application/json'},
      body: JSON.stringify({output_format: 'page', transcription_providers: {video: 'soniox', meeting: 'soniox', lecture: 'soniox'}})}));
  }
});
