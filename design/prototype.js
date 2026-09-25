'use strict';
// All data is fictional. No media, credentials, network, persistence, or crypto.
const cases = {
 exact: ['Original · exact file', 'Exact file match', 'Valid', 'Trusted', 'Exact file match', 'App/device capture assurance unavailable. Installation signature checked.', 'Record available', 'This does not establish whether the scene is truthful.'],
 pixels: ['Metadata changed · pixels match', 'Exact defined-content match', 'Valid', 'Trusted', 'Exact defined-content match', 'Fresh capture challenge passed. App/device assurance unavailable.', 'Record available', 'Pixels match; file bytes differ. Metadata may have changed.'],
 mismatch: ['Screenshot / copied watermark', 'Record recovered; content does not exactly match', 'Valid', 'Trusted', 'Mismatch', 'Checks belong to the candidate record, not this supplied photo.', 'Record available', 'This does not explain why it differs or prove it came from this record.'],
 none: ['No identifier recovered', 'No record recovered', 'Not checked', 'Unknown', 'Uncheckable', 'Unavailable', 'No ID recovered; no lookup performed', 'This does not tell us whether the photo is real or AI-generated.'],
 missing: ['ID found · record missing', 'No record found', 'Not checked', 'Unknown', 'Uncheckable', 'Unavailable', 'Lookup returned no record', 'A missing record does not tell us whether the photo is truthful.'],
 network: ['Lookup network failure', 'Lookup unavailable', 'Not checked', 'Unknown', 'Uncheckable', 'Unavailable', 'Network unavailable', 'Try again when connected or import a signed receipt.'],
 stale: ['Matching photo · stale trust', 'Issuer status needs refresh', 'Valid', 'Stale', 'Exact file match', 'Record reports checks; current issuer status is unknown.', 'Offline receipt; trust cache older than 24 hours', 'The file matches, but current signer status is unknown.'],
 unknown: ['Matching photo · unknown issuer', 'Issuer unknown', 'Valid', 'Unknown', 'Exact file match', 'Record claims not trusted.', 'Receipt imported', 'A matching hash does not make an unknown issuer trusted.'],
 revoked: ['Matching photo · revoked issuer', 'Issuer revoked', 'Valid', 'Revoked', 'Exact file match', 'Affected policy claims invalidated.', 'Record available', 'The file matches this record, but the issuer is revoked.'],
 invalid: ['Invalid record signature', 'Record signature invalid', 'Invalid', 'Unknown', 'Uncheckable', 'Record claims not trusted.', 'Record retrieved', 'This record cannot establish a trusted baseline.'],
 format: ['Unsupported record format', 'Record format unsupported', 'Unsupported', 'Unknown', 'Uncheckable', 'Unavailable', 'Unsupported schema or signature algorithm', 'This version cannot validate the record.'],
 unsupported: ['Image exceeds supported limits', 'Unable to check this file', 'Not checked', 'Unknown', 'Uncheckable', 'Unavailable', 'Unsupported image size', 'Pilot limit: JPEG/PNG, 25 MiB, 20 million pixels; neither dimension over 16,384.'],
 decoder: ['Watermark decoder unavailable', 'Decoder unavailable', 'Not checked', 'Unknown', 'Uncheckable', 'Unavailable', 'Unsupported decoder version', 'This is not a content mismatch. Try an exact-file lookup or a compatible signed app release.'],
 development: ['Development certificate', 'Development record', 'Valid', 'Untrusted development issuer', 'Exact file match', 'Development checks only.', 'Development receipt', 'Public verification does not trust development records.'],
 receipt: ['Offline receipt · fresh trust', 'Exact file match', 'Valid', 'Trusted', 'Exact file match', 'No fresh capture challenge: captured offline.', 'Offline receipt; current lookup availability unknown', 'Content matches under a fresh cached trust policy. The scene is not certified.']
};
function trustedMatch(v) { return v[2] === 'Valid' && v[3] === 'Trusted' && ['Exact file match','Exact defined-content match'].includes(v[4]); }
let state = { page:'capture', permission:false, consent:null, asset:null, result:'exact', modal:null, toast:'' };
const screen=document.getElementById('screen');
const verifySelect=document.getElementById('verify-mode');
Object.entries(cases).forEach(([key,value])=>{ const option=document.createElement('option'); option.value=key; option.textContent=value[0]; verifySelect.append(option); });
const photo = '<div class="photo" role="img" aria-label="Illustrative landscape placeholder">SAMPLE PHOTO · NO REAL MEDIA</div>';
const button=(action,label,kind='')=>`<button data-action="${action}" class="${kind}">${label}</button>`;
const actions=(...b)=>`<div class="actions">${b.join('')}</div>`;
const rows=(items)=>`<dl>${items.map(([a,b])=>`<div><dt>${a}</dt><dd>${b}</dd></div>`).join('')}</dl>`;
function render(){
 document.querySelectorAll('[data-nav]').forEach(b=>{ if(b.dataset.nav===state.page)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current'); });
 let html=''; const a=state.asset;
 if(state.modal){
  const dialogs={
   disclosure:['Register your photos?','Registration publishes a record ID, photo hashes, and capture-check results. The service sees registration and lookup requests. Your photo is not uploaded. Copies of records cannot be recalled.',actions(button('consent','Allow registration'),button('local','Keep local only','secondary'))],
   share:['Share original',`${a && a.status==='registered'?'Registered export.':a && a.status==='rejected'?'Registration was rejected. This photo has no issued certificate.':a && a.status==='local'?'Registration was not requested. This photo has no public record.':a && ['removed','removal'].includes(a.status)?'Public record removal was requested. Lookup may fail.':'Registration is pending or incomplete. Public lookup may not succeed.'} Sharing destinations may change the file.`,actions(button('share-done','Open share sheet · simulated'),button('close','Cancel','secondary'))],
   digest:['Look up this exact file?','Send this file’s SHA-256 digest to look for an exact match? The digest can identify this file. The photo stays on your device.',actions(button('digest-yes','Send digest · simulated'),button('close','Not now','secondary'))],
   remove:['Remove public record?','Future lookup will stop working. Your local photo stays. Previously copied records cannot be recalled.',actions(button('remove-yes','Remove record','danger'),button('close','Keep record','secondary'))],
   delete:['Delete local photo?',`This deletes the photo on this device, not its public record. ${a && ['pending','paused','processing','expired'].includes(a.status)?'Pending registration will be canceled and any in-flight commit reconciled first.':''} Receipt and management access are retained separately.`,actions(button('delete-yes','Delete local photo','danger'),button('close','Keep photo','secondary'))],
   recovery:['Save management recovery','Anyone with this recovery file can manage removal of your records. It cannot restore photos or your capture signing key. Keep it private and separate from public receipts.',actions(button('recovery-done','Choose private destination · simulated'),button('close','Cancel','secondary'))],
   import:['Import management recovery','This restores management access only. A public receipt cannot restore that access. No real secret is accepted in this prototype.',actions(button('import-done','Simulate recovery import'),button('close','Cancel','secondary'))]
  }; const d=dialogs[state.modal]; html=`<span class="tag">CONFIRMATION</span><h2>${d[0]}</h2><p>${d[1]}</p>${d[2]}`;
 }else if(state.page==='capture'){
  if(!state.permission)html='<h2>Capture a photo</h2><p>Your photos stay on this device unless you share them.</p>'+actions(button('enable','Enable camera · simulated'),button('deny','Deny camera · simulated','secondary'));
  else html='<span class="tag">PHOTO / REAR CAMERA</span>'+photo+'<h2>Ready when you are</h2><p class="small">'+(document.getElementById('capture-mode').value==='offline'?'Offline · registration will wait.':'Sample camera preview. No device camera is active.')+'</p>'+actions(button('shutter','Take photo'));
 }else if(state.page==='processing'){
  html='<h2>Preparing your photo</h2><div class="progress"><strong>Checking saved photo</strong>Preparing export → checking → signing</div><p>No percentage is shown until actual progress is measurable.</p>'+actions(button('finish','Finish processing · simulated'),button('pause','Pause processing','secondary'));
 }else if(state.page==='library'){
  html='<h2>Your library</h2>'+(a?(a.deleted?'':photo)+`<div class="card"><h3>${a.deleted?'Photo deleted locally':'Sample capture'}</h3><p>${label(a.status)}</p></div>`+actions(button('detail','Open details')):'<p>Your captures will appear here.</p>'+actions(button('go-capture','Capture a photo')));
 }else if(state.page==='detail'){
  if(!a){state.page='library';render();return;}
  html=(a.deleted?'':photo)+'<h2>'+label(a.status)+'</h2>'+rows([['Photo',a.deleted?'Deleted locally':['processing','paused'].includes(a.status)?'Needs processing':a.status==='unsigned'?'Ready; unsigned':'Ready; locally signed'],['Registration',label(a.status)],['Capture checks',a.mode==='offline'||a.reduced?'No fresh capture challenge. App/device assurance unavailable.':'App/device capture assurance unavailable in this example.']]);
  if(a.status==='expired')html+='<p class="notice">The online capture check expired. Your photo is safe. Registering with fewer checks cannot validate capture time.</p>';
  if(a.status==='rejected')html+='<p class="notice">Security validation failed. A reduced-assurance retry is not available.</p>';
  let controls=[];
  if(!a.deleted && ['processing','paused'].includes(a.status))controls.push(button('resume','Resume processing'));
  if(!a.deleted && !['processing','paused','unsigned'].includes(a.status))controls.push(button('share','Share original'));
  if(a.status==='unsigned' && !a.deleted)controls.push(button('unsigned-export','Save photo without a record'));
  if(a.status==='expired')controls.push(button('reduce','Register with fewer capture checks','secondary'),button('go-capture','Retake photo','secondary'));
  if(a.status==='pending')controls.push(button('sync','Simulate successful sync','secondary'));
  if(a.status==='registered')controls.push(button('receipt','Export public receipt','secondary'),button('remove','Remove public record','secondary'));
  if(a.status==='removal')controls.push(button('removed','Simulate server removal acknowledgement','secondary'));
  if(a.status==='canceling')controls.push(button('deleted','Simulate cancellation reconciled','secondary'));
  if(!a.deleted && !['processing','paused'].includes(a.status))controls.push(button('verify-own','Verify this photo','secondary'));
  if(!a.deleted)controls.push(button('delete','Delete local photo','secondary'));
  html+=actions(...controls);
 }else if(state.page==='verify'){
  html='<h2>Check a photo</h2><p>The photo is checked on your device. Record lookup sends its ID to the service.</p><div class="card"><h3>Three different questions</h3><p class="small">Can we recover a record? Does the content match? Which capture checks passed?</p></div>'+actions(button('check','Choose sample photo'),button('receipt-import','Import sample public receipt','secondary'));
 }else if(state.page==='checking'){
  html='<h2>Checking this photo</h2><ol><li>Read file locally</li><li>Recover record ID</li><li>Look up record</li><li>Check signature and issuer</li><li>Compare supplied content</li></ol>'+actions(button('show-result','Complete sample check'),button('cancel-check','Cancel','secondary'));
 }else if(state.page==='result'){
  const v=cases[state.result]; html=`<span class="tag">ILLUSTRATIVE RESULT</span><h2 class="${trustedMatch(v)?'match':''}">${v[1]}</h2><p class="small">${v[7]}</p>`+rows([['Record signature',v[2]],['Issuer status',v[3]],['Content',v[4]],['Capture checks',v[5]],['Availability',v[6]]]);
  let controls=[button('details','Record and trust details','secondary')];
  if(['none','mismatch'].includes(state.result))controls.push(button('crop','Select screenshot region','secondary'));
  if(['none','decoder'].includes(state.result))controls.push(button('digest','Try exact-file lookup','secondary'));
  if(['network','stale'].includes(state.result))controls.push(button('retry','Retry / refresh · simulated','secondary'));
  controls.push(button('go-verify','Check another photo','secondary'));html+=actions(...controls);
 }else if(state.page==='crop'){
  html='<h2>Select the photo</h2>'+photo.replace('</div>','<div class="crop"></div></div>')+'<p>Select the media inside the screenshot. This prototype uses a fixed sample region.</p><p class="notice">Region selection helps recover an ID. Integrity checks still cover the original supplied photo.</p>'+actions(button('crop-check','Retry selected region · simulated'),button('crop-cancel','Cancel','secondary'));
 }else if(state.page==='details'){
  html='<h2>Record and trust</h2>'+rows([['Trust policy','proofcam-android-pilot-v1'],['Issuer',cases[state.result][3]==='Trusted'?'Sample trusted pilot issuer':'See issuer status on result'],['Trust freshness',state.result==='stale'?'Older than 24 hours':'Illustrative; no actual refresh performed'],['Comparison scope','Entire supplied asset; region selection never changes this'],['Times','Device time is reported; registration time is the service’s statement.'],['Privacy','No media is uploaded in the intended verification flow.']])+actions(button('back-result','Back to results','secondary'));
 }else if(state.page==='settings'){
  html='<h2>Privacy and recovery</h2><p>Photos stay local unless you share them. Public IDs and hashes are linkable. No location or microphone access.</p><div class="card"><h3>Two different exports</h3><p class="small">A public receipt lets someone verify a record. A secret recovery file lets its holder manage removal of your records.</p></div>'+actions(button('recovery','Save management recovery'),button('import','Import management recovery','secondary'),button('disclosure','Registration choice','secondary'))+'<p class="small">Local media is not automatically backed up. Losing all management credentials means losing self-service removal access.</p>';
 }
 screen.innerHTML=(state.toast?`<p class="notice" role="status">${state.toast}</p>`:'')+html;
}
function label(s){return {processing:'Processing',paused:'Needs recovery',pending:'Registration pending',registered:'Registered',expired:'Capture check expired',rejected:'Registration rejected',unsigned:'Saved locally; signing unavailable',local:'Saved locally; registration not requested',removal:'Removal pending; record may still be available',removed:'Public record removed',canceling:'Canceling registration; checking public status'}[s]||s;}
function act(action){
 state.toast=''; const a=state.asset;
 if(['share','digest','remove','delete','recovery','import','disclosure'].includes(action)){state.modal=action;render();return;}
 switch(action){
 case 'enable':state.permission=true;break;
 case 'deny':state.toast='Camera access is off. You can still verify photos.';break;
 case 'shutter':
  if(document.getElementById('capture-mode').value==='storage'){state.toast='Not enough space to safely save a photo. Existing photos are unchanged.';break;}
  if(state.consent===null){state.modal='disclosure';break;}
  state.asset={status:'processing',mode:document.getElementById('capture-mode').value,deleted:false,reduced:false};state.page='processing';break;
 case 'consent':state.consent=true;state.modal=null;state.toast='Registration allowed. Sample enrollment is assumed; real pilot admission is required.';break;
 case 'local':state.consent=false;state.modal=null;state.toast='Capture remains available. Photos will stay local until you choose registration.';break;
 case 'finish':a.status=a.mode==='signing'?'unsigned':!state.consent?'local':({online:'registered',offline:'pending',expired:'expired',rejected:'rejected'}[a.mode]||'pending');state.page='detail';break;
 case 'pause':a.status='paused';state.page='library';break;
 case 'resume':a.status='processing';state.page='processing';break;
 case 'detail':state.page='detail';break;
 case 'close':state.modal=null;break;
 case 'share-done':state.modal=null;state.toast='Share sheet simulated. Delivery is not confirmed. Registration state is unchanged.';break;
 case 'unsigned-export':state.toast='Unsigned local export simulated. No record or capture certification is implied.';break;
 case 'sync':a.status='registered';a.reduced=a.mode==='offline'||a.reduced;break;
 case 'reduce':a.status='pending';a.reduced=true;state.toast='Reduced-assurance request queued. No new capture challenge is claimed.';break;
 case 'receipt':state.toast='Public receipt export simulated. No management secret is included.';break;
 case 'remove-yes':a.status='removal';state.modal=null;break;
 case 'removed':a.status='removed';break;
 case 'delete-yes':state.modal=null;if(['pending','processing','paused','expired'].includes(a.status))a.status='canceling';else a.deleted=true;break;
 case 'deleted':a.status='local';a.deleted=true;state.toast='Example: no public commit found. Photo deleted after reconciliation; management handle retained.';break;
 case 'recovery-done':state.modal=null;state.toast='Private recovery export simulated. No secret was generated or saved.';break;
 case 'import-done':state.modal=null;state.toast='Management recovery simulated. Photos and capture signing keys are not restored.';break;
 case 'check':state.result=verifySelect.value;state.page='checking';break;
 case 'receipt-import':state.result='receipt';state.page='checking';break;
 case 'verify-own':state.result=a.status==='registered'?(a.reduced?'receipt':'exact'):a.status==='removed'?'missing':'none';state.page='checking';break;
 case 'show-result':state.page='result';break;
 case 'cancel-check':state.page='verify';state.toast='Check stopped. Source photo unchanged.';break;
 case 'go-capture':state.page='capture';break;
 case 'go-verify':state.page='verify';break;
 case 'crop':state.page='crop';break;
 case 'crop-cancel':state.page='result';break;
 case 'crop-check':state.result='mismatch';state.page='result';state.toast='Sample ID recovered from selected region. Full supplied content still differs.';break;
 case 'digest-yes':state.modal=null;state.result='missing';state.page='result';state.toast='Digest lookup consent recorded only in this simulation. No network request was made.';break;
 case 'retry':state.toast='Refresh simulated only. No current trust information obtained; existing result retained.';break;
 case 'details':state.page='details';break;
 case 'back-result':state.page='result';break;
 }
 render();
}
screen.addEventListener('click',e=>{const b=e.target.closest('[data-action]');if(b)act(b.dataset.action);});
document.querySelectorAll('[data-nav]').forEach(b=>b.addEventListener('click',()=>{if(state.page==='processing'&&state.asset)state.asset.status='paused';state.page=b.dataset.nav;state.modal=null;state.toast='';render();}));
document.getElementById('settings').addEventListener('click',()=>{if(state.page==='processing'&&state.asset)state.asset.status='paused';state.page='settings';state.modal=null;state.toast='';render();});
document.getElementById('reset').addEventListener('click',()=>{state={page:'capture',permission:false,consent:null,asset:null,result:'exact',modal:null,toast:''};render();});
document.getElementById('capture-mode').addEventListener('change',()=>render());
verifySelect.addEventListener('change',()=>{state.result=verifySelect.value;state.page='verify';state.modal=null;state.toast='';render();});
render();
