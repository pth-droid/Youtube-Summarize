/* User-named connections. API keys are never returned in saved settings. */
'use strict';

// Local CLIs on the user's own subscription: no saved key and no paid-use approval.
const SUBSCRIPTION_PROVIDERS=['codex','claude_code'];

function providerName(id, connections=state.settings?.preferences.api_connections||{}) {
  if(id==='codex')return 'Codex';
  if(id==='claude_code')return 'Claude';
  if(id==='deepseek')return 'DeepSeek';
  return connections[id]?.name||(id.startsWith('api_')?'Saved API connection':id.replaceAll('_',' '));
}

function providerOptions(selected='') {
  const connections=state.settings?.preferences.api_connections||{};
  const options=[['codex','Codex · existing subscription'],['claude_code','Claude · existing subscription']];
  if(selected==='deepseek'||state.settings?.preferences.provider==='deepseek'||state.settings?.credentials?.deepseek?.configured)options.push(['deepseek','DeepSeek · saved connection']);
  Object.entries(connections).forEach(([id,value])=>options.push([id,`${providerName(id,connections)} · ${value.model||'Set a model'}`]));
  if(selected&&!options.some(([id])=>id===selected))options.push([selected,`${providerName(selected)} · unavailable`]);
  return options.map(([id,label])=>`<option value="${escapeHTML(id)}" ${id===selected?'selected':''}>${escapeHTML(label)}</option>`).join('');
}

function renderConnections(preferences, credentials) {
  const current=$('new-provider').value;
  const selected=SUBSCRIPTION_PROVIDERS.includes(current)||current==='deepseek'||preferences.api_connections?.[current]?current:preferences.provider;
  $('new-provider').innerHTML=providerOptions(selected);
  $('settings-provider').innerHTML=providerOptions(preferences.provider);
  const expanded=new Set([...$('api-connection-list').querySelectorAll('details[open]')].map(item=>item.dataset.connection));
  const connections=Object.entries(preferences.api_connections||{});
  $('connection-empty').hidden=connections.length>0;
  $('api-connection-list').innerHTML=connections.map(([id,value])=>{
    const key=credentials?.[id]?.configured;
    const requiresKey=value.requires_key??id!=='selfhost';
    return `<details class="api-connection" data-connection="${id}" ${expanded.has(id)?'open':''}><summary><span>${escapeHTML(providerName(id))}</span><span class="badge">${preferences.provider===id?'Default':key?'Key saved':requiresKey?'Add a key':'No key needed'}</span><small>${escapeHTML(value.model)} · ${escapeHTML(value.endpoint)}</small></summary><div class="connection-actions"><button type="button" class="button secondary" data-edit-connection="${id}">Edit</button><button type="button" class="button secondary" data-default-connection="${id}" ${preferences.provider===id?'disabled':''}>Use as default</button><button type="button" class="button quiet" data-remove-key="${id}" ${key?'':'hidden'}>Remove saved key</button><button type="button" class="button quiet" data-delete-connection="${id}">Remove connection</button></div></details>`;
  }).join('');
  $('legacy-deepseek').hidden=!(credentials?.deepseek?.configured||preferences.provider==='deepseek');
  paidRow();
}

function openConnectionEditor(id='') {
  const value=state.settings?.preferences.api_connections?.[id]||{};
  const form=$('connection-editor');
  form.reset();form.dataset.connection=id;
  $('connection-editor-title').textContent=id?'Edit connection':'Add a connection';
  $('connection-name').value=value.name|| (id?providerName(id):'');
  $('connection-endpoint').value=value.endpoint||'';
  $('connection-model').value=value.model||'';
  $('connection-protocol').value=value.protocol||'openai';
  $('connection-json-mode').checked=value.json_mode!==false;
  $('connection-token-parameter').value=value.token_parameter||'max_tokens';
  $('connection-no-key').checked=value.requires_key===false||id==='selfhost'&&value.requires_key===undefined;
  $('connection-key').placeholder=id?'Leave blank to keep the saved key':'Enter an API key, if required';
  $('connection-compatible-options').hidden=value.protocol==='anthropic';
  $('connection-error').hidden=true;
  form.hidden=false;$('add-connection').hidden=true;
  $('connection-name').focus();
}

function closeConnectionEditor() {
  $('connection-editor').reset();$('connection-editor').hidden=true;$('add-connection').hidden=false;$('add-connection').focus();
}

async function saveConnection() {
  const button=$('save-connection');
  if(button.disabled)return;
  button.disabled=true;$('connection-error').hidden=true;
  const id=$('connection-editor').dataset.connection;
  const value={name:$('connection-name').value.trim(),endpoint:$('connection-endpoint').value.trim(),model:$('connection-model').value.trim(),protocol:$('connection-protocol').value,api_key:$('connection-key').value.trim(),requires_key:!$('connection-no-key').checked,json_mode:$('connection-json-mode').checked,token_parameter:$('connection-token-parameter').value};
  try {
    await json(id?`/api/connections/${id}`:'/api/connections',{method:id?'PUT':'POST',body:JSON.stringify(value)});
    $('connection-key').value='';
    await loadSettings(false);
    closeConnectionEditor();
    notice('Connection saved. You can select it for a page or use it as your default.');
  } catch(error) {
    $('connection-error').textContent=error.message;$('connection-error').hidden=false;
  } finally {button.disabled=false;}
}

async function connectionAction(button) {
  if(button.id==='add-connection')openConnectionEditor();
  else if(button.id==='cancel-connection')closeConnectionEditor();
  else if(button.dataset.editConnection)openConnectionEditor(button.dataset.editConnection);
  else if(button.dataset.defaultConnection){
    await json('/api/settings',{method:'PUT',body:JSON.stringify({provider:button.dataset.defaultConnection})});
    await loadSettings();notice('Default connection saved. Your next page will use it.');
  } else if(button.dataset.deleteConnection){
    const id=button.dataset.deleteConnection;
    if(!confirm(`Remove ${providerName(id)} and its saved key? Saved learning pages will stay in your library.`))return;
    await json(`/api/connections/${id}`,{method:'DELETE'});
    await loadSettings();
    if($('connection-editor').dataset.connection===id)closeConnectionEditor();
    notice('Connection removed.');
  }
}
