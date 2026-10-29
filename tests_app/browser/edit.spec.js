const {test, expect} = require('@playwright/test');

const srt = '1\n00:00:10,000 --> 00:00:15,000\nHeating affects reaction speed.\n\n2\n00:01:20,000 --> 00:01:25,000\nDevelopment time changes aroma.\n';

test('edit slides: change text in place, keep the deck keys out of it, and save it into the deck', async ({page}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const title = `Edit deck ${Date.now()}`;
  await page.goto('/#new');
  await expect(page.locator('#create-button')).toBeEnabled();
  await page.getByRole('button', {name: 'Lecture slides', exact: true}).click();
  await page.getByRole('button', {name: 'Transcript file', exact: true}).click();
  await page.locator('#source-file').setInputFiles({name: 'edit.srt', mimeType: 'text/plain', buffer: Buffer.from(srt.replace('Heating', `Heating (${title})`))});
  await page.locator('#import-title').fill(title);
  await page.getByRole('button', {name: 'Create lecture slides'}).click();
  await expect(page.locator('#job-detail')).toContainText('Your lecture slides are ready.', {timeout: 20000});
  await page.getByRole('button', {name: 'Present lecture slides'}).click();

  const deck = page.frameLocator('#reader-frame');
  const status = page.locator('#edit-status'), save = page.getByRole('button', {name: 'Save changes'});
  await deck.locator('#next').click();
  await expect(deck.locator('#counter')).toHaveText(/^2 \//);
  await page.getByRole('button', {name: 'Edit slides'}).click();
  // Edit mode opens at the slide in view; Share and Export wait until it ends.
  await expect(deck.locator('html')).toHaveClass(/editing/);
  await expect(deck.locator('#counter')).toHaveText(/^2 \//);
  await expect(page.locator('#reader-export')).toBeHidden();
  await expect(page.locator('#reader-share')).toBeHidden();
  await expect(status).toHaveText('Click a text on a slide to change it. Presenter notes are under each slide.');
  await expect(save).toBeDisabled();

  // Typing goes into the text: space and arrows do not move the deck, and a click does not advance it.
  const objective = deck.locator('[data-field="objectives.0"]');
  await objective.click();
  await page.keyboard.press('End');
  await page.keyboard.type(' Then apply it.');
  await page.keyboard.press('ArrowRight');
  await expect(deck.locator('#counter')).toHaveText(/^2 \//);
  await expect(objective).toHaveText('Explain the source model. Then apply it.');
  await expect(objective).toHaveClass(/edited/);
  await expect(status).toHaveText('1 change not saved yet.');
  await expect(save).toBeEnabled();

  // An emptied text names its slide and cannot be saved; Esc puts it back.
  const second = deck.locator('[data-field="objectives.1"]');
  await second.fill('');
  await expect(status).toHaveText('Slide 2: a text is empty. Type it, or press Esc in it to put it back.');
  await expect(save).toBeDisabled();
  await second.press('Escape');
  await expect(second).toHaveText('Identify its evidence.');
  await expect(status).toHaveText('1 change not saved yet.');

  // Presenter notes show in edit mode and are text to edit too.
  await deck.locator('#next').click();
  await deck.locator('#next').click();
  await expect(deck.locator('#counter')).toHaveText(/^4 \//);
  const notes = deck.locator('.slide-frame.is-current [data-field$=".notes"]');
  await expect(notes).toBeVisible();
  await notes.fill('Say this first.');
  await expect(status).toHaveText('2 changes not saved yet.');

  await save.click();
  await expect(page.locator('#notice')).toHaveText('Slide text saved.');
  // The deck is drawn again with the changes, at the slide being edited, and edit mode has ended.
  await expect(page.locator('#edit-bar')).toBeHidden();
  await expect(page.locator('#reader-export')).toBeVisible();
  await expect(deck.locator('html')).not.toHaveClass(/editing/);
  await expect(deck.locator('#counter')).toHaveText(/^4 \//);
  await expect(deck.locator('.slide-frame').nth(1)).toContainText('Explain the source model. Then apply it.');
  await expect(deck.locator('.slide-frame').nth(3).locator('.notes')).toContainText('Say this first.');
  await expect(deck.locator('[data-field]')).toHaveCount(0);

  // Unsaved changes ask before they are dropped; staying keeps them.
  await page.getByRole('button', {name: 'Edit slides'}).click();
  const heading = deck.locator('.slide-frame.is-current h2 [data-field]');
  const before = await heading.textContent();
  await heading.fill('A title that is not kept');
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('button', {name: 'Cancel', exact: true}).click();
  await expect(page.locator('#edit-bar')).toBeVisible();
  await expect(heading).toHaveText('A title that is not kept');
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', {name: '← Library'}).click();
  await expect(page).toHaveURL(/#library$/);
  await page.locator('.page-card', {hasText: title}).getByRole('button', {name: /Present|Open/}).first().click();
  await expect(page.frameLocator('#reader-frame').locator('.slide-frame').nth(3)).toContainText(before);
  expect(errors).toEqual([]);
});
