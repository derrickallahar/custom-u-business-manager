'use strict';
const el=id=>document.getElementById(id);
const labels={'customers.view':'View customers and contacts','customers.create':'Add customers and contacts','customers.edit':'Edit customers and contacts','quotes.view':'View quotes and print previews','quotes.create':'Create quotes','quotes.edit':'Edit saved draft quotes','quotes.approve':'Finalise and lock quotes','invoices.view':'View invoices and print previews','invoices.create':'Create invoices from finalised quotes','invoices.edit':'Edit saved draft invoices','invoices.issue':'Finalise and lock invoices','payments.view':'View payment history and receipts','payments.record':'Record money received','payments.reverse':'Reverse incorrect payment entries'};
const groups=['customers','quotes','invoices','payments'];let selected=null,busy=false,dirty=false,rows=[],staffEnabled=true;
const messages={CONFIRMED_ACCOUNT_REQUIRED:'No single confirmed account matches that email. Add the person in Supabase Authentication first, then return here.',ALREADY_ADDED:'This person is already listed. Open their existing access settings.',ADMIN_PROTECTED:'Administrator access cannot be changed here.',VERSION_CONFLICT:'These settings changed in another session. Copy any changes you want to keep, then use Reload saved access before saving again.',VIEW_PERMISSION_REQUIRED:'Enable View in an area before enabling its other actions.',RELATED_VIEW_REQUIRED:'Creating or editing quotes also needs View customers. Creating invoices needs View quotes. Viewing payments needs View invoices.',INVALID_PERMISSIONS:'Check the selected permissions.',INVALID_REQUEST:'The server rejected these settings. Reload saved access, then try again.'};
function status(s,kind='info',focus=false){el('status').textContent=s;const box=el('edit-status');if(!el('edit').hidden){box.hidden=false;box.textContent=s;box.dataset.kind=kind;box.setAttribute('role',kind==='error'?'alert':'status');if(focus){box.focus();box.scrollIntoView?.({block:'nearest'});}}}
function clear(){selected=null;rows=[];dirty=false;el('workspace').hidden=true;el('edit').hidden=true;el('rows').replaceChildren();el('permissions').replaceChildren();el('identity').textContent='';el('person').textContent='';el('email').value='';el('active').checked=false;el('edit-status').textContent='';el('edit-status').hidden=true;}
async function api(path,body){
 let r;try{r=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});}catch{throw Error('The connection failed. The save is not confirmed. Use Reload saved access before retrying.');}
 let d;try{d=await r.json();}catch{if(r.status===401||r.status===403)clear();throw Error('The server did not return a readable result (HTTP '+r.status+'). The save is not confirmed. Use Reload saved access.');}
 if(!r.ok){if(r.status===401||(r.status===403&&d.error!=='ADMIN_PROTECTED')){clear();throw Error('Administrator access is required. Return to Workspace to sign in.');}throw Error(messages[d.error]||'Save not confirmed (HTTP '+r.status+'). Reload saved access before retrying.');}return d;
}
async function run(fn){if(busy)return;busy=true;document.querySelectorAll('input,button').forEach(x=>x.disabled=true);try{await fn();}catch(e){status(e.message,'error',true);}finally{busy=false;document.querySelectorAll('input,button').forEach(x=>x.disabled=false);}}
function leave(){return !dirty||window.confirm('Discard unsaved permission changes?');}
function needs(key){const [area,action]=key.split('.'),result=action==='view'?[]:[area+'.view'];if(key==='quotes.create'||key==='quotes.edit')result.push('customers.view');if(key==='invoices.create')result.push('quotes.view');if(area==='payments')result.push('invoices.view');return result;}
function boxFor(key){return el('permissions').querySelector('[data-permission="'+key+'"]');}
function permissionChange(input){
 const changed=[];
 if(input.checked){function add(key){for(const required of needs(key)){const box=boxFor(required);if(!box.checked){box.checked=true;changed.push(labels[required]);}add(required);}}add(input.dataset.permission);}
 else{let again=true;while(again){again=false;for(const key of Object.keys(labels)){const box=boxFor(key);if(box.checked&&needs(key).some(k=>!boxFor(k).checked)){box.checked=false;changed.push(labels[key]);again=true;}}}}
 dirty=true;status(changed.length?(input.checked?'Also selected the required permissions: ':'Also cleared actions that need that permission: ')+changed.join('; ')+'. Review the checked boxes, then Save access.':'Unsaved changes. Click Save access to apply them.');
}
function effective(row){if(row.role==='admin')return 'Administrator';if(!row.access?.active)return 'Disabled';if(!row.member_active)return 'Blocked by account membership';if(!staffEnabled)return 'Paused for all staff';return Object.values(row.access.permissions).some(v=>v===true)?'Enabled':'Enabled · no areas selected';}
function open(row,checkDirty=true){if(checkDirty&&!leave())return;selected=row;el('edit').hidden=false;el('person').textContent=row.email;el('active').checked=row.access.active;el('permissions').replaceChildren();
 for(const group of groups){const fs=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=group[0].toUpperCase()+group.slice(1);fs.append(legend);for(const [key,label] of Object.entries(labels)){if(!key.startsWith(group+'.'))continue;const l=document.createElement('label'),i=document.createElement('input');i.type='checkbox';i.dataset.permission=key;i.checked=row.access.permissions[key]===true;i.onchange=()=>permissionChange(i);l.append(i,document.createTextNode(' '+label));fs.append(l);}el('permissions').append(fs);}dirty=false;status('Saved state: '+effective(row)+'.');el('person').scrollIntoView?.({behavior:'smooth'});}
async function list(){const r=await api('/api/staff');if(!Array.isArray(r.data)||typeof r.enabled!=='boolean')throw Error('The staff list could not be verified. Refresh before making another change.');rows=r.data;staffEnabled=r.enabled;el('pause-notice').hidden=r.enabled;el('rows').replaceChildren();for(const row of rows){const tr=document.createElement('tr');for(const value of [row.email,effective(row),row.role==='admin'?'All administrator access':Object.keys(labels).filter(k=>row.access?.permissions[k]===true).map(k=>labels[k]).join(' · ')||'No permissions']){const td=document.createElement('td');td.textContent=value;tr.append(td);}const td=document.createElement('td');if(row.role!=='admin'&&row.access){const b=document.createElement('button');b.type='button';b.textContent='Edit access';b.onclick=()=>open(row);td.append(b);}else td.textContent=row.role==='admin'?'Protected':'Add this email to configure access';tr.append(td);el('rows').append(tr);}}
el('add').onsubmit=e=>{e.preventDefault();run(async()=>{if(!leave())return;await api('/api/staff/save',{op:'add',email:el('email').value.trim()});el('email').value='';el('edit').hidden=true;selected=null;dirty=false;await list();status('Person added with access disabled and no permissions. Open Edit access to choose permissions and enable their account.');});};
el('edit').oninput=()=>dirty=true;
el('active').onchange=()=>{dirty=true;status('Unsaved change: access will be '+(el('active').checked?'enabled':'disabled')+' when you click Save access.');};
el('edit').onsubmit=e=>{
 e.preventDefault();if(busy||!selected)return;
 // Capture the reviewed values before disabling controls during the request.
 const permissions={};el('permissions').querySelectorAll('[data-permission]').forEach(i=>{if(i.checked)permissions[i.dataset.permission]=true;});
 const row=selected,payload={op:'save',user_id:row.user_id,version:row.access.version,active:el('active').checked,permissions};
 const missing=[...new Set(Object.keys(permissions).flatMap(needs).filter(k=>!permissions[k]))];
 if(missing.length){status('Not saved. Select '+missing.map(k=>labels[k]).join('; ')+', or clear the actions that need them.','error',true);return;}
 if(payload.active&&!row.member_active){status('Not enabled. This account has an additional membership block. Enabling it here cannot remove that block.','error',true);return;}
 run(async()=>{
  status('Saving access…');const r=await api('/api/staff/save',payload),saved=r.data;
  if(!saved||saved.user_id!==payload.user_id||saved.active!==payload.active||!Number.isInteger(saved.version)||saved.version<payload.version||!saved.permissions||Object.keys(labels).some(k=>(saved.permissions[k]===true)!==(permissions[k]===true)))throw Error('The server result did not confirm these settings. Use Reload saved access before retrying.');
  selected={...row,access:saved};dirty=false;
  try{await list();}catch(e){if(!el('workspace').hidden)status('The server confirmed the save, but the staff list could not refresh. Use Reload saved access before another change.','error',true);else status(e.message,'error');return;}
  const current=rows.find(x=>x.user_id===payload.user_id);
  if(!current?.access)throw Error('The server confirmed the save, but this person is missing from the refreshed list. Refresh before another change.');
  open(current,false);
  if(current.access.version!==saved.version||current.access.active!==saved.active||Object.keys(labels).some(k=>(current.access.permissions[k]===true)!==(saved.permissions[k]===true)))status('Your save completed, but another change is now present. The current saved settings are shown.','info',true);
  else status('Saved and verified: '+effective(current)+'. '+(current.access.active?'The checked permissions are saved.':'This person cannot access the app.'),'success',true);
 });
};
el('cancel').onclick=()=>{if(leave()){dirty=false;selected=null;el('edit').hidden=true;}};
el('reload-access').onclick=()=>run(async()=>{if(!selected||!leave())return;const id=selected.user_id;await list();const row=rows.find(x=>x.user_id===id);if(!row?.access)throw Error('This person is no longer in the staff list.');open(row,false);status('Reloaded saved access: '+effective(row)+'.','info',true);});
el('refresh').onclick=()=>run(async()=>{if(!leave())return;dirty=false;selected=null;el('edit').hidden=true;await list();status('Staff access refreshed.');});
el('logout').onclick=()=>run(async()=>{if(!leave())return;clear();await api('/api/logout',{});status('Signed out.');});
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
run(async()=>{const s=await api('/api/session');if(s.me.role!=='admin'){clear();throw Error('Administrator access is required. Return to Workspace.');}el('identity').textContent=s.me.email;el('workspace').hidden=false;await list();status('Choose the permissions for each person. New entries start disabled.');});
