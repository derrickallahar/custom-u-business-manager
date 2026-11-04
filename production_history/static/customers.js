'use strict';
const el=id=>document.getElementById(id);
const fields={c:['name','email','phone','address','tax_id'],p:['name','title','email','phone']};
let customer=null,contact=null,page=1,dirty=false,busy=false,epoch=0;
const errors={VERSION_CONFLICT:'This record changed in another window. Reopen it before saving again.',ID_CONFLICT:'This save conflicts with an existing record. Reopen the customer.',CUSTOMER_INACTIVE:'Activate and save the customer before adding or editing contacts.',NAME_REQUIRED:'Enter a name.',INVALID_EMAIL:'Check the email address.',CUSTOMERS_NOT_ENABLED:'Customer management has not been enabled yet.'};
function status(s){el('status').textContent=s;}
function clearPrivate(){epoch++;customer=contact=null;dirty=false;el('workspace').hidden=true;el('rows').replaceChildren();el('contact-list').replaceChildren();el('customer-form').reset();el('contact-form').reset();el('identity').textContent='';}
async function api(url,body){
 const r=await fetch(url,{credentials:'same-origin',cache:'no-store',method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});
 const data=await r.json();
 if(!r.ok){if(r.status===401||r.status===403){clearPrivate();throw Error('Access ended. Use the sign-in link above.');}throw Error(errors[data.error]||'The request could not be completed. Your unsaved entries are still in the form.');}
 return data;
}
function fill(prefix,record){for(const f of fields[prefix])el(prefix+'-'+f).value=record.data[f]||'';el(prefix+'-active').checked=record.active;}
function draft(kind){return {id:crypto.randomUUID(),kind,version:0,data:{},active:true};}
function mayLeave(){return !dirty||window.confirm('Discard unsaved changes?');}
function showCustomer(row){customer=row;contact=null;fill('c',row);el('customer-form').hidden=false;el('customer-heading').textContent=row.version?'Edit customer':'New customer';el('contact-form').hidden=true;el('contacts').hidden=!row.version;el('new-contact').disabled=!row.active;dirty=false;}
function showContacts(rows){el('contact-list').replaceChildren();for(const r of rows){const p=document.createElement('p'),b=document.createElement('button');b.textContent=r.data.name+(r.active?'':' (inactive)');b.disabled=!customer.active;b.onclick=()=>{if(!mayLeave())return;contact=r;fill('c',customer);el('customer-form').hidden=true;fill('p',r);el('contact-form').hidden=false;dirty=false;};p.append(b);el('contact-list').append(p);}if(!rows.length)el('contact-list').textContent='No contacts added yet.';}
async function list(){const ticket=epoch;const r=await api('/api/customers?'+new URLSearchParams({q:el('search').value,page:String(page)}));if(ticket!==epoch)return;el('rows').replaceChildren();for(const row of r.data){const tr=document.createElement('tr');for(const value of [row.data.name,row.active?'Active':'Inactive']){const td=document.createElement('td');td.textContent=value;tr.append(td);}const td=document.createElement('td'),b=document.createElement('button');b.textContent='Open';b.onclick=()=>run(async()=>{if(!mayLeave())return;await openCustomer(row.id);});td.append(b);tr.append(td);el('rows').append(tr);}el('count').textContent=r.total+' customers · Page '+page;el('prev').disabled=page===1;el('next').disabled=page*50>=r.total;}
async function openCustomer(id){const ticket=epoch;const r=await api('/api/customers/'+encodeURIComponent(id));if(ticket!==epoch)return;showCustomer(r.data);showContacts(r.contacts);}
async function run(action){if(busy)return;busy=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);try{await action();}catch(e){status(e.message);}finally{busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);el('prev').disabled=page===1;el('next').disabled=page*50>=Number(el('count').textContent.split(' ')[0]);el('new-contact').disabled=!customer?.active;}}
function payload(prefix,row,op){const data={};for(const f of fields[prefix])data[f]=el(prefix+'-'+f).value.trim();const p={op,id:row.id,version:row.version,active:el(prefix+'-active').checked,data};if(prefix==='p')p.customer_id=customer.id;return p;}
el('new-customer').onclick=()=>{if(!mayLeave())return;showCustomer(draft('customer'));el('c-name').focus();status('Enter the new customer details.');};
el('new-contact').onclick=()=>{if(!mayLeave())return;contact=draft('contact');fill('c',customer);el('customer-form').hidden=true;fill('p',contact);el('contact-form').hidden=false;dirty=false;el('p-name').focus();};
for(const prefix of ['c','p']){const form=el(prefix==='c'?'customer-form':'contact-form');form.oninput=()=>{dirty=true;};form.onsubmit=e=>{e.preventDefault();run(async()=>{const row=prefix==='c'?customer:contact;if(!row)return;const id=prefix==='c'?row.id:customer.id;const ticket=epoch;await api('/api/customers/save',payload(prefix,row,prefix==='c'?'save_customer':'save_contact'));if(ticket!==epoch)return;dirty=false;await openCustomer(id);await list();status(prefix==='c'?'Customer saved.':'Contact saved.');});};}
el('search-button').onclick=()=>run(async()=>{page=1;await list();});el('search').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();el('search-button').click();}};
el('prev').onclick=()=>run(async()=>{page--;await list();});el('next').onclick=()=>run(async()=>{page++;await list();});
el('logout').onclick=()=>run(async()=>{if(!mayLeave())return;clearPrivate();await api('/api/logout',{});status('Signed out. Use the sign-in link above to return.');});
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
run(async()=>{const r=await api('/api/session');if(!r.crm_enabled){status(errors.CUSTOMERS_NOT_ENABLED);return;}el('identity').textContent=r.me.email;el('workspace').hidden=false;await list();status('Ready. Add customers for new work; archive records are not imported automatically.');});
