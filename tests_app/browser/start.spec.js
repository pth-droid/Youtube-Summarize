const {test: base, expect} = require('@playwright/test');

const test = base.extend({
  restorePreferences: [async ({request}, use) => {
    const saved = (await (await request.get('/api/settings')).json()).preferences;
    const html = await (await request.get('/')).text();
    const token = html.match(/name="visual-learning-token" content="([^"]+)"/)[1];
    try { await use(); }
    finally {
      const response = await request.put('/api/settings', {data: saved, headers: {'x-visual-learning': token}});
      expect(response.ok()).toBeTruthy();
    }
  }, {auto: true}],
});

const videoUrl = 'https://www.youtube.com/watch?v=jNQXAC9IVRw';

test('home opens ready for a link and submits saved defaults with Enter', async ({page, request}) => {
  await page.goto('/#settings');
  await expect(page.locator('#create-button')).toBeEnabled();
  await page.locator('#settings-language').selectOption('en');
  await page.locator('#settings-level').selectOption('advanced');
  await page.locator('#settings-provider').selectOption('codex');
  await page.getByRole('button', {name: 'Save preferences', exact: true}).click();
  await expect(page.locator('#notice')).toContainText('Preferences saved');

  await page.goto('/');
  await expect(page.getByRole('heading', {name: 'Learn something new', exact: true})).toBeVisible();
  await expect(page.locator('#view-library')).toBeHidden();
  await expect(page.locator('#video-url')).toBeFocused();
  await expect(page.locator('#create-button')).toBeEnabled();
  await expect(page.locator('#page-options')).not.toHaveAttribute('open');
  await expect(page.locator('#new-language')).toBeHidden();
  await expect(page.locator('#defaults-summary')).toContainText('English');
  await expect(page.locator('#defaults-summary')).toContainText('Advanced');
  await expect(page.locator('#defaults-label')).toHaveText('Using your saved defaults');

  await page.locator('#video-url').fill(videoUrl);
  const sent = page.waitForRequest(req => req.method() === 'POST' && req.url().endsWith('/api/jobs'));
  await page.locator('#video-url').press('Enter');
  const payload = (await sent).postDataJSON();
  expect(payload.preferences).toMatchObject({language: 'en', knowledge_level: 'advanced', provider: 'codex'});
  await expect(page.locator('#view-jobs')).toBeVisible();
  await expect(page.locator('#job-detail')).toContainText('English');
  const jobs = await (await request.get('/api/jobs')).json();
  const job = jobs.jobs.find(item => item.input.url === videoUrl);
  expect(job.input.preferences).toMatchObject({language: 'en', knowledge_level: 'advanced', provider: 'codex'});
  await page.getByRole('button', {name: 'Cancel processing', exact: true}).click();
  await expect(page.locator('#job-detail .job-stage strong')).toHaveText('Cancelled');
});

test('options affect one page and can return to saved defaults', async ({page, request}) => {
  await page.goto('/');
  await expect(page.locator('#create-button')).toBeEnabled();
  const saved = (await (await request.get('/api/settings')).json()).preferences;
  await page.getByText('Options for this page', {exact: true}).click();
  const language = saved.language === 'en' ? 'vi' : 'en';
  await page.locator('#new-language').selectOption(language);
  await page.locator('#learning-goal').fill('Understand the main connections.');
  await expect(page.locator('#defaults-label')).toHaveText('Using options for this page');
  await expect(page.locator('#defaults-summary')).toContainText('Learning goal set');
  const unchanged = (await (await request.get('/api/settings')).json()).preferences;
  expect(unchanged).toEqual(saved);
  await page.getByRole('button', {name: 'Use saved defaults', exact: true}).click();
  await expect(page.locator('#new-language')).toHaveValue(saved.language);
  await expect(page.locator('#learning-goal')).toHaveValue(saved.learning_goal);
  await expect(page.locator('#page-options')).not.toHaveAttribute('open');
  await expect(page.locator('#defaults-label')).toHaveText('Using your saved defaults');

  await page.getByRole('button', {name: 'Edit defaults', exact: true}).click();
  await expect(page.locator('#view-settings')).toBeVisible();
  await page.getByRole('link', {name: 'Visual Learning home', exact: true}).click();
  await expect(page.locator('#view-new')).toBeVisible();
  await expect(page.locator('#video-url')).toBeFocused();
});

test('settings must load before a page can start', async ({page}) => {
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  await page.route('**/api/settings', async route => {
    await pending;
    await route.continue();
  });
  await page.goto('/');
  await expect(page.locator('#view-new')).toBeVisible();
  await expect(page.locator('#create-button')).toBeDisabled();
  await expect(page.locator('#defaults-label')).toContainText('Loading');
  await page.locator('#video-url').fill(videoUrl);
  release();
  await expect(page.locator('#create-button')).toBeEnabled();
  await expect(page.locator('#video-url')).toHaveValue(videoUrl);
});

test('unavailable settings keep the start action disabled', async ({page}) => {
  await page.route('**/api/settings', route => route.fulfill({status: 503, json: {detail: 'Settings unavailable.'}}));
  await page.goto('/');
  await expect(page.locator('#new-error')).toContainText('Refresh the app');
  await expect(page.locator('#create-button')).toBeDisabled();
  await expect(page.locator('#defaults-label')).toHaveText('Saved settings are unavailable');
});

test('API approval stays visible outside the collapsed options', async ({page}) => {
  await page.route('**/api/settings', async route => {
    const response = await route.fetch();
    const settings = await response.json();
    settings.preferences.provider = 'deepseek';
    settings.preferences.allow_paid_llm = false;
    await route.fulfill({json: settings});
  });
  await page.goto('/');
  await expect(page.locator('#create-button')).toBeEnabled();
  await expect(page.locator('#page-options')).not.toHaveAttribute('open');
  await expect(page.locator('#new-paid')).toBeVisible();
  await expect(page.locator('#new-paid')).not.toBeChecked();
  await expect(page.locator('#defaults-summary')).toContainText('DeepSeek');
});

test('saved API approval allows a quick start without another checkbox', async ({page}) => {
  await page.route('**/api/settings', async route => {
    const response = await route.fetch();
    const settings = await response.json();
    settings.preferences.provider = 'deepseek';
    settings.preferences.allow_paid_llm = true;
    await route.fulfill({json: settings});
  });
  await page.goto('/');
  await expect(page.locator('#create-button')).toBeEnabled();
  await expect(page.locator('#new-paid')).toBeHidden();
  await expect(page.locator('#defaults-summary')).toContainText('DeepSeek');
});

test('mobile home keeps the link and start button in view and supports other sources', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('/');
  await expect(page.locator('#create-button')).toBeEnabled();
  await expect(page.locator('#video-url')).toBeInViewport();
  await expect(page.locator('#create-button')).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: '.feasibility/screenshots/start-mobile.png', fullPage: true});
  await page.getByRole('button', {name: 'Transcript file', exact: true}).click();
  await expect(page.locator('#source-file')).toBeVisible();
  await expect(page.locator('#source-file')).toHaveAttribute('required');
  await expect(page.locator('#video-url')).not.toHaveAttribute('required');
  await page.getByRole('button', {name: 'Audio file', exact: true}).click();
  await expect(page.locator('#import-help')).toContainText('approve sending it to Groq');
  await expect(page.locator('#import-url-row')).toBeHidden();
  await page.getByRole('button', {name: 'YouTube link', exact: true}).click();
  await expect(page.locator('#video-url')).toBeVisible();
  await expect(page.locator('#video-url')).toHaveAttribute('required');
  await expect(page.locator('#source-file')).not.toHaveAttribute('required');
  await page.getByRole('button', {name: 'Menu', exact: true}).click();
  await page.locator('.nav-item[data-view="library"]').click();
  await expect(page.locator('#view-library')).toBeVisible();
  await page.getByRole('button', {name: 'New learning page'}).click();
  await expect(page.locator('#view-new')).toBeVisible();
});

test('desktop home and explicit navigation work after reload', async ({page}) => {
  await page.setViewportSize({width: 1440, height: 900});
  await page.goto('/');
  await expect(page.locator('#create-button')).toBeEnabled();
  await expect(page.locator('.nav-item[data-view="new"]')).toHaveClass(/active/);
  await expect(page.locator('#create-button')).toBeInViewport();
  await page.screenshot({path: '.feasibility/screenshots/start-desktop.png', fullPage: true});
  await page.goto('/#library');
  await expect(page.locator('#view-library')).toBeVisible();
  await page.reload();
  await expect(page.locator('#view-library')).toBeVisible();
  await page.goto('/#unknown');
  await expect(page.locator('#view-new')).toBeVisible();
  await page.goto('/');
  await page.reload();
  await expect(page.locator('#view-new')).toBeVisible();
});
