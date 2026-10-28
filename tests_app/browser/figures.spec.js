const {test, expect} = require('@playwright/test');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

const fixture = name => pathToFileURL(path.resolve(`.feasibility/figure-fixtures/${name}.html`)).href;
// An authored Artisan profile: a Python literal with seconds in timex, ET in temp1 and BT in temp2.
const times = Array.from({length: 111}, (_, k) => k * 6);
const bean = times.map(t => t < 90 ? +(200 - t * 1.2).toFixed(1) : +(92 + (t - 90) * .21).toFixed(1));
const alog = `{'mode': 'C', 'title': u'Authored test roast', 'timex': [${times.join(', ')}], 'temp1': [${times.map(t => 230 - t * .02).join(', ')}], `
  + `'temp2': [${bean.join(', ')}], 'timeindex': [0, 45, 90, 0, 0, 0, 110, 0], 'flavors': (5.0, 5.0), 'roastertype': None, 'heavyFC': False}`;
const artisanCsv = 'Date:27.10.2026\tUnit:C\tCHARGE:00:00\tTP:01:30\tDRYe:04:30\tFCs:09:00\tFCe:\tSCs:\tSCe:\tDROP:11:00\tCOOL:\tTime:11:00\n'
  + 'Time1\tTime2\tET\tBT\tEvent\n' + times.map((t, k) => `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}\t${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}\t${230 - t * .02}\t${bean[k]}\t`).join('\n');

// Range inputs cannot be typed into; set the value and announce it as a person's drag would.
const scrubTo = (locator, value) => locator.evaluate((input, to) => { input.value = to; input.dispatchEvent(new Event('input', {bubbles: true})); }, String(value));

function watch(page, context) {
  const problems = [];
  page.on('pageerror', error => problems.push(error.message));
  page.on('request', request => { if (/^https?:/.test(request.url())) problems.push(`remote request ${request.url()}`); });
  return context.setOffline(true).then(() => problems);
}

test.beforeAll(() => {
  execFileSync(path.resolve('.venv/Scripts/python.exe'), ['-m', 'tests_app.figure_fixture'], {stdio: 'pipe'});
});

test('process figure: one scrubber moves the curves, phases and bean states', async ({page, context}) => {
  const problems = await watch(page, context);
  await page.goto(fixture('roast'));
  // Figures follow the learning views and join the view menu.
  await expect(page.locator('#visuals > .figure-section')).toHaveCount(4);
  await expect(page.locator('#visuals > .visual-section').nth(1)).toHaveId('figure-1');
  await expect(page.locator('#view-nav a[href="#figure-2"]')).toHaveText('Nhiệt và gió đi qua máy rang trống');
  const figure = page.locator('#figure-1');
  await expect(figure.locator('.fig-chart svg')).toBeVisible();
  await expect(figure.locator('.fig-dot')).toHaveCount(4);  // only the four values the source states
  await expect(figure.locator('.fig-chart')).toContainText('Hình dáng minh họa · không phải số liệu thật');
  await expect(figure.locator('.fig-key-row')).toContainText('Chấm: số liệu nguồn nêu');

  await figure.getByRole('button', {name: 'Phát triển', exact: true}).click();
  await expect(figure.getByRole('button', {name: 'Phát triển', exact: true})).toHaveAttribute('aria-pressed', 'true');
  await expect(figure.locator('.fig-state[data-phase="development"]')).toHaveClass(/is-current/);
  await expect(figure.locator('.fig-readout')).toContainText('Phát triển — Sau nứt lần 1 hạt nở');
  await scrubTo(figure.locator('.fig-scrubber'), 540);
  await expect(figure.locator('.fig-readout')).toContainText('9:00');
  await expect(figure.locator('.fig-readout')).toContainText('Nhiệt độ hạt 196 °C (theo nguồn)');
  await scrubTo(figure.locator('.fig-scrubber'), 200);
  await expect(figure.locator('.fig-state[data-phase="drying"]')).toHaveClass(/is-current/);
  await expect(figure.locator('.fig-readout')).not.toContainText('°C');  // between stated values the readout shows none
  await figure.getByRole('button', {name: 'Chạy'}).click();
  await expect(figure.locator('.fig-play')).toHaveAttribute('aria-pressed', 'true');
  await figure.locator('.fig-play').click();
  await expect(figure.locator('.fig-play')).toHaveText('Chạy');

  await figure.locator('.fig-table summary').click();
  await expect(figure.locator('.fig-data').first()).toContainText('Độ ẩm giảm từ khoảng 11% xuống gần 2%');
  await expect(figure.locator('.fig-data').nth(2)).toContainText('196');
  await figure.getByRole('button', {name: 'Giai đoạn sấy', exact: true}).click();
  await expect(page.locator('#detail-content h2')).toHaveText('Giai đoạn sấy');
  await expect(page.locator('#selected-evidence blockquote')).toContainText('11 percent');

  // Theme tokens: the same series uses the validated light and dark steps.
  const fill = () => figure.locator('.fig-dot').first().evaluate(dot => getComputedStyle(dot).fill);
  await page.evaluate(() => { document.documentElement.dataset.theme = 'dark'; });
  expect(await fill()).toBe('rgb(20, 160, 142)');
  await page.evaluate(() => { document.documentElement.dataset.theme = 'light'; });
  expect(await fill()).toBe('rgb(0, 137, 123)');
  await page.setViewportSize({width: 390, height: 844});
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await expect(figure.locator('.fig-chart svg')).toBeVisible();
  expect(problems).toEqual([]);
});

test('a roast log is read in the browser and overlaid without upload', async ({page, context}) => {
  const problems = await watch(page, context);
  await page.goto(fixture('roast'));
  const figure = page.locator('#figure-1'), file = figure.locator('.fig-log-file');
  await expect(figure.locator('.fig-log')).toHaveText('So với log rang của bạn');
  await file.setInputFiles({name: 'test.alog', mimeType: 'text/plain', buffer: Buffer.from(alog)});
  await expect(figure.locator('.fig-log-status')).toContainText('test.alog: BT của bạn, ET của bạn, RoR của bạn (tính từ BT). Chỉ đọc trong trình duyệt này');
  await expect(figure.locator('.fig-key-row')).toContainText('RoR của bạn (tính từ BT) (°C/min)');
  await expect(figure.locator('.fig-chart')).toContainText('Kết thúc sấy');
  await expect(figure.locator('.fig-chart svg text', {hasText: '°C/min'})).toHaveCount(1);  // one panel per unit, no second y-axis
  await scrubTo(figure.locator('.fig-scrubber'), 300);
  await expect(figure.locator('.fig-readout')).toContainText('BT của bạn 136 °C · ET của bạn 224 °C · RoR của bạn (tính từ BT) 12,6 °C/min');
  await figure.getByRole('button', {name: 'Bỏ log'}).click();
  await expect(figure.locator('.fig-key-row')).not.toContainText('BT của bạn');

  await file.setInputFiles({name: 'artisan.csv', mimeType: 'text/csv', buffer: Buffer.from(artisanCsv)});
  await expect(figure.locator('.fig-log-status')).toContainText('artisan.csv: ET của bạn, BT của bạn');
  await expect(figure.locator('.fig-chart')).toContainText('Nứt lần 1');
  await figure.getByRole('button', {name: 'Bỏ log'}).click();
  await file.setInputFiles({name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('Just some notes')});
  await expect(figure.locator('.fig-log-status')).toContainText('Không đọc được tệp này');
  expect(problems).toEqual([]);
});

test('apparatus layers and parts, and what-if levers follow the stated directions', async ({page, context}) => {
  const problems = await watch(page, context);
  await page.goto(fixture('roast'));
  const roaster = page.locator('#figure-2');
  await expect(roaster.locator('.flow')).toHaveCount(6);
  await roaster.getByRole('button', {name: 'Bức xạ'}).click();
  await expect(roaster.getByRole('button', {name: 'Bức xạ'})).toHaveAttribute('aria-pressed', 'false');
  await expect(roaster.locator('.flow-radiation')).toBeHidden();
  await roaster.getByRole('button', {name: 'Bức xạ'}).click();
  await expect(roaster.locator('.flow-radiation')).toBeVisible();
  await roaster.getByRole('button', {name: 'Dừng chuyển động'}).click();
  await expect(roaster.locator('.figure')).toHaveClass(/paused/);
  await roaster.locator('.ap-callout[data-slot="radiant_element"]').click();
  await expect(roaster.locator('.fig-parts li[data-slot="radiant_element"]')).toHaveClass(/active/);
  await expect(roaster.locator('.ap-svg')).toHaveAttribute('role', 'img');

  const levers = page.locator('#figure-3');
  await expect(levers.locator('.fig-link')).toHaveCount(5);
  await levers.locator('[data-lever="airflow"] [data-sign="1"]').click();
  await expect(levers.locator('[data-node="ror"]')).toHaveAttribute('data-state', 'up');
  await expect(levers.locator('[data-node="first_crack_time"]')).toHaveAttribute('data-state', 'down');
  await expect(levers.locator('.fig-announce')).toContainText('Gió tăng');
  await levers.locator('[data-lever="gas"] [data-sign="-1"]').click();
  await expect(levers.locator('[data-node="ror"] .fig-node-state')).toHaveText('↕ tùy tác động nào mạnh hơn');
  await levers.getByRole('button', {name: 'Đặt lại'}).click();
  await expect(levers.locator('[data-node="ror"]')).toHaveAttribute('data-state', '');
  await levers.locator('[data-node="ror"]').click();
  await expect(page.locator('#detail-content h2')).toHaveText('Tốc độ tăng nhiệt (RoR)');
  expect(problems).toEqual([]);
});

test('extraction figures: particle states, espresso flows and a control chart', async ({page, context}) => {
  const problems = await watch(page, context);
  await page.goto(fixture('extraction'));
  const shot = page.locator('#figure-1');
  await expect(shot.locator('.fig-log')).toHaveText('So với log chiết của bạn');
  await expect(shot.locator('.glyph-grounds')).toHaveCount(2);
  await expect(shot.locator('.fig-badges')).toContainText('Số liệu tham khảo, không có trong nguồn');
  await expect(page.locator('#figure-2 .flow-pressure')).toHaveCount(1);
  const chart = page.locator('#figure-3');
  await expect(chart.locator('.fig-region')).toHaveCount(3);
  await expect(chart.locator('.fig-chart')).toContainText('1,2');  // Vietnamese decimal comma
  await chart.getByRole('button', {name: '2 Chiết thiếu'}).click();
  await expect(chart.locator('.fig-region').nth(1)).toHaveClass(/active/);
  expect(problems).toEqual([]);
});

test('figure slides present, keep their own arrow keys and print one slide per page', async ({page, context}) => {
  const problems = await watch(page, context);
  await page.setViewportSize({width: 1366, height: 800});
  await page.goto(fixture('roast-deck'));
  const kinds = await page.locator('.slide').evaluateAll(slides => slides.map(slide => slide.classList.contains('kind-figure')));
  const first = kinds.indexOf(true) + 1;
  expect(kinds.filter(Boolean)).toHaveLength(5);
  await page.goto(fixture('roast-deck') + `#slide-${first}`);
  const slide = page.locator('.slide-frame.is-current');
  await expect(slide.locator('.fig-chart svg')).toBeVisible();
  const scrubber = slide.locator('.fig-scrubber');
  await scrubber.focus();
  await page.keyboard.press('End');
  await expect(page.locator('#counter')).toHaveText(`${first} / ${kinds.length}`);  // the scrubber kept the key
  await expect(slide.locator('.fig-readout')).toContainText('Phát triển');
  // Nothing overflows the canvas: the readout ends above the footer.
  const [readout, footer] = await Promise.all([slide.locator('.fig-readout').boundingBox(), slide.locator('.slide-foot').boundingBox()]);
  expect(readout.y + readout.height).toBeLessThanOrEqual(footer.y + 1);
  await page.locator('#next').click();
  const states = page.locator('.slide-frame.is-current');
  await expect(states.locator('.fig-state[data-phase="development"]')).toHaveClass(/is-current/);
  await expect(states.locator('.fig-compounds td[data-phase="development"]').first()).toHaveClass(/is-current/);
  await page.emulateMedia({media: 'print'});
  const pdf = (await page.pdf({preferCSSPageSize: true, printBackground: true})).toString('latin1');
  expect(pdf.match(/\/Type\s*\/Page[^s]/g).length).toBe(kinds.length);
  expect(problems).toEqual([]);
});

test('deck builds: a click, a wheel notch or a key reveals the next point before the next slide', async ({page, context}) => {
  const problems = await watch(page, context);
  await page.setViewportSize({width: 1366, height: 800});
  await page.goto(fixture('roast-deck'));
  const titles = await page.locator('.slide-frame').evaluateAll(frames => frames.map(frame => frame.getAttribute('aria-label')));
  const total = titles.length, at = titles.findIndex(title => title.includes('Nhiệt đến hạt theo ba đường')) + 1;
  await page.goto(fixture('roast-deck') + `#slide-${at}`);
  const counter = page.locator('#counter');
  // Whatever layout the slide draws, its content parts carry data-part in reading order.
  const rows = page.locator('.slide-frame.is-current .slide-content [data-part]');
  await expect(rows).toHaveCount(3);
  // The first point arrives with the slide; the others wait in place, invisible.
  await expect(rows.nth(0)).not.toHaveClass(/build-pending/);
  await expect(rows.nth(1)).toHaveClass(/build-pending/);
  await expect(rows.nth(1)).toHaveCSS('opacity', '0');
  await page.locator('.slide-frame.is-current .slide h2').click();
  // A click during the arrival finishes it first: the first point is whole before the second rises.
  expect(await rows.nth(0).evaluate(row => getComputedStyle(row).opacity)).toBe('1');
  await expect(rows.nth(1)).toHaveClass(/build-shown/);
  // One wheel gesture is one step: the second notch of the same burst is ignored.
  await page.mouse.move(683, 380);
  await page.mouse.wheel(0, 100);
  await page.mouse.wheel(0, 100);
  await expect(rows.nth(2)).toHaveClass(/build-shown/);
  await expect(counter).toHaveText(`${at} / ${total}`);
  await page.waitForTimeout(400);
  await page.mouse.wheel(0, 100);
  await expect(counter).toHaveText(`${at + 1} / ${total}`);
  // Clicks inside a figure keep their own meaning.
  await page.locator('.slide-frame.is-current .fig-chart svg').click();
  await expect(counter).toHaveText(`${at + 1} / ${total}`);
  // Back arrives fully built, then each step back hides one point, then the slide before.
  await page.keyboard.press('ArrowLeft');
  await expect(counter).toHaveText(`${at} / ${total}`);
  await expect(page.locator('.slide-frame.is-current .build-pending')).toHaveCount(0);
  await page.keyboard.press('PageUp');
  await expect(rows.nth(2)).toHaveClass(/build-pending/);
  await page.keyboard.press('PageUp');
  await expect(rows.nth(1)).toHaveClass(/build-pending/);
  await page.keyboard.press('PageUp');
  await expect(counter).toHaveText(`${at - 1} / ${total}`);
  await page.keyboard.press('PageDown');
  await expect(counter).toHaveText(`${at} / ${total}`);
  // A printed deck shows every point.
  await page.emulateMedia({media: 'print'});
  await expect(rows.nth(2)).toHaveCSS('opacity', '1');
  await page.emulateMedia({media: 'screen'});
  // B blanks the room's screen, as a remote's pause button does; the next key only brings the slide back.
  await page.keyboard.press('b');
  await expect(page.locator('body')).toHaveClass(/blanked/);
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('body')).not.toHaveClass(/blanked/);
  await expect(counter).toHaveText(`${at} / ${total}`);
  // Shift skips the remaining build steps; End arrives fully built.
  await page.keyboard.press('Shift+ArrowRight');
  await expect(counter).toHaveText(`${at + 1} / ${total}`);
  await page.keyboard.press('End');
  await expect(counter).toHaveText(`${total} / ${total}`);
  await expect(page.locator('.slide-frame.is-current .build-pending')).toHaveCount(0);
  expect(problems).toEqual([]);
});

test('figures work inside the app reader under its sandbox policy', async ({page}) => {
  const problems = [];
  page.on('pageerror', error => problems.push(error.message));
  page.on('console', message => { if (message.type() === 'error') problems.push(message.text()); });
  await page.goto('/#library');
  await page.locator('.page-card').filter({hasText: 'Coffee process figures'}).getByRole('button', {name: 'Explore'}).click();
  const reader = page.frameLocator('#reader-frame');
  const figure = reader.locator('#figure-1');
  await expect(figure.locator('.fig-chart svg')).toBeVisible();
  await figure.getByRole('button', {name: 'Maillard', exact: true}).click();
  await expect(figure.locator('.fig-state[data-phase="maillard"]')).toHaveClass(/is-current/);
  await expect(reader.locator('#figure-2 .flow')).toHaveCount(6);
  await reader.locator('#figure-3 [data-lever="gas"] [data-sign="1"]').click();
  await expect(reader.locator('#figure-3 [data-node="ror"]')).toHaveAttribute('data-state', 'up');
  await figure.locator('.fig-log-file').setInputFiles({name: 'test.alog', mimeType: 'text/plain', buffer: Buffer.from(alog)});
  await expect(figure.locator('.fig-log-status')).toContainText('test.alog');
  expect(problems).toEqual([]);
});
