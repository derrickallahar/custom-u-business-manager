/* A fixed, owner-reviewed bundle. Uses the existing signed-in quote API only. */
(() => {
 'use strict';
 const BUNDLE_SHA256='9b38108ab87d9de94ea86d2b5dcffe8ebfb5b9951af318a6a6cf1acd8007e187';
 const el=id=>document.getElementById(id),same=(a,b)=>String(a||'').trim().toLowerCase()===String(b||'').trim().toLowerCase();
 let signed=false,busy=false,rows=[],ready=false;
 const money=c=>'BSD '+(c/100).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
 function node(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
 function status(text){el('status').textContent=text;}
 function controls(){el('preview').disabled=busy||!signed;el('source').disabled=busy||!signed;el('logout').disabled=busy;el('confirmed').disabled=busy||!ready;el('save').disabled=busy||!signed||!ready||!el('confirmed').checked||!rows.some(r=>r.state==='ready');}
 function clear(){signed=false;rows=[];ready=false;el('workspace').hidden=true;el('review').hidden=true;el('source').value='';el('confirmed').checked=false;el('items').replaceChildren();el('summary').textContent='';el('result').textContent='';el('identity').textContent='';controls();}
 async function request(path,body,optional=false){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),25000);
  try{
   let r;try{r=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});}catch{throw Error('The connection was interrupted. Review the same file again to check what was saved.');}
   if(r.status===401||r.status===403){clear();throw Error('Access ended. Return to Workspace to sign in.');}
   let data;try{data=await r.json();}catch{throw Error('The response could not be read (HTTP '+r.status+'). Review the same file again before retrying.');}
   if(optional&&r.status===404&&data?.error==='NOT_FOUND')return null;
   if(!r.ok)throw Error('The check or save was not confirmed (HTTP '+r.status+'). Review the same file again before retrying.');
   return data;
  }finally{clearTimeout(timer);}
 }
 async function access(){const session=await request('/api/session');if(!session.crm_enabled||session.me?.role!=='admin'){clear();throw Error('An administrator account is required for this reviewed import.');}signed=true;return session;}
 async function work(fn){if(busy)return;busy=true;controls();try{await fn();}catch(e){ready=false;el('confirmed').checked=false;status(e.message);if(signed)el('result').textContent=e.message;}finally{busy=false;controls();}}
 async function readFile(file){if(!file||file.size>250000)throw Error('Choose the reviewed JSON file supplied with update 114.8.');return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(Error('The file could not be read.'));r.readAsArrayBuffer(file);});}
 async function resolve(q){
  const previous=await request('/api/quotes/'+q.id,null,true);
  if(previous){if(previous.data?.id!==q.id||!previous.data.number)throw Error('The saved quote response could not be verified.');return {state:'kept',saved:previous.data,message:'Already saved — kept, including any later changes.'};}
  // Also detect manually carried quotes whose reference appears in number/title.
  const existing=await request('/api/quotes?q='+encodeURIComponent(q.source_number)+'&page=1');
  if(!Array.isArray(existing.data)||!Number.isInteger(existing.total))throw Error('The existing-quote check could not be verified.');
  if(existing.total>0)throw Error('ShopVox '+q.source_number+': a quote already matches this reference. Review it in Saved quotes before importing this item.');
  const found=await request('/api/customers?q='+encodeURIComponent(q.customer)+'&page=1');
  if(!Array.isArray(found.data)||!Number.isInteger(found.total)||found.total>50)throw Error('The customer match could not be verified.');
  const matches=found.data.filter(c=>c.active&&same(c.data?.name,q.customer));
  if(matches.length!==1)throw Error('ShopVox '+q.source_number+': expected one active customer named '+q.customer+'. Check the customer record first.');
  const customer=await request('/api/customers/'+matches[0].id);
  if(customer.data?.id!==matches[0].id||!customer.data.active||!same(customer.data.data?.name,q.customer)||!Array.isArray(customer.contacts))throw Error('The selected customer changed. Review the file again.');
  const contacts=customer.contacts.filter(c=>c.active&&c.customer_id===customer.data.id&&same(c.data?.email,q.contact_email)&&same(c.data?.name,q.contact));
  if(contacts.length!==1)throw Error('ShopVox '+q.source_number+': expected one active contact '+q.contact+' ('+q.contact_email+'). Check the customer contact first.');
  return {state:'ready',customer_id:customer.data.id,contact_id:contacts[0].id,message:'Ready — customer and contact matched.'};
 }
 function render(){
  el('items').replaceChildren();
  for(const row of rows){
   const q=row.q,box=node('section');box.className='card';box.append(node('h3','ShopVox '+q.source_number+' · '+q.customer),node('p',q.contact+' · '+q.contact_email),node('p','Quote date '+q.data.quote_date+' · Valid until '+q.data.valid_until),node('p',money(q.expected.subtotal_cents)+' before VAT + '+money(q.expected.tax_cents)+' VAT = '+money(q.expected.total_cents)+' · Deposit '+money(q.expected.deposit_cents)),node('p',row.message));
   if(row.saved){box.append(node('p','Current saved quote: '+money(row.saved.data.total_cents)+' · '+(row.saved.status==='issued'?'Finalised':'Draft')));const a=node('a','Open saved quote '+row.saved.number);a.href='/quotes?id='+encodeURIComponent(row.saved.id);box.append(a);}
   const details=node('details');details.append(node('summary','Review '+q.data.lines.length+' item(s) and terms'));
   const scroll=node('div');scroll.className='scroll';const table=node('table'),head=node('tr');for(const t of ['Item','Quantity / unit','Unit price (before VAT)','VAT'])head.append(node('th',t));table.append(head);
   for(const l of q.data.lines){const tr=node('tr'),td=node('td');td.append(node('pre',l.description+(l.finish?'\n'+l.finish:'')+(l.placement?'\n'+l.placement:'')));tr.append(td,node('td',l.quantity+' '+l.unit),node('td','BSD '+l.unit_price),node('td',l.vat_rate+'%'));table.append(tr);}
   scroll.append(table);details.append(scroll,node('pre',q.data.notes),node('pre',q.data.terms));box.append(details);el('items').append(box);
  }
  const kept=rows.filter(r=>r.state==='kept').length,missing=rows.filter(r=>r.state==='ready').length,held=rows.filter(r=>r.state==='held').length;
  el('summary').textContent=rows.length+' quotes · '+missing+' ready · '+kept+' already saved · '+held+' held · Source total '+money(rows.reduce((n,r)=>n+r.q.expected.total_cents,0));
  el('review').hidden=!rows.length;
 }
 function savedMatches(saved,q,resolved){
  if(!saved||saved.id!==q.id||saved.status!=='draft'||saved.version!==1||!saved.number||saved.customer_id!==resolved.customer_id||saved.contact_id!==resolved.contact_id||!saved.data)return false;
  const data=saved.data;
  for(const [k,v] of Object.entries(q.expected))if(data[k]!==v)return false;
  for(const [k,v] of Object.entries(q.data)){
   if(k==='lines'){
    if(!Array.isArray(data.lines)||data.lines.length!==v.length)return false;
    if(!v.every((l,i)=>Object.entries(l).every(([f,value])=>data.lines[i]?.[f]===value)))return false;
   }else if(data[k]!==v)return false;
  }
  return true;
 }
 el('source').onchange=()=>{rows=[];ready=false;el('confirmed').checked=false;el('review').hidden=true;el('items').replaceChildren();el('result').textContent='';controls();};
 el('confirmed').onchange=controls;
 el('preview').onclick=()=>work(async()=>{
  ready=false;rows=[];el('confirmed').checked=false;el('review').hidden=true;el('items').replaceChildren();el('result').textContent='';
  await access();const bytes=await readFile(el('source').files?.[0]);
  const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');
  if(hash!==BUNDLE_SHA256)throw Error('This is not the unchanged reviewed quote file supplied with update 114.8. Choose CustomU_Reviewed_Quotes_1864_1867.json.');
  const bundle=JSON.parse(new TextDecoder().decode(bytes));
  const profile=await request('/api/quotes/profile');if(!profile.data?.version)throw Error('Save the business details in Quotes before importing.');
  for(const q of bundle.quotes){
   status('Checking ShopVox '+q.source_number+'…');
   let resolved;try{resolved=await resolve(q);}catch(e){if(!signed)throw e;resolved={state:'held',message:e.message};}
   if(!signed)return;rows.push({q,...resolved});render();
  }
  ready=true;status('Review complete. Only ready quotes will be saved when you click Save.');
 });
 el('save').onclick=()=>work(async()=>{
  if(!ready||!el('confirmed').checked)return;
  ready=false;await access();
  for(const row of rows){
   if(row.state!=='ready')continue;
   status('Saving ShopVox '+row.q.source_number+'…');
   try{
    const checked=await resolve(row.q);if(checked.state==='kept'){Object.assign(row,checked);render();continue;}
    if(checked.customer_id!==row.customer_id||checked.contact_id!==row.contact_id)throw Error('The customer or contact match changed. Review the file again.');
    const result=await request('/api/quotes/save',{op:'save',id:row.q.id,version:0,customer_id:checked.customer_id,contact_id:checked.contact_id,data:row.q.data});
    if(!savedMatches(result.data,row.q,checked))throw Error('The saved quote values could not be confirmed. Review the same file again before retrying.');
    row.state='kept';row.saved=result.data;row.message='Saved as a draft — amounts and items confirmed.';render();
   }catch(e){if(signed){row.state='held';row.message=e.message;render();}throw e;}
  }
  el('confirmed').checked=false;status('Draft import finished. Open the saved quotes to review them.');el('result').textContent='No quotes were finalised and no invoices or emails were created.';
 });
 el('logout').onclick=()=>work(async()=>{clear();await request('/api/logout',{});status('Signed out.');});
 window.addEventListener('beforeunload',e=>{if(busy){e.preventDefault();e.returnValue='';}});
 work(async()=>{const session=await access();el('workspace').hidden=false;el('identity').textContent=session.me.email;status('Choose the reviewed quote file to begin.');});
})();
