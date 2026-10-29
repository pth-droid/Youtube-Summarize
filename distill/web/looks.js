/* The look editor (Settings → Slide looks → Customize): one look's light and dark colours and its type, previewed on
   sample slides or a saved deck as they change. The server keeps only what differs from the look as designed and adds
   it to every deck in the look when the deck is shown, exported or shared. */
'use strict';
// [token, name, what it colours]
const LOOK_GROUPS=[
  ['Slide',[['surface','Slide background','The slide itself'],['paper','Around the slides','Behind the slide and the deck bars'],['ink','Text','Titles and body text'],['muted','Secondary text','Labels, sources and captions'],['line','Hairlines','Rules, borders and grid lines']]],
  ['Accent',[['accent','Accent','Numbers, links and highlights'],['on-accent','Text on accent','Text on accent fills'],['tint','Soft fill','Tiles and highlighted rows']]],
  ['Statement slides',[['feature','Statement background','Filled statement slides and panels'],['on-feature','Statement text','Text on statement fills']]],
  ['Chart series',[1,2,3,4,5].map(n=>[`data-${n}`,`Series ${n}`,n===1?'Charts and figure steps use them in this order':'Charts and figure steps'])],
];
const LOOK_MORE=['Labels and focus',[['warning','Warning text','Claims the source leaves uncertain'],['warning-bg','Warning background','Behind warning labels'],['inference','Inference label','Claims inferred from the source'],['focus','Focus ring','Keyboard focus']]];
// The pairs a deck draws, as the slide-design skill's check_look.mjs checks them: [text, behind it, name, minimum, projector target].
const LOOK_PAIRS=[['ink','surface','Text on the slide',4.5,7],['ink','paper','Text around the slides',4.5,7],['ink','tint','Text on soft fill',4.5,7],
  ['muted','surface','Secondary text',4.5,5.5],['muted','tint','Secondary text on soft fill',4.5,5.5],['accent','surface','Accent on the slide',4.5,4.5],
  ['accent','tint','Accent on soft fill',4.5,4.5],['on-accent','accent','Text on accent',4.5,4.5],['on-feature','feature','Statement text',4.5,4.5],
  ['warning','warning-bg','Warning label',4.5,4.5],['warning','surface','Warning on the slide',4.5,4.5],['inference','surface','Inference label',4.5,4.5],
  ['focus','surface','Focus ring',3,3],...[1,2,3,4,5].map(n=>[`data-${n}`,'surface',`Series ${n} on the slide`,3,3])];
const LOOK_VERDICTS={ok:'✓ Good',warn:'! Close up only',bad:'✕ Too faint'};

const lookEdit={details:null,id:null,mode:'light',values:null,saved:'',decks:[]};
const lookItem=id=>lookEdit.details?.looks.find(item=>item.id===id);
const lookDirty=()=>Boolean(lookEdit.values)&&JSON.stringify(lookEdit.values)!==lookEdit.saved;
function lookValues(item,designedOnly=false){const designed=item.designed,changes=designedOnly?{}:item.changes||{};return{light:{...designed.light,...changes.light},dark:{...designed.dark,...changes.dark},display:changes.display||designed.fonts.display||'',sans:changes.sans||designed.fonts.sans||''};}
const fontStack=(kind,id)=>lookEdit.details.fonts[kind].find(font=>font.id===id)?.stack||lookItem(lookEdit.id).designed[kind];
function currentTokens(){return{...lookEdit.values[lookEdit.mode],display:fontStack('display',lookEdit.values.display),sans:fontStack('sans',lookEdit.values.sans)};}

// WCAG 2 contrast, as check_look.mjs computes it.
function luminance(hex){const value=parseInt(hex.slice(1),16);return[value>>16,value>>8&255,value&255].map(channel=>{channel/=255;return channel<=.04045?channel/12.92:((channel+.055)/1.055)**2.4;}).reduce((sum,channel,index)=>sum+channel*[.2126,.7152,.0722][index],0);}
function contrast(a,b){const x=luminance(a),y=luminance(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
function normalHex(text){const value=text.trim().toLowerCase().replace(/^#?/,'#');if(/^#[0-9a-f]{3}$/.test(value))return'#'+[...value.slice(1)].map(c=>c+c).join('');return/^#[0-9a-f]{6}$/.test(value)?value:null;}

function colourRow([token,name,hint]){return`<div class="colour-row" data-row="${token}"><input type="color" data-colour="${token}" aria-label="${escapeHTML(name)} colour"><label class="plain" for="look-hex-${token}"><strong>${escapeHTML(name)}</strong><small>${escapeHTML(hint)}</small></label><input id="look-hex-${token}" class="hex-input" data-hex="${token}" maxlength="7" spellcheck="false" autocomplete="off" aria-label="${escapeHTML(name)} hex code"><button type="button" class="token-reset" data-reset="${token}" title="Back to the original" aria-label="Put ${escapeHTML(name.toLowerCase())} back to the original" hidden>↺</button></div>`;}
function renderLookFields(){const group=([title,rows])=>`<div class="colour-group"><h3>${title}</h3>${rows.map(colourRow).join('')}</div>`;$('look-fields').innerHTML=LOOK_GROUPS.map(group).join('')+`<details class="colour-more"><summary>${LOOK_MORE[0]}: warning, inference and focus</summary>${group(LOOK_MORE)}</details>`;}
function fontOptions(kind,designed){const fonts=lookEdit.details.fonts[kind];return(designed?'':`<option value="">As designed</option>`)+fonts.map(font=>`<option value="${font.id}">${escapeHTML(font.name)}${font.id===designed?' · as designed':''}</option>`).join('');}

async function openLookEditor(id){
  if(lookEdit.id===id&&lookEdit.values)return;
  if(lookDirty()&&!confirm('Leave without saving your changes to this look?')){history.replaceState(null,'',`#settings/looks/${lookEdit.id}`);return;}
  $('look-title').textContent='Loading the look…';$('look-lede').textContent='';
  try{
    const [details,library]=await Promise.all([json('/api/looks'),json('/api/library')]);
    lookEdit.details=details;const item=lookItem(id);
    if(!item){notice('This slide look was not found.',true);setView('settings/looks');return;}
    lookEdit.id=id;lookEdit.mode='light';lookEdit.values=lookValues(item);lookEdit.saved=JSON.stringify(lookEdit.values);
    lookEdit.decks=library.generations.filter(page=>page.metadata?.output_format==='lecture');
    $('look-title').textContent=item.name;$('look-crumb').textContent=item.name;document.title=`${item.name} · Distill`;
    renderLookFields();
    $('look-display').innerHTML=fontOptions('display',item.designed.fonts.display);$('look-sans').innerHTML=fontOptions('sans',item.designed.fonts.sans);
    const name=id=>state.settings?.looks?.find(look=>look.id===id)?.name||'';
    $('look-preview-source').innerHTML='<option value="">Sample slides</option>'+lookEdit.decks.map(page=>`<option value="${page.id}">${escapeHTML(page.title)}${page.metadata?.slide_theme?` · made in ${escapeHTML(name(page.metadata.slide_theme))}`:''}</option>`).join('');
    const own=lookEdit.decks.find(page=>page.metadata?.slide_theme===id)||lookEdit.decks[0];
    $('look-preview-source').value=own?.id||'';
    fillLook();loadLookPreview();
  }catch(error){$('look-title').textContent='Slide look';notice(error.message,true);}
}
// Leaving the editor drops the look and its fields, so opening it again reads what is saved and nothing stale can be
// edited meanwhile. Unsaved changes ask first.
function leaveLook(){
  if($('view-look').hidden||!lookEdit.values)return true;
  if(lookDirty()&&!confirm('Leave without saving your changes to this look?')){history.replaceState(null,'',`#settings/looks/${lookEdit.id}`);return false;}
  lookEdit.id=null;lookEdit.values=null;$('look-fields').innerHTML='';$('look-checks').innerHTML='';$('look-frame').src='about:blank';document.title='Distill · Your learning workspace';
  return true;
}

function fillLook(){
  const values=lookEdit.values[lookEdit.mode];
  document.querySelectorAll('[data-look-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.lookMode===lookEdit.mode)));
  Object.entries(values).forEach(([token,colour])=>{const colourInput=document.querySelector(`[data-colour="${token}"]`);if(!colourInput)return;colourInput.value=colour;$('look-hex-'+token).value=colour;$('look-hex-'+token).removeAttribute('aria-invalid');markRow(token);});
  $('look-display').value=lookEdit.values.display;$('look-sans').value=lookEdit.values.sans;
  paintLook();
}
function markRow(token){const changed=lookEdit.values[lookEdit.mode][token]!==lookItem(lookEdit.id).designed[lookEdit.mode][token];document.querySelector(`[data-row="${token}"]`).classList.toggle('changed',changed);document.querySelector(`[data-reset="${token}"]`).hidden=!changed;}
function setColour(token,colour,from){
  lookEdit.values[lookEdit.mode][token]=colour;
  if(from!=='colour')document.querySelector(`[data-colour="${token}"]`).value=colour;
  if(from!=='hex'){$('look-hex-'+token).value=colour;$('look-hex-'+token).removeAttribute('aria-invalid');}
  markRow(token);paintLook();
}
// Everything that follows the values: the sample slides, the saved deck, the readability checks and the buttons.
function paintLook(){
  const tokens=currentTokens();
  Object.entries(tokens).forEach(([key,value])=>$('look-sample').style.setProperty('--look-'+key,value));
  postLook();renderChecks(tokens);
  const item=lookItem(lookEdit.id),designed=JSON.stringify(lookValues(item,true)),dirty=lookDirty();
  $('look-save').disabled=!dirty;$('look-discard').hidden=!dirty;$('look-reset').disabled=JSON.stringify(lookEdit.values)===designed;
  const customized=Object.keys(item.changes||{}).length>0;
  $('look-lede').textContent=`${item.hint}. ${dirty?'You have unsaved changes.':customized?'Your changes are saved and show on every deck in this look.':'As designed. Changes you save show on every deck in this look.'}`;
}
function renderChecks(tokens){
  const rows=LOOK_PAIRS.map(([text,behind,name,minimum,target])=>{const ratio=contrast(tokens[text],tokens[behind]);return{text,behind,name,ratio,level:ratio<minimum?'bad':ratio<target?'warn':'ok'};});
  $('look-checks').innerHTML=rows.map(row=>`<li class="check-row ${row.level}"><span class="check-sample" aria-hidden="true">Aa</span><span class="check-name">${escapeHTML(row.name)}</span><span class="check-score"><span class="check-ratio">${row.ratio.toFixed(1)}:1</span><span class="check-verdict">${LOOK_VERDICTS[row.level]}</span></span></li>`).join('');
  [...$('look-checks').children].forEach((item,index)=>{const sample=item.firstElementChild;sample.style.color=tokens[rows[index].text];sample.style.background=tokens[rows[index].behind];});
  const bad=rows.filter(row=>row.level==='bad').length,warn=rows.filter(row=>row.level==='warn').length;
  $('checks-summary').textContent=!bad&&!warn?`${lookEdit.mode==='dark'?'Dark':'Light'}: every pair reads well, even in a lit room.`:[bad&&`${bad} too faint to read`,warn&&`${warn} may fade on a projector`].filter(Boolean).join(' · ');
}

// The saved-deck preview is a real deck, sandboxed like the reader, drawn at 1280 × 800 and scaled to fit. Colours
// being tried arrive by message; type being tried reloads it, so the deck fits its text to the type.
function loadLookPreview(){
  const deck=$('look-preview-source').value;
  $('look-sample').hidden=Boolean(deck);$('look-deck').hidden=!deck;$('look-deck-hint').hidden=!deck;
  $('look-frame').src=deck?`/api/looks/${lookEdit.id}/preview/${deck}?`+new URLSearchParams({display:lookEdit.values.display,sans:lookEdit.values.sans}):'about:blank';
  scaleLookFrame();
}
function postLook(){const frame=$('look-frame').contentWindow;if(!frame||$('look-deck').hidden||!lookEdit.values)return;frame.postMessage({type:'visual-learning-theme',theme:lookEdit.mode},'*');frame.postMessage({type:'distill-look',colours:lookEdit.values[lookEdit.mode]},'*');}
function scaleLookFrame(){const box=$('look-deck');if(!box.hidden&&box.clientWidth)$('look-frame').style.transform=`scale(${box.clientWidth/1280})`;}
new ResizeObserver(scaleLookFrame).observe($('look-deck'));
$('look-frame').addEventListener('load',postLook);
$('look-preview-source').addEventListener('change',loadLookPreview);

async function saveLook(){
  const button=$('look-save');button.disabled=true;button.textContent='Saving…';
  try{
    const values=lookEdit.values;
    const result=await json(`/api/looks/${lookEdit.id}`,{method:'PUT',body:JSON.stringify({light:values.light,dark:values.dark,display:values.display||null,sans:values.sans||null})});
    lookEdit.details=result;lookEdit.saved=JSON.stringify(values);
    if(state.settings)state.settings.looks=result.swatches;renderLooks(result.swatches);
    const item=lookItem(lookEdit.id);
    notice(Object.keys(item.changes).length?`${item.name} is saved. Every deck in this look shows it now.`:`${item.name} is back to its original design.`);
  }catch(error){notice(error.message,true);}
  finally{button.textContent='Save look';paintLook();}
}

const lookForm=$('look-form');
lookForm.addEventListener('input',event=>{
  const target=event.target;
  if(target.dataset.colour)setColour(target.dataset.colour,target.value,'colour');
  else if(target.dataset.hex){const colour=normalHex(target.value);target.setAttribute('aria-invalid',String(!colour));if(colour&&colour!==lookEdit.values[lookEdit.mode][target.dataset.hex])setColour(target.dataset.hex,colour,'hex');}
});
// A half-typed code goes back to the colour in use when the field is left.
lookForm.addEventListener('focusout',event=>{const token=event.target.dataset?.hex;if(token&&lookEdit.values){event.target.value=lookEdit.values[lookEdit.mode][token];event.target.removeAttribute('aria-invalid');}});
lookForm.addEventListener('change',event=>{if(event.target.id==='look-display'||event.target.id==='look-sans'){lookEdit.values[event.target.id==='look-display'?'display':'sans']=event.target.value;paintLook();if($('look-preview-source').value)loadLookPreview();}});
lookForm.addEventListener('click',event=>{
  const reset=event.target.closest('[data-reset]'),mode=event.target.closest('[data-look-mode]');
  if(reset)setColour(reset.dataset.reset,lookItem(lookEdit.id).designed[lookEdit.mode][reset.dataset.reset]);
  else if(mode&&mode.dataset.lookMode!==lookEdit.mode){lookEdit.mode=mode.dataset.lookMode;fillLook();}
});
lookForm.addEventListener('submit',event=>{event.preventDefault();event.stopPropagation();if(lookDirty())saveLook();});
$('look-reset').addEventListener('click',()=>{lookEdit.values=lookValues(lookItem(lookEdit.id),true);fillLook();notice('The original colours and type are back. Save the look to keep them.');});
$('look-discard').addEventListener('click',()=>{lookEdit.values=JSON.parse(lookEdit.saved);fillLook();});
addEventListener('beforeunload',event=>{if(!$('view-look').hidden&&lookDirty())event.preventDefault();});
// A look opened by its link: the workspace shows the view before this script has loaded.
{const [view,part,id]=location.hash.slice(1).split('/');if(view==='settings'&&part==='looks'&&id)openLookEditor(id);}
