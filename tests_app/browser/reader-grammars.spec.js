const {test, expect} = require('@playwright/test');
const {execFileSync} = require('node:child_process');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const grammars = ['concept_map','causal_graph','process','argument_map','hierarchy','comparison','timeline'];

test.beforeAll(() => {
  execFileSync(path.resolve('.venv/Scripts/python.exe'), ['-m','tests_app.grammar_fixture'], {stdio:'pipe'});
});

for(const grammar of grammars) {
  test(`${grammar} preserves readable source navigation offline`, async ({page,context}) => {
    const errors=[], remote=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',request=>{if(/^https?:/.test(request.url()))remote.push(request.url());});
    await context.setOffline(true);
    await page.goto(pathToFileURL(path.resolve(`.feasibility/grammar-fixtures/${grammar}.html`)).href);
    await expect(page.locator('#source-browser')).not.toHaveAttribute('open', '');
    await expect(page.locator('#transcript-list')).not.toBeVisible();
    const view=page.locator('[data-visual-type]');
    await expect(view).toHaveAttribute('data-visual-type',grammar);
    await expect(view.getByRole('heading',{level:2})).toBeVisible();
    if(grammar!=='comparison'){
      await view.locator('.idea-card .inline-citation').first().click();
      await expect(page.locator('.source-row.highlight').first()).toBeVisible();
      await page.locator('#source-browser > summary').click();
    }
    if(grammar==='causal_graph') {
      await expect(view.locator('svg path[marker-end]')).toHaveCount(1);
      await expect(view.locator('.relationship-button')).toContainText('increases reaction speed');
    }
    if(grammar==='process')expect(await view.locator('.process-flow [data-unit-id]').evaluateAll(nodes=>nodes.map(n=>n.dataset.unitId))).toEqual(['u1','u4']);
    if(grammar==='hierarchy')await expect(view.locator('.hierarchy-tree .hierarchy-tree [data-unit-id="example"]')).toBeVisible();
    if(grammar==='argument_map')await expect(view.locator('.argument-column').last()).toContainText('Origin changes the result');
    if(grammar==='comparison') {
      await expect(view.locator('table')).toContainText('Coffee origin also matters.');
      await expect(view.locator('th[scope="col"]')).toHaveCount(2);
    }
    if(grammar==='timeline')await expect(view.locator('.timeline a.source-link').nth(1)).toHaveAttribute('href', /watch\?v=L_Guz73e6fw&t=60s$/);
    const selected=view.locator('[data-unit-id="u2"]').first();
    if(grammar==='comparison')await view.locator('th[scope="col"] button').first().click();
    else if(await selected.count())await selected.click();else await view.locator('[data-unit-id]').first().click();
    await expect(page.locator('#selected-evidence blockquote')).toBeVisible();
    const citation = page.locator('#detail-content .inline-citation').first();
    await expect(citation).toHaveAttribute('href', /^#source-/);
    const target = await citation.getAttribute('href');
    await citation.click();
    await expect(page.locator('#source-browser')).toHaveAttribute('open', '');
    await expect(page.locator(target)).toBeVisible();
    await expect(page.locator(target)).toHaveClass(/highlight/);
    await page.locator('#source-browser > summary').click();
    await expect(page.locator('#transcript-list')).not.toBeVisible();
    await expect(page.locator('#selected-evidence a')).toHaveAttribute('href', /https:\/\/www.youtube.com\/watch\?v=L_Guz73e6fw&t=\d+s$/);
    await page.getByRole('button',{name:'Show in transcript',exact:true}).click();
    await expect(page.locator('.source-row.highlight')).toBeVisible();
    await page.getByRole('button',{name:'← Return to overview',exact:true}).click();
    await expect(page.locator('.detail-empty')).toBeVisible();
    for(const width of [1280,390]) {
      await page.setViewportSize({width,height:900});
      await page.locator('#overview').scrollIntoViewIfNeeded();
      await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
      // Each card must fit its containing visual. Comparison uses an explicit scroll area.
      if(grammar!=='comparison')expect(await view.locator('.idea-node').evaluateAll(nodes=>nodes.every(n=>n.scrollWidth<=n.clientWidth+1))).toBe(true);
      else if(width===390) {
        await view.locator('.comparison-scroll').evaluate(node=>{node.scrollLeft=node.scrollWidth;});
        await expect(view.locator('th[scope="col"]').last()).toBeInViewport();
        await view.locator('.comparison-scroll').evaluate(node=>{node.scrollLeft=0;});
      }
      await page.screenshot({path:`.feasibility/screenshots/grammar-${grammar}-${width}.png`,fullPage:true});
    }
    expect(errors).toEqual([]);expect(remote).toEqual([]);
  });
}
