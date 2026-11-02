'use strict';
const $=id=>document.getElementById(id);
const state={csrf:'',me:null,tab:'overview',customers:[],products:[],catalogs:[],quotes:[],invoices:[],jobs:[],staff:[],files:[],audit:[]};
const TAB_PERM={overview:'jobs.view',customers:'customers.view',products:'products.view',
    catalogs:'catalogs.view',quotes:'quotes.view',invoices:'invoices.view',jobs:'jobs.view',files:'files.view'};
const permit=key=>!!(state.me?.permissions?.[key]);
const allowed=tab=>!!state.me && (['staff','security'].includes(tab)?state.me.role==='admin':permit(TAB_PERM[tab]));
function showRole(){const historyLink=$('historyPreviewLink');if(historyLink)historyLink.hidden=state.me?.role!=='admin';document.querySelectorAll('[data-tab]').forEach(b=>b.hidden=!allowed(b.dataset.tab));
  $('staffIdentity').textContent=state.me?`${state.me.full_name} · ${state.me.role.toUpperCase()}`:'NOT SIGNED IN'}
state.permissionCatalog=null;state.permissionDetail=null;

const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=c=>'BSD $'+(Number(c||0)/100).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
function note(txt,error=false){$('notice').textContent=txt;$('notice').className=error?'error':'';}
async function api(path,data=null){const opts={credentials:'same-origin',headers:{}};if(data!==null){opts.method='POST';opts.headers['Content-Type']='application/json';opts.headers['X-CustomU-CSRF']=state.csrf;opts.body=JSON.stringify(data)}const r=await fetch(path,opts);let j;try{j=await r.json()}catch{throw Error('UNEXPECTED_SERVER_RESPONSE')}if(!r.ok)throw Error(j.error||'REQUEST_FAILED');return j.result??j.data??j;}
async function login(e){e.preventDefault();const email=$('emailInput').value,password=$('passwordInput').value;try{let r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password}),credentials:'same-origin'});if(!r.ok)throw Error('Login failed. Check pilot credentials or account lockout.');const session=await api('/api/session');state.csrf=session.csrf;state.me=session.me;showRole();$('login').hidden=true;$('app').hidden=false;await refresh();}catch(err){$('loginError').textContent=err.message;}}
$('loginForm').addEventListener('submit',login);
const endpoint={customers:'customers',products:'products',catalogs:'catalogs',quotes:'quotes',invoices:'invoices',jobs:'jobs'};
async function refresh(){try{
    // Read effective permissions on every refresh, so changes made by an admin
    // take effect without requiring a new login.
    const sess=await api('/api/session');state.me=sess.me;state.csrf=sess.csrf;
    showRole();
    if(!allowed(state.tab))state.tab='overview';
    document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===state.tab));
    $('heading').textContent={overview:'Overview',customers:'Customer Records',products:'Product Library',catalogs:'Catalog Studio',quotes:'Quotes',invoices:'Invoices',jobs:'Production Jobs',staff:'Staff & Roles',files:'Private Test Files',security:'Security & Backups'}[state.tab];
    const resources=['dashboard','customers','products','catalogs','quotes','invoices','jobs','staff']
      .filter(x=>x==='dashboard'||allowed(x));
    // Clear records no longer available after an administrator revokes access.
    for(const name of ['customers','products','catalogs','quotes','invoices','jobs','staff'])
      if(!resources.includes(name))state[name]=[];
    const values=await Promise.all(resources.map(x=>api('/api/'+x)));
    resources.forEach((x,i)=>state[x]=values[i]);
    state.files=allowed('files')?await api('/api/private-files'):[];
    state.audit=allowed('security')&&state.tab==='security'?await api('/api/audit-summary'):[];
    render();
  }catch(err){note('Request failed: '+err.message,true)}}
function view(tab){if(!allowed(tab))return;state.tab=tab;document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));$('heading').textContent={overview:'Overview',customers:'Customer Records',products:'Product Library',catalogs:'Catalog Studio',quotes:'Quotes',invoices:'Invoices',jobs:'Production Jobs',staff:'Staff & Roles',files:'Private Test Files',security:'Security & Backups'}[tab];note('');refresh();}
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>view(b.dataset.tab)));
const card=(label,value)=>`<div class="metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
function table(headers,rows){return `<div class="tableWrap"><table><thead><tr>${headers.map(h=>'<th>'+esc(h)+'</th>').join('')}</tr></thead><tbody>${rows.join('')||`<tr><td colspan="${headers.length}">No fictional records yet.</td></tr>`}</tbody></table></div>`}
const td=s=>`<td>${s}</td>`;
function optionRows(list,key,label){return list.map(a=>`<option value="${esc(a[key])}">${esc(a[label])}</option>`).join('')}
async function post(path,data,success){try{const d=await api(path,data);note(success||'Saved successfully.');await refresh();return d}catch(e){note(e.message,true);return null}}
const submit=(form,fn)=>{document.querySelector(form)?.addEventListener('submit',async e=>{e.preventDefault();await fn(Object.fromEntries(new FormData(e.currentTarget)))})};
const byId=(name,id)=>state[name].find(x=>Number(x.id)===Number(id));
function render(){if(!state.csrf)return;const target=$('view');if(state.tab==='overview')return target.innerHTML=overview();if(state.tab==='customers'){target.innerHTML=customers();wireCustomers()}if(state.tab==='products')target.innerHTML=products();if(state.tab==='catalogs'){target.innerHTML=catalogs();wireCatalogs()}if(state.tab==='quotes'){target.innerHTML=quotes();wireQuotes()}if(state.tab==='invoices'){target.innerHTML=invoices();wireInvoices()}if(state.tab==='jobs'){target.innerHTML=jobs();wireJobs()}if(state.tab==='staff'){target.innerHTML=staffView();wireStaff()}if(state.tab==='files'){target.innerHTML=filesView();wireFiles()}if(state.tab==='security'){target.innerHTML=securityView()}}
function overview(){const d=state.dashboard||{};
  let items=d.jobs===undefined?[]:[card('Production jobs',d.jobs||0)];
  for(const [key,label] of [['customers','Fictional customers'],['products','Products'],
    ['catalogs','Catalogs'],['quotes','Quotes'],['invoices','Invoices']]){
      if(d[key]!==undefined)items.push(card(label,d[key]));
    }
  if(d.open_cents!==undefined)items.push(card('Outstanding TEST balances',money(d.open_cents)));
  return `<div class="grid">${items.join('')}</div><div class="panel"><h2>Individual permissions · staging</h2><p>Signed in as <strong>${esc(state.me.full_name)}</strong>. An Administrator can grant or deny individual quote and invoice permissions without changing this person's staff role.</p><div class="note"><strong>Fictional data only:</strong> This is a public HTTPS staging pilot using fictional Supabase PostgreSQL records only. Do not enter real clients, real staff identities, or production credentials; email delivery is disabled.</div></div>`}

function customers(){return `<div class="cols"><section class="panel"><h2>Add fictional customer</h2><p>Names must start with TEST, SYNTH, or FICTIONAL. Emails must end in @example.invalid.</p><form id="customerForm" class="formGrid"><label class="wide">Customer name<input name="name" value="TEST Sample Business" required maxlength="120"></label><label class="wide">Email<input name="email" value="office@example.invalid" type="email" required></label><button type="submit">Add fictional customer</button></form></section><section class="panel"><h2>Add contact to a customer</h2><form id="contactForm" class="formGrid"><label class="wide">Company<select name="customer_id">${optionRows(state.customers,'id','name')}</select></label><label>First name<input name="first_name" value="Fictional" required></label><label>Last name<input name="last_name" value="Buyer" required></label><label class="wide">Email<input name="email" type="email" value="buyer@example.invalid" required></label><button>Add contact</button></form></section></div><div class="panel"><h2>Customers in PostgreSQL</h2>${table(['ID','Company','Email','Credit terms'],state.customers.map(c=>`<tr>${td(esc(c.id))}${td(esc(c.name))}${td(esc(c.email))}${td(esc(c.terms_days)+' days')}</tr>`))}</div>`}
function wireCustomers(){if(!permit('customers.create'))document.querySelectorAll('#customerForm input,#customerForm select,#customerForm button,#contactForm input,#contactForm select,#contactForm button').forEach(el=>el.disabled=true);submit('#customerForm',async f=>post('/api/customers',f,'Fictional customer created in PostgreSQL.'));submit('#contactForm',async f=>post('/api/customers/'+Number(f.customer_id)+'/contacts',f,'Fictional contact saved.'))}
function products(){return `<div class="panel"><h2>Products in the pilot schema</h2><p>Prices are intentionally fictional. The product configurator and supplier-image importing remain in your local v0.7.1 app until further cloud conversion.</p>${table(['SKU','Product','Category','Sample unit price','Methods'],state.products.map(p=>`<tr>${td(esc(p.sku))}${td(esc(p.name))}${td(esc(p.category))}${td(money(p.base_cents))}${td(esc(JSON.parse(p.methods_json||'[]').join(' / ')))}</tr>`))}</div>`}
function catalogs(){const p=state.products[0], methods=p?JSON.parse(p.methods_json||'[]'):[];return `<div class="panel"><h2>Create a fictional client catalog</h2><p>Choose the product, finish, branding location and manual selling price. These selections are saved to PostgreSQL and passed to the quote and production ticket.</p><form id="catalogForm" class="formGrid"><label>Customer<select name="customer_id">${optionRows(state.customers,'id','name')}</select></label><label>Product<select name="product_id" id="productSelect">${optionRows(state.products,'id','name')}</select></label><label class="wide">Catalog title<input name="title" value="TEST Executive Gift Selection" required></label><label>Finish<select name="method" id="methodSelect">${methods.map(x=>`<option>${esc(x)}</option>`).join('')}</select></label><label>Branding location<select name="logo_location"><option>Cover center</option><option>Upper left</option><option>Bottom right</option><option>Center chest</option><option>Left chest</option><option>Back</option></select></label><label>Quantity<input type="number" name="quantity" min="1" max="10000" value="5"></label><label>Selling price per item (BSD)<input name="unit_price" type="number" min="0" max="1000000" step="0.01" value="25.00"></label><button>Create Catalog</button></form></div><div class="panel"><h2>Saved catalogs</h2>${table(['Catalog','Client','Product selection','Created'],state.catalogs.map(c=>`<tr>${td('#'+c.id+' · '+esc(c.title))}${td(esc(byId('customers',c.customer_id)?.name||c.customer_id))}${td(esc(JSON.parse(c.lines_json)[0]?.name||'')+' · '+esc(JSON.parse(c.lines_json)[0]?.method||''))}${td(esc(c.created_at).slice(0,10))}</tr>`))}</div>`}
function wireCatalogs(){if(!permit('catalogs.create'))document.querySelectorAll('#catalogForm input,#catalogForm select,#catalogForm button').forEach(el=>el.disabled=true);const select=$('productSelect');select?.addEventListener('change',()=>{const p=byId('products',select.value);if(!p)return;$('methodSelect').innerHTML=JSON.parse(p.methods_json||'[]').map(m=>`<option>${esc(m)}</option>`).join('');document.querySelector('[name="unit_price"]').value=(p.base_cents/100).toFixed(2)});submit('#catalogForm',async f=>{const cents=Math.round(Number(f.unit_price)*100);await post('/api/catalogs',{customer_id:Number(f.customer_id),product_id:Number(f.product_id),title:f.title,method:f.method,logo_location:f.logo_location,quantity:Number(f.quantity),unit_cents:cents},'Fictional catalog saved to PostgreSQL.')})}
function quotes(){return `<div class="panel"><h2>Generate a draft quote from catalog</h2><p>The PostgreSQL server recalculates the total from the stored catalog lines—not from a browser-submitted total.</p><form id="quoteForm" class="formGrid"><label class="wide">Catalog<select name="catalog_id">${state.catalogs.map(c=>`<option value="${c.id}">${esc(c.title)} — #${c.id}</option>`).join('')}</select></label><button ${state.catalogs.length?'':'disabled'}>Create Draft Quote</button></form></div><div class="panel"><h2>Quotes</h2>${table(['Number','Amount','Status','Actions'],state.quotes.map(q=>`<tr>${td(documentButton("quotes",q,q.number))}${td(money(q.total_cents))}${td(`<span class="chip">${esc(q.status)}</span>`)}${td(documentButton('quotes',q,'View details')+' '+(q.status==='draft'&&permit('quotes.approve')?`<button class="slim" data-approve="${q.id}">Approve → Invoice + Job</button>`:'—'))}</tr>`))}</div>`}
function wireQuotes(){wireDocuments();if(!permit('quotes.create'))document.querySelectorAll('#quoteForm input,#quoteForm select,#quoteForm button').forEach(el=>el.disabled=true);submit('#quoteForm',async f=>post('/api/quotes',{catalog_id:Number(f.catalog_id)},'Draft quote created in PostgreSQL.'));document.querySelectorAll('[data-approve]').forEach(b=>b.addEventListener('click',async()=>{if(!confirm('Approve this FICTIONAL quote? The pilot will create a draft invoice and job in one PostgreSQL transaction.'))return;await post('/api/quotes/'+b.dataset.approve+'/approve',{},'Approved! Draft invoice and production ticket created atomically.')}))}
function invoices(){return `<div class="panel"><h2>Invoices · fictional only</h2><p>Issue a synthetic invoice, then record a fictional payment. No emails or tax-compliant invoices are produced.</p>${table(['Invoice','Total','Paid','Open balance','Status','Action'],state.invoices.map(i=>{const balance=i.total_cents-i.paid_cents;return `<tr>${td(documentButton("invoices",i,i.number))}${td(money(i.total_cents))}${td(money(i.paid_cents))}${td(money(balance))}${td(`<span class="chip">${esc(i.status)}</span>`)}${td(documentButton('invoices',i,'View details')+' '+(i.status==='draft'&&permit('invoices.issue')?`<button class="slim" data-issue="${i.id}">Issue Test Invoice</button>`:i.status==='issued'&&balance>0&&permit('payments.record')?`<button class="slim" data-payment="${i.id}">Record Test Payment</button>`:'—'))}</tr>`}))}</div>`}
function wireInvoices(){wireDocuments();document.querySelectorAll('[data-issue]').forEach(b=>b.addEventListener('click',async()=>{if(!confirm('Mark this FICTIONAL invoice as issued? No email will be sent.'))return;await post('/api/invoices/'+b.dataset.issue+'/issue',{confirm:'ISSUE SYNTHETIC'},'Test invoice marked issued.')}));document.querySelectorAll('[data-payment]').forEach(b=>b.addEventListener('click',async()=>{const amount=prompt('Fictional payment amount in BSD (e.g. 25.00):','25.00');if(amount===null)return;const cents=Math.round(Number(amount)*100);await post('/api/invoices/'+b.dataset.payment+'/payments',{amount_cents:cents},'Fictional payment recorded to PostgreSQL.')}))}
function jobs(){return `<div class="panel"><h2>Production tickets in PostgreSQL</h2><p>The ticket retains the approved quote's finish, quantity and placement. Updating a job's stage does not alter the approved sale.</p>${table(['Job','Original selection','Stage','Change stage','Assignment (Admin)'],state.jobs.map(j=>{const x=JSON.parse(j.ticket_json||'{}');const item=x.lines?.[0]||{};return `<tr>${td(esc(j.number))}${td(`${esc(item.quantity||'')} × ${esc(item.name||j.title)}<br><span class="detail">${esc(item.method||'')} · ${esc(item.logo_location||'')}</span>`)}${td(`<span class="chip">${esc(j.status)}</span>`)}${td(`<div class="control"><select data-select-job="${j.id}">${['new','design','proof','production','installation','completed','on_hold'].map(s=>`<option value="${s}" ${s===j.status?'selected':''}>${esc(s)}</option>`).join('')}</select><button class="slim" data-save-stage="${j.id}">Save</button></div>`)}${td(state.me.role==='admin'?`<div class="control"><select data-assign-job="${j.id}">${state.staff.filter(x=>x.active).map(u=>`<option value="${u.id}" ${Number(j.assigned_to_user_id)===Number(u.id)?'selected':''}>${esc(u.full_name)}</option>`).join('')}</select><button class="slim" data-save-assign="${j.id}">Assign</button></div>`:esc(j.assigned_to_user_id||'Unassigned'))}</tr>`}))}</div>`}
function wireJobs(){if(!permit('jobs.update')){document.querySelectorAll('[data-save-stage]').forEach(b=>b.disabled=true)}document.querySelectorAll('[data-save-stage]').forEach(b=>b.addEventListener('click',async()=>{const id=b.dataset.saveStage,stage=document.querySelector(`[data-select-job="${id}"]`).value;await post('/api/jobs/'+id+'/stage',{stage},'Production stage updated in PostgreSQL.')}));document.querySelectorAll('[data-save-assign]').forEach(b=>b.addEventListener('click',async()=>{const id=b.dataset.saveAssign,staff=Number(document.querySelector(`[data-assign-job="${id}"]`).value);await post('/api/jobs/'+id+'/assign',{staff_id:staff},'Fictional production job assigned to staff.')}))}
(async()=>{try{let session=await api('/api/session');state.csrf=session.csrf;state.me=session.me;showRole();$('login').hidden=true;$('app').hidden=false;await refresh()}catch{}})();

function staffView(){const count=state.staff.filter(u=>u.active).length;
 const edit=state.permissionDetail;
 let editor='';
 if(edit){const target=edit.user;
   editor=`<section class="panel"><h2>Individual permissions: ${esc(target.full_name)}</h2><p><strong>${esc(target.email||'')}</strong> · ${esc(target.role)} · choose <strong>Role default</strong>, <strong>Allow</strong>, or <strong>Deny</strong> independently for each capability. No live customer records are used.</p>`;
   if(target.role==='admin')editor+='<div class="note">Administrator access cannot be overridden in this pilot.</div>';
   else editor+=`<form id="permissionForm" class="formGrid">${state.permissionCatalog.permissions.map(x=>{
     const key=x.key, override=edit.overrides[key],value=override===true?'allow':override===false?'deny':'inherit';
     const defaultText=edit.defaults[key]?'Allowed':'Denied';
     return `<label class="wide">${esc(x.label)} <span class="detail">(role default: ${defaultText})</span><select data-permission-key="${esc(key)}"><option value="inherit" ${value==='inherit'?'selected':''}>Role default</option><option value="allow" ${value==='allow'?'selected':''}>Allow</option><option value="deny" ${value==='deny'?'selected':''}>Deny</option></select></label>`;
   }).join('')}<button type="submit">Save individual permissions</button><button type="button" class="alt" id="cancelEditPermissions">Close</button></form>`;
   editor+='</section>';
 }
 return `<div class="cols"><section class="panel"><h2>Add fictional staff account</h2><p>Up to five active users including admin. Test emails must end in @example.invalid, with unique 14+ character passwords.</p><form id="staffForm" class="formGrid"><label class="wide">Name<input name="full_name" required value="Fictional Staff Member" maxlength="100"></label><label class="wide">Email<input name="email" type="email" required value="sales@example.invalid"></label><label>Role<select name="role"><option value="sales">Sales</option><option value="production">Production</option><option value="office">Office</option><option value="admin">Administrator</option></select></label><label>Password<input name="password" type="password" minlength="14" maxlength="128" required autocomplete="new-password"></label><button ${count>=5?'disabled':''}>Create staff (${count}/5)</button></form></section><section class="panel"><h2>Role defaults + individual overrides</h2><p>Roles provide starting access. For any non-admin employee, choose <strong>Edit access</strong> to override quote viewing, quote creation, approval, invoice viewing, issuance, and payment entry.</p><p>Changes are enforced by the server on the very next request. Users cannot edit their own permissions.</p><div class="note">Administrator retains full control. This staging version does not send customer emails.</div></section></div><section class="panel"><h2>Staff accounts</h2>${table(['Name','Email','Role','Status','Permissions / account'],state.staff.map(u=>`<tr>${td(esc(u.full_name))}${td(esc(u.email))}${td(esc(u.role))}${td(u.active?'Active':'Inactive')}${td(`${u.active?`<button class="slim" data-edit-permissions="${u.id}">Edit access</button> `:''}${u.active&&u.id!==state.me.id?`<button class="slim" data-deactivate="${u.id}">Deactivate</button>`:''}`)}</tr>`))}</section>${editor}`
}
async function editPermissions(id){try{
  const [catalog,detail]=await Promise.all([api('/api/permission-catalog'),api('/api/staff/'+id+'/permissions')]);
  state.permissionCatalog=catalog;state.permissionDetail=detail;render();
  $('permissionForm')?.scrollIntoView({behavior:'smooth',block:'nearest'});
}catch(e){note('Could not load permissions: '+e.message,true)}}
function wireStaff(){submit('#staffForm',async f=>post('/api/staff',f,'Fictional staff account created.'));
 document.querySelectorAll('[data-edit-permissions]').forEach(b=>b.addEventListener('click',()=>editPermissions(Number(b.dataset.editPermissions))));
 document.querySelectorAll('[data-deactivate]').forEach(b=>b.addEventListener('click',async()=>{
   if(!confirm('Deactivate this FICTIONAL staff account?'))return;
   await post('/api/staff/'+b.dataset.deactivate+'/deactivate',{},'Account deactivated.');
   state.permissionDetail=null;
 }));
 $('cancelEditPermissions')?.addEventListener('click',()=>{state.permissionDetail=null;render()});
 $('permissionForm')?.addEventListener('submit',async e=>{e.preventDefault();const overrides={};
   document.querySelectorAll('[data-permission-key]').forEach(sel=>{
     if(sel.value!=='inherit')overrides[sel.dataset.permissionKey]=sel.value==='allow';
   });
   const id=state.permissionDetail.user.id;
   const result=await post('/api/staff/'+id+'/permissions',{overrides},'Individual permissions saved in PostgreSQL.');
   if(result)await editPermissions(id);
 });
}
$('logoutButton').addEventListener('click',async()=>{try{await api('/api/logout',{})}catch{}state.csrf='';state.me=null;$('app').hidden=true;$('login').hidden=false;$('passwordInput').value='';});


function filesView(){return `<div class="panel"><h2>Private test files · fictional staging only</h2><p>Store only synthetic sample PDFs or generated sample PNG/JPEG previews, with names beginning <code>TEST_</code>. Maximum 2 MB per file, 50 files and 40 MB in this pilot. Private bucket is not a full document-management workflow.</p>${permit('files.upload')?`<form id="fileForm" class="formGrid"><label class="wide">Select a fictional TEST_ file<input type="file" id="testFile" accept=".pdf,.png,.jpg,.jpeg" required></label><button type="submit">Upload private test file</button></form>`:'<p>Your account cannot upload test files.</p>'}<p class="detail">The storage feature requires a private Supabase bucket and separate encrypted DigitalOcean runtime configuration. If not configured, uploads return STORAGE_NOT_CONFIGURED.</p></div><div class="panel"><h2>Test file inventory</h2>${table(['File','Size','SHA-256','Uploaded','Action'],state.files.map(f=>`<tr>${td(esc(f.original_name))}${td(esc(f.size_bytes)+' bytes')}${td(esc((f.sha256||'').slice(0,16))+'…')}${td(esc(f.created_at))}${td(`<a href="/api/private-files/${f.id}/download">Download privately</a>`)}</tr>`))}</div>`}
function wireFiles(){document.querySelector('#fileForm')?.addEventListener('submit',async e=>{
  e.preventDefault();const input=$('testFile'),f=input?.files?.[0];if(!f)return;
  if(!/^TEST_[A-Za-z0-9_.-]{1,85}$/.test(f.name)||!f.size||f.size>2_000_000){note('Use fictional TEST_ filename, max 2 MB.',true);return}
  const ext=f.name.toLowerCase().split('.').at(-1);
  const mime=ext==='pdf'?'application/pdf':ext==='png'?'image/png':['jpg','jpeg'].includes(ext)?'image/jpeg':'';
  if(!mime){note('Only PDF, PNG or JPEG allowed',true);return}
  try{const b64=await new Promise((resolve,reject)=>{const fr=new FileReader();fr.onload=()=>resolve(String(fr.result).split(',')[1]);fr.onerror=()=>reject(Error('FILE_READ_FAILED'));fr.readAsDataURL(f)});
      await post('/api/private-files',{filename:f.name,mime,base64:b64},'Private fictional test file saved and checksum recorded.');
  }catch(err){note('Upload failed: '+err.message,true)}
})}
function securityView(){return `<div class="panel"><h2>Security and encrypted backup rehearsal</h2><p>Use <strong>BACKUP_ENCRYPTED_WINDOWS.bat</strong> locally to create an AES-256-GCM encrypted snapshot of the fictional commercial workflow. Verify it with <strong>VERIFY_ENCRYPTED_BACKUP_WINDOWS.bat</strong>, then restore into a <em>new isolated rehearsal schema</em> using the separate Windows script.</p><div class="note">No automatic backups are enabled in the pilot. These snapshots exclude user password/session tables and Supabase Storage object bytes; they are <strong>not</strong> a complete disaster-recovery backup.</div></div><div class="panel"><h2>Recent audit actions · administrator only</h2>${table(['UTC','Actor ID','Action','Entity','Record ID'],state.audit.map(a=>`<tr>${td(esc(a.created_at))}${td(esc(a.actor_user_id??'system'))}${td(esc(a.action))}${td(esc(a.entity))}${td(esc(a.entity_id??''))}</tr>`))}</div>`}

// Read-only views use the existing permission-checked list APIs.
function documentButton(kind,row,label){return `<button type="button" class="slim" data-document="${kind}" data-document-id="${esc(row.id)}">${esc(label)}</button>`}
function documentDetails(kind,row){
  let lines;try{lines=JSON.parse(row.lines_json||'null')}catch{lines=null}
  const items=Array.isArray(lines)?table(['Item','Finish','Placement','Quantity','Unit price','Line total'],lines.map(l=>`<tr>${td(esc(l.name))}${td(esc(l.method))}${td(esc(l.logo_location))}${td(esc(l.quantity))}${td(money(l.unit_cents))}${td(money(Number(l.quantity)*Number(l.unit_cents)))}</tr>`)):'<p>Saved line items are unavailable.</p>';
  const client=byId('customers',row.customer_id);
  return `<h2>${kind==='quotes'?'Quote':'Invoice'} ${esc(row.number)}</h2><p>Fictional staging document</p><p>Customer: ${esc(client?.name||('Customer #'+row.customer_id))}</p><p>Status: ${esc(row.status)} · Created: ${esc(row.created_at)}</p>${items}<p><strong>Total: ${money(row.total_cents)}</strong></p>${kind==='invoices'?`<p>Paid: ${money(row.paid_cents)} · Open balance: ${money(row.total_cents-row.paid_cents)}</p><p>Due date: ${esc(row.due_date||'Not set')}</p>`:''}`;
}
function wireDocuments(){document.querySelectorAll('[data-document]').forEach(button=>button.addEventListener('click',async()=>{
  const kind=button.dataset.document,id=button.dataset.documentId;
  try{
    // Fetch again to enforce current permissions and display current balances.
    const rows=await api('/api/'+kind),row=rows.find(r=>Number(r.id)===Number(id));
    if(!row)throw Error('Document no longer available.');
    const dialog=document.createElement('dialog');
    dialog.style.cssText='width:min(950px,90vw);max-height:85vh;overflow:auto;border:1px solid #ccd3df;border-radius:12px;padding:24px';
    dialog.innerHTML='<button type="button" data-close>Close details</button>'+documentDetails(kind,row)+`<p><a href="/documents/${kind}/${Number(row.id)}" target="_blank" rel="noopener">Open printable test preview</a></p>`;
    document.body.appendChild(dialog);
    dialog.querySelector('[data-close]').addEventListener('click',()=>dialog.close());
    dialog.addEventListener('close',()=>{dialog.remove();button.focus()},{once:true});
    dialog.showModal();
  }catch(err){note('Unable to open document: '+err.message,true)}
}))}
