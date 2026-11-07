'use strict';
const el=id=>document.getElementById(id);
const fields=['code','name','category','description','unit','unit_price','vat_rate','finish','placement'];
let me=null,record=null,page=1,total=0,busy=false,dirty=false;
const can=k=>me?.role==='admin'||me?.permissions?.[k]===true;
const errors={PRODUCT_HISTORY_LIMIT:'The catalogue has reached its change-history limit. Contact your administrator before making further changes.',VERSION_CONFLICT:'This product changed in another session. Your changes are still here. Copy them before reloading the saved product.',PRODUCT_CODE_EXISTS:'That product code is already in use, including archived products. Choose a unique code.',INVALID_PRODUCT:'Check the product code, required fields, selling price and VAT rate.',PRODUCT_LIMIT:'The catalogue has reached its limit of 5,000 products.',NOT_FOUND:'This product could not be found. Refresh the catalogue.'};
function status(message,kind='info',focus=false){
 el('status').textContent=message;
 if(!el('edit').hidden){el('edit-status').textContent=message;const box=el('save-status');box.hidden=false;box.textContent=message;box.dataset.kind=kind;box.setAttribute('role',kind==='error'?'alert':'status');if(focus){box.focus();box.scrollIntoView?.({block:'nearest'});}}
 else if(focus){el('status').setAttribute('tabindex','-1');el('status').focus();el('status').scrollIntoView?.({block:'nearest'});}
}
function clear(){me=null;record=null;dirty=false;el('workspace').hidden=true;el('edit').hidden=true;el('rows').replaceChildren();for(const k of fields)el('p-'+k).value='';el('identity').textContent='';el('heading').textContent='';el('revision').textContent='';el('edit-status').textContent='';el('save-status').textContent='';el('save-status').hidden=true;el('count').textContent='';el('active').checked=false;el('search').value='';}
const safeCodes=new Set([...Object.keys(errors),'INVALID_REQUEST','INVALID_PROVIDER_RESPONSE','REQUEST_FAILED','REQUEST_REJECTED','PROVIDER_REQUEST_FAILED','PROVIDER_UNAVAILABLE','RESPONSE_TOO_LARGE','CUSTOMERS_NOT_ENABLED','PLEASE_WAIT_AND_TRY_AGAIN']);
async function api(path,body){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
 try{
  let r;try{r=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});}catch{throw Error(controller.signal.aborted?'The request timed out. A save may still have completed. Search for this product code before retrying. Code: PRODUCT_REQUEST_TIMEOUT.':'The connection failed. The save is not confirmed. Keep your entries and search for this product code before retrying. Code: PRODUCT_CONNECTION_FAILED.');}
  let d;try{d=await r.json();}catch{if(r.status===401||r.status===403)clear();throw Error('The response could not be read (HTTP '+r.status+'). A save is not confirmed. Code: PRODUCT_RESPONSE_UNREADABLE.');}
  if(!r.ok){if(r.status===401||r.status===403){clear();throw Error('Product access ended. Return to Workspace to sign in.');}const code=safeCodes.has(d?.error)?d.error:'PRODUCT_REQUEST_FAILED';throw Error((errors[code]||'The save is not confirmed. Keep your entries and search for this product code before retrying.')+' Code: '+code+' (HTTP '+r.status+').');}
  return d;
 }finally{clearTimeout(timer);}
}
function controls(){const editable=can(record?.version?'products.edit':'products.create');el('fields').disabled=busy||!editable;el('save').hidden=!editable;el('save').disabled=busy;el('new').hidden=!can('products.create');el('duplicate').hidden=!record?.version||!can('products.create');el('reload').hidden=!record?.version;el('prev').disabled=busy||page===1;el('next').disabled=busy||page*50>=total;el('backup-link').hidden=me?.role!=='admin';el('quotes-link').hidden=!can('quotes.view');}
async function run(fn){if(busy)return;busy=true;document.querySelectorAll('button,input,select,textarea').forEach(e=>e.disabled=true);try{await fn();}catch(e){status(e.message||'The action could not complete. Code: PRODUCT_ACTION_FAILED.','error',true);}finally{busy=false;el('save').textContent='Save product';document.querySelectorAll('button,input,select,textarea').forEach(e=>e.disabled=false);controls();}}
function leave(){return !dirty||window.confirm('Discard your unsaved product changes?');}
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
async function list(){const r=await api('/api/products?q='+encodeURIComponent(el('search').value)+'&state='+el('state').value+'&page='+page);total=r.total;el('rows').replaceChildren();for(const p of r.data){const tr=document.createElement('tr');for(const v of [p.data.code+' · '+p.data.name,p.data.category,p.data.unit_price+' / '+p.data.unit,p.data.vat_rate+'%',p.active?'Active':'Archived']){const td=document.createElement('td');td.textContent=v;tr.append(td);}const td=document.createElement('td'),b=document.createElement('button');b.textContent='Open';b.type='button';b.onclick=()=>run(async()=>{if(!leave())return;fill((await api('/api/products/'+p.id)).data);status('Saved product opened.');});td.append(b);tr.append(td);el('rows').append(tr);}el('count').textContent=r.total+' products · Page '+page;controls();}
function fill(p){record=p;for(const k of fields)el('p-'+k).value=p.data[k]??'';el('active').checked=p.active;el('edit').hidden=false;el('heading').textContent=p.version?p.data.name:'New product';el('revision').textContent=p.version?'Saved · revision '+p.version:'Unsaved';el('edit-status').textContent='';el('save-status').hidden=true;el('save-status').textContent='';dirty=false;controls();}
function fresh(source){fill({id:crypto.randomUUID(),version:0,active:true,data:source?{...source.data,code:''}:{unit:'Each'}});dirty=true;status(source?'Choose a unique code for this copy, then save.':'Enter the product details, selling price and VAT rate.');}
el('new').onclick=()=>{if(leave())fresh();};el('duplicate').onclick=()=>{if(leave())fresh(record);};
el('fields').oninput=()=>{dirty=true;status('Unsaved changes. Click Save product to apply them.');};
const fieldLabels={code:'Product code',name:'Product name',category:'Category',description:'Description',unit:'Unit',unit_price:'Selling price',vat_rate:'VAT rate',finish:'Finish / branding method',placement:'Placement'};
const fieldLimits={code:40,name:160,category:80,description:800,unit:20,finish:160,placement:160};
function validatedProduct(){
 const data={};
 for(const k of fields){
  const input=el('p-'+k),v=input.value.trim(),label=fieldLabels[k];
  if(['code','name','unit','unit_price','vat_rate'].includes(k)&&!v)throw Error(label+': enter a value before saving.');
  if(k==='code'&&!/^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$/.test(v))throw Error('Product code: use letters, numbers, dots, underscores or ordinary hyphens, for example TEST-CAT-105.');
  if(fieldLimits[k]&&v.length>fieldLimits[k])throw Error(label+': use no more than '+fieldLimits[k]+' characters.');
  if(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/.test(v)||k!=='description'&&/[\t\r\n]/.test(v))throw Error(label+': remove line breaks or control characters.');
  if(k==='unit_price'||k==='vat_rate'){
   const max=k==='unit_price'?1000000:100;
   if(input.validity.badInput||!/^[0-9]{1,7}(\.[0-9]{1,2})?$/.test(v)||Number(v)>max)throw Error(label+': enter a number from 0 to '+max+' with at most two decimal places, for example 10.00.');
  }
  data[k]=v;
 }
 return data;
}
function savedMatches(saved,payload){
 return saved&&saved.id===payload.id&&Number.isInteger(saved.version)&&saved.version>=1&&[payload.version,payload.version+1].includes(saved.version)&&saved.active===payload.active&&saved.data&&fields.every(k=>typeof saved.data[k]==='string'&&(k==='unit_price'||k==='vat_rate'?Number(saved.data[k])===Number(payload.data[k]):saved.data[k]===payload.data[k]));
}
el('edit').onsubmit=e=>{
 e.preventDefault();if(busy)return;
 if(!record){status('Open New product or a saved product before saving.','error',true);return;}
 if(!can(record.version?'products.edit':'products.create')){status('Your account does not have permission to save this product.','error',true);return;}
 let payload;try{payload={op:'save',id:record.id,version:record.version,active:el('active').checked,data:validatedProduct()};}catch(error){status(error.message,'error',true);return;}
 run(async()=>{
  el('save').textContent='Saving…';status('Saving product…');
  const r=await api('/api/products/save',payload);
  if(!savedMatches(r?.data,payload))throw Error('The server did not confirm the saved values. Keep your entries and search for this product code before retrying. Code: PRODUCT_SAVE_RESPONSE.');
  fill(r.data);status('Product saved · revision '+r.data.version+'.','success',true);
  try{await list();if(me)status('Product saved · revision '+r.data.version+'.','success');}catch(error){if(me)status('Product saved, but the list could not refresh. Use Refresh catalogue.','success',true);else status(error.message,'error',true);}
 });
};
el('reload').onclick=()=>run(async()=>{if(record?.version&&leave()){fill((await api('/api/products/'+record.id)).data);status('Reloaded the saved product.');}});
el('close').onclick=()=>{if(leave()){dirty=false;record=null;el('edit').hidden=true;controls();}};
el('search-button').onclick=()=>run(async()=>{page=1;await list();});el('state').onchange=()=>run(async()=>{page=1;await list();});
el('prev').onclick=()=>run(async()=>{if(page>1){page--;await list();}});el('next').onclick=()=>run(async()=>{if(page*50<total){page++;await list();}});
el('refresh').onclick=()=>run(async()=>{await list();status(dirty?'Catalogue refreshed. Your unsaved product changes are still here.':'Catalogue refreshed.');});
el('logout').onclick=()=>run(async()=>{if(!leave())return;clear();await api('/api/logout',{});status('Signed out.');});
run(async()=>{const r=await api('/api/session');me=r.me;if(!r.crm_enabled||!can('products.view')){clear();throw Error('Product catalogue access is required. Return to Workspace.');}el('workspace').hidden=false;el('identity').textContent=me.email;await list();status('Choose a product or add a new one.');});
