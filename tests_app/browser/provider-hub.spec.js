const {test: base, expect} = require('@playwright/test');

const test = base.extend({
  cleanConnections: [async ({request}, use) => {
    const original=(await (await request.get('/api/settings')).json()).preferences;
    const html=await (await request.get('/')).text();
    const headers={'x-visual-learning':html.match(/name="visual-learning-token" content="([^"]+)"/)[1]};
    try {await use();} finally {
      const current=(await (await request.get('/api/settings')).json()).preferences;
      const added=Object.keys(current.api_connections).filter(id=>!original.api_connections[id]);
      const jobs=(await (await request.get('/api/jobs')).json()).jobs;
      for(const job of jobs.filter(job=>added.includes(job.input.preferences.provider)&&!['complete','failed','cancelled'].includes(job.state)))await request.post(`/api/jobs/${job.id}/cancel`,{headers});
      for(const id of added)expect((await request.delete(`/api/connections/${id}`,{headers})).ok()).toBeTruthy();
      expect((await request.put('/api/settings',{headers,data:original})).ok()).toBeTruthy();
    }
  }, {auto:true}],
});

async function openHub(page) {
  await page.goto('/#settings');
  await expect(page.locator('#create-button')).toBeEnabled();
  await expect(page.getByRole('heading',{name:'Provider access',exact:true})).toBeVisible();
}

async function addConnection(page,name='My Study Lab',model='anything-v2',endpoint='http://127.0.0.1:1234/v1') {
  await page.getByRole('button',{name:'Add connection'}).click();
  await page.locator('#connection-name').fill(name);
  await page.locator('#connection-endpoint').fill(endpoint);
  await page.locator('#connection-model').fill(model);
  await page.locator('#connection-key').fill('test-key-for-isolated-browser');
  await page.getByRole('button',{name:'Save connection',exact:true}).click();
  await expect(page.locator('#connection-editor')).toBeHidden();
  return page.locator('.api-connection').filter({hasText:name});
}

test('hub starts with saved connections instead of predefined provider slots',async({page})=>{
  await openHub(page);
  await expect(page.locator('#connection-empty')).toBeVisible();
  await expect(page.locator('#api-connection-list .api-connection')).toHaveCount(0);
  const options=await page.locator('#settings-provider option').allTextContents();
  expect(options.some(text=>/Grok|Muse|GLM|OpenAI-compatible/.test(text))).toBe(false);
  await page.getByRole('button',{name:'Add connection'}).click();
  await page.locator('#connection-name').fill('Unsaved');
  await page.getByRole('button',{name:'Cancel',exact:true}).click();
  await expect(page.locator('#connection-editor')).toBeHidden();
  await expect(page.locator('#connection-empty')).toBeVisible();
});

test('custom connection persists and is used by the quick start',async({page,request})=>{
  await openHub(page);
  const card=await addConnection(page);
  await expect(card).toContainText('anything-v2');
  await card.locator('summary').click();
  await expect(card).toContainText('Key saved');
  await card.getByRole('button',{name:'Use as default',exact:true}).click();
  await expect(page.locator('#notice')).toContainText('Default connection saved');
  const settings=(await (await request.get('/api/settings')).json()).preferences;
  const id=settings.provider;
  expect(settings.api_connections[id]).toMatchObject({name:'My Study Lab',model:'anything-v2',endpoint:'http://127.0.0.1:1234/v1'});
  expect(JSON.stringify(settings)).not.toContain('test-key-for-isolated-browser');
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Learn something new',exact:true})).toBeVisible();
  await expect(page.locator('#defaults-summary')).toContainText('My Study Lab');
  await expect(page.locator('#new-provider')).toHaveValue(id);
  await expect(page.locator('#new-paid')).toBeVisible();
  await page.locator('#new-paid').check();
  await page.locator('#video-url').fill('https://youtu.be/dQw4w9WgXcQ');
  await page.locator('#video-url').press('Enter');
  await expect(page.locator('#view-jobs')).toBeVisible();
  const jobs=(await (await request.get('/api/jobs')).json()).jobs;
  const job=jobs.find(job=>job.input.preferences.provider===id);
  expect(job.input.preferences.model).toBe('anything-v2');
  await page.getByRole('button',{name:'Cancel processing',exact:true}).click();
});

test('several models can share an endpoint and edits keep the key',async({page})=>{
  await openHub(page);
  await addConnection(page,'My fast model','fast-v1');
  await addConnection(page,'My detailed model','deep-v1');
  await expect(page.locator('#api-connection-list .api-connection')).toHaveCount(2);
  let card=page.locator('.api-connection').filter({hasText:'My fast model'});
  await card.locator('summary').click();
  await card.getByRole('button',{name:'Edit',exact:true}).click();
  await expect(page.locator('#connection-key')).toHaveValue('');
  await page.locator('#connection-name').fill('My revised model');
  await page.locator('#connection-model').fill('fast-v2');
  await page.getByRole('button',{name:'Save connection',exact:true}).click();
  card=page.locator('.api-connection').filter({hasText:'My revised model'});
  await expect(card).toContainText('fast-v2');
  await expect(card).toContainText('Key saved');
  await expect(page.locator('#settings-provider option').filter({hasText:'My revised model'})).toHaveCount(1);
  await page.reload();
  await expect(page.locator('#create-button')).toBeEnabled();
  await expect(card).toContainText('fast-v2');
  await expect(page.locator('.api-connection').filter({hasText:'My detailed model'})).toContainText('deep-v1');
});

test('remove a default connection removes its key and returns to Codex',async({page,request})=>{
  await openHub(page);
  const card=await addConnection(page,'Remove me');
  await card.locator('summary').click();
  await card.getByRole('button',{name:'Use as default',exact:true}).click();
  await expect(page.locator('#notice')).toContainText('Default connection saved');
  const id=(await (await request.get('/api/settings')).json()).preferences.provider;
  page.once('dialog',dialog=>dialog.accept());
  await card.getByRole('button',{name:'Remove connection',exact:true}).click();
  await expect(card).toHaveCount(0);
  const settings=(await (await request.get('/api/settings')).json());
  expect(settings.preferences.provider).toBe('codex');
  expect(settings.preferences.api_connections[id]).toBeUndefined();
  expect(settings.credentials[id]).toBeUndefined();
  await page.getByRole('link',{name:'Visual Learning home',exact:true}).click();
  await expect(page.locator('#defaults-summary')).toContainText('Codex');
});

test('invalid endpoints leave the editor open and preserve saved settings',async({page})=>{
  await openHub(page);
  await page.getByRole('button',{name:'Add connection'}).click();
  await page.locator('#connection-name').fill('Example');
  await page.locator('#connection-model').fill('example-model');
  await page.locator('#connection-endpoint').fill('http://remote.example/v1');
  await page.getByRole('button',{name:'Save connection',exact:true}).click();
  await expect(page.locator('#connection-error')).toBeVisible();
  await expect(page.locator('#connection-editor')).toBeVisible();
  await expect(page.locator('#api-connection-list .api-connection')).toHaveCount(0);
});

test('mobile hub escapes custom names and supports Anthropic format',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await openHub(page);
  await page.getByRole('button',{name:'Add connection'}).click();
  await page.locator('#connection-name').fill('Study <img src=x>');
  await page.locator('#connection-endpoint').fill('https://my-service.example/messages');
  await page.locator('#connection-model').fill('my-messages-model');
  await page.locator('#connection-protocol').selectOption('anthropic');
  await page.getByText('Connection options',{exact:true}).click();
  await expect(page.locator('#connection-compatible-options')).toBeHidden();
  await page.locator('#connection-no-key').check();
  await page.screenshot({path:'.feasibility/screenshots/provider-editor-mobile.png',fullPage:true});
  await page.getByRole('button',{name:'Save connection',exact:true}).click();
  const card=page.locator('.api-connection').filter({hasText:'Study <img src=x>'});
  await expect(card).toBeVisible();
  await expect(card.locator('img')).toHaveCount(0);
  await expect(card).toContainText('No key needed');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'.feasibility/screenshots/provider-hub-mobile.png',fullPage:true});
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:'.feasibility/screenshots/provider-hub-desktop.png',fullPage:true});
});
