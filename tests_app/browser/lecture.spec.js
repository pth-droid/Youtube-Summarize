const {test, expect} = require('@playwright/test');

const srt = '1\n00:00:10,000 --> 00:00:15,000\nHeating affects reaction speed.\n\n2\n00:01:20,000 --> 00:01:25,000\nDevelopment time changes aroma.\n';

test('lecture slides: choose the output, present, take notes and answer the quiz', async ({page, request}) => {
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
  await deck.locator('#next').click();
  await expect(deck.locator('.slide-frame.is-current')).toContainText('Explain the source model.');
  await deck.locator('.slide-frame.is-current').click();
  await page.keyboard.press('ArrowRight');
  await expect(deck.locator('#counter')).toHaveText(`3 / ${total}`);
  await page.keyboard.press('End');
  await expect(deck.locator('#counter')).toHaveText(`${total} / ${total}`);
  // Hidden slides cannot take keyboard focus while one slide is presented.
  expect(await deck.locator('.slide-frame:not(.is-current)').evaluateAll(frames => frames.every(frame => frame.inert))).toBeTruthy();

  await deck.locator('#notes-toggle').click();
  await expect(deck.locator('#notes-toggle')).toHaveAttribute('aria-pressed', 'true');
  await deck.locator('#outline-button').click();
  // The fixture's central question and quiz question share wording; the quiz comes last.
  await deck.locator('#outline').getByRole('button', {name: 'What does the source explain?'}).last().click();
  const quiz = deck.locator('.slide-frame.is-current');
  await expect(quiz.locator('.notes')).toBeVisible();
  await expect(quiz.locator('.answer')).toBeHidden();
  await quiz.getByRole('button', {name: /An unrelated topic/}).click();
  await expect(quiz.locator('.option.wrong')).toContainText('An unrelated topic');
  await expect(quiz.locator('.option.right')).toContainText('How its ideas connect');
  await expect(quiz.locator('.answer')).toBeVisible();

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
    await page.locator('#settings-output').selectOption('lecture');
    await page.getByRole('button', {name: 'Save preferences'}).click();
    await expect(page.locator('#notice')).toContainText('Preferences saved');
    await page.reload();
    await expect(page.locator('#storage-details')).not.toBeEmpty();
    await expect(page.locator('#transcribe-lecture')).toHaveValue('groq');
    await expect(page.locator('#transcribe-meeting')).toHaveValue('soniox');
    await expect(page.locator('#settings-output')).toHaveValue('lecture');

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
