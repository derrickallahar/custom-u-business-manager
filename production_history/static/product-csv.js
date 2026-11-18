'use strict';
const el=id=>document.getElementById(id);
let report=null,previewId=null,busy=false,completed=false,selected=new Set(),vat=new Map();
const errors={
 CSV_SIZE_INVALID:'Choose a nonempty CSV under 2 MB.',CSV_ROW_LIMIT:'Use a CSV with at most 1,000 products.',CSV_HEADERS_INVALID:'This file does not have the required ShopVox product columns. Export the product list as CSV.',CSV_COLUMNS_INVALID:'Some rows do not match the CSV column headings.',CSV_CONTROL_CHARACTERS:'The CSV contains unsupported control characters.',CSV_FORMAT_INVALID:'The CSV could not be read. Export a fresh UTF-8 CSV.',CSV_EMPTY:'There are no product rows in this CSV.',
 PREVIEW_STALE:'The catalogue has changed. Preview the CSV again before selecting products.',PREVIEW_EXPIRED:'This preview expired. Preview the CSV again.',PREVIEW_ALREADY_USED:'This preview was already imported. Preview the CSV again for another selection.',INVALID_SELECTION:'One or more selected rows cannot be imported. Preview again and review the selected rows.',VAT_REVIEW_REQUIRED:'Enter a VAT percentage from 0 to 100 for each selected item.',CONFIRM_PREVIEW_REQUIRED:'Select products and confirm their prices, units and VAT before adding them.',IMPORT_BUSY:'Another import is running. Wait for it to finish, then preview again.',PRODUCT_LIMIT:'The catalogue limit of 5,000 products has been reached.',PRODUCT_HISTORY_LIMIT:'The product change-history limit has been reached.',CUSTOMERS_NOT_ENABLED:'The catalogue is not enabled in this installation.'
};
function status(message){el('status').textContent=message;}
function invalidate(){report=null;previewId=null;completed=false;selected.clear();vat.clear();el('preview').hidden=true;el('result').hidden=true;el('rows').replaceChildren();el('summary').textContent='';el('result-text').textContent='';el('confirmed').checked=false;el('prices-confirmed').checked=false;el('batch-vat').value='';controls();}
function clear(){invalidate();el('workspace').hidden=true;el('identity').textContent='';el('csv-file').value='';}
function confirmationsOff(){el('confirmed').checked=false;}
function validVat(value){return typeof value==='string'&&/^[0-9]{1,3}(\.[0-9]{1,2})?$/.test(value)&&Number(value)<=100;}
function controls(){
 const count=selected.size,missing=[...selected].filter(n=>!validVat(vat.get(n))).length;
 el('commit').disabled=busy||completed||!previewId||count<1||count>250||missing>0||!el('prices-confirmed').checked||!el('confirmed').checked;
 el('commit').textContent='Add '+count+' selected product'+(count===1?'':'s');
 el('selection-summary').textContent=count+' selected'+(missing?' · '+missing+' need a VAT rate':'');
 el('preview-button').disabled=busy;el('csv-file').disabled=busy;
 for(const id of ['select-candidates','clear-selection','apply-vat','batch-vat','prices-confirmed','confirmed'])el(id).disabled=busy||completed;
 el('confirm-box').hidden=completed;
 el('rows').querySelectorAll('input').forEach(x=>x.disabled=busy||completed);
}
async function api(path,body){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),45000);
 try{
  let r;try{r=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});}catch{previewId=null;throw Error('The response was not received. A submitted import may have completed. Preview the CSV again to check which products were added.');}
  let d;try{d=await r.json();}catch{previewId=null;if(r.status===401||r.status===403)clear();throw Error('The result could not be read. Preview again to check the catalogue.');}
  if(!r.ok){if(r.status===401||r.status===403){clear();throw Error('Administrator access is required. Return to Workspace to sign in.');}previewId=null;throw Error(errors[d?.error]||'The import is not confirmed. Check that the product CSV update is installed, then preview the CSV again.');}
  return d;
 }finally{clearTimeout(timer);}
}
async function run(fn){if(busy)return;busy=true;controls();try{await fn();}catch(e){status(e.message||'The action could not complete.');}finally{busy=false;controls();}}
const td=(tr,text)=>{const cell=document.createElement('td');cell.textContent=text;tr.append(cell);return cell;};
function render(){
 el('rows').replaceChildren();if(!report)return;
 const q=el('find').value.toLowerCase().trim(),filter=el('filter').value;
 for(const r of report.rows){
  if(filter!=='all'&&r.status!==filter)continue;
  if(q&&!`${r.data.name} ${r.data.category} ${r.data.code}`.toLowerCase().includes(q))continue;
  const tr=document.createElement('tr'),pick=td(tr,'');
  if(r.status==='candidate'){
   const box=document.createElement('input');box.type='checkbox';box.checked=selected.has(r.row);box.setAttribute('aria-label','Select '+r.data.name);box.onchange=()=>{box.checked?selected.add(r.row):selected.delete(r.row);confirmationsOff();controls();};pick.append(box);
  }
  const product=td(tr,r.data.name);const detail=document.createElement('small');detail.textContent='CSV row '+r.row+' · '+r.data.category;product.append(detail);
  if(r.data.description){const desc=document.createElement('small');desc.textContent=r.data.description;product.append(desc);}
  td(tr,r.data.unit+' · '+r.source_price);
  td(tr,`${r.pricing_type} · Active: ${r.source_active} · Taxable: ${r.source_taxable}`);
  td(tr,r.status==='candidate'?'Review unit price and VAT.':r.problems.join(' '));
  const tax=td(tr,'');
  if(r.status==='candidate'){
   const input=document.createElement('input');input.className='vat';input.type='number';input.min='0';input.max='100';input.step='0.01';input.placeholder='Review';input.value=vat.get(r.row)||'';input.setAttribute('aria-label','VAT rate for '+r.data.name);
   input.oninput=()=>{vat.set(r.row,input.value);confirmationsOff();controls();};tax.append(input);
  }
  el('rows').append(tr);
 }
 controls();
}
el('preview-form').onsubmit=e=>{e.preventDefault();run(async()=>{
 invalidate();const file=el('csv-file').files?.[0];if(!file||!file.size||file.size>2*1024*1024)throw Error(errors.CSV_SIZE_INVALID);
 let text;try{text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(await file.arrayBuffer());}catch{throw Error('Please export or save this file as UTF-8 CSV.');}
 status('Checking products and existing catalogue matches…');
 const r=await api('/api/products/csv-import/preview',{csv:text});
 if(!r.preview_id||!Array.isArray(r.report?.rows)||!r.report?.counts)throw Error('The preview response was incomplete. Try a fresh preview.');
 report=r.report;previewId=r.preview_id;const c=report.counts;
 el('summary').textContent=`${c.total} source rows · ${c.candidate} available for review · ${c.review} held · ${c.existing} existing matches · ${c.already_added} already imported`;
 el('preview').hidden=false;render();status('Preview ready. No products have been added.');
});};
el('csv-file').onchange=()=>{if(!busy){invalidate();status('');}};
el('filter').onchange=render;el('find').oninput=render;
el('select-candidates').onclick=()=>{if(busy||completed||!report)return;for(const r of report.rows)if(r.status==='candidate'&&selected.size<250)selected.add(r.row);confirmationsOff();render();};
el('clear-selection').onclick=()=>{if(busy||completed)return;selected.clear();confirmationsOff();render();};
el('apply-vat').onclick=()=>{if(busy||completed)return;const v=el('batch-vat').value;if(!validVat(v)){status(errors.VAT_REVIEW_REQUIRED);return;}for(const n of selected)vat.set(n,v);confirmationsOff();render();status('VAT rate applied to selected rows. Review before adding products.');};
el('prices-confirmed').onchange=controls;el('confirmed').onchange=controls;
el('commit').onclick=()=>{if(el('commit').disabled)return;run(async()=>{
 const selections=[...selected].sort((a,b)=>a-b).map(row=>({row,vat_rate:vat.get(row)}));
 status('Adding selected products…');
 const r=await api('/api/products/csv-import/commit',{preview_id:previewId,selections,confirm:true,prices_bsd_before_vat:true});
 if(r.products_added!==selections.length){previewId=null;throw Error('The import count was not confirmed. Preview again to check the catalogue.');}
 completed=true;previewId=null;el('result').hidden=false;el('result-text').textContent=`${r.products_added} products added. Existing catalogue products were kept.`;status('Import complete.');
 });};
el('download').onclick=()=>{if(!report)return;const blob=new Blob([JSON.stringify({format:'custom-u-product-csv-review-114.1',...report},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='CustomU_Product_CSV_Review.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);};
run(async()=>{const r=await api('/api/session');if(r.me?.role!=='admin'||!r.crm_enabled){clear();throw Error('Administrator access is required. Return to Workspace to sign in.');}el('identity').textContent=r.me.email+' · Administrator';el('workspace').hidden=false;status('');});
