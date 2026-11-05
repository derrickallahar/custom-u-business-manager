'use strict';
const el=id=>document.getElementById(id);
const reviewed=document.body.dataset.reviewed==='1';
const apiBase=reviewed?'/api/customers/reviewed-import':'/api/customers/import';
let report=null,previewId=null,busy=false,page=1,completed=false;
const labels={ready:'Ready to add',review:'Held for review',already_added:'Already added',combined:'Included with another source row',excluded:'Kept in archive'};
const errors={PREVIEW_STALE:'Customer records changed. Preview the CSV again before importing.',PREVIEW_EXPIRED:'This preview expired or the app restarted. Preview the CSV again.',DUPLICATE_REVIEW_REQUIRED:'A possible duplicate needs review. Preview again; nothing was added by this attempt.',IMPORT_ROLLED_BACK:'A row failed validation. This import was rolled back completely.',CUSTOMER_CSV_HEADERS_REQUIRED:'Choose the original ShopVox customer export CSV, with all its original columns.',CSV_FORMAT_INVALID:'This file could not be read as a customer CSV.',CSV_COLUMN_COUNT_INVALID:'The CSV has an unexpected number of fields in a row.',CSV_TOO_LARGE_OR_EMPTY:'Choose a nonempty customer CSV smaller than 512 KB.',CSV_ROW_LIMIT_REACHED:'This import supports up to 1,000 customer rows.',IMPORT_BUSY:'Another import is running. Wait, then preview again.',CUSTOMERS_NOT_ENABLED:'Customer management has not been enabled.',IMPORT_REVIEW_LIMIT:'The CRM is too large for this import tool. No import was performed.',IMPORT_CONFLICT:'An imported identity already exists. Preview again to check what has already been added.'};
function status(text){el('status').textContent=text;}
Object.assign(errors,{APPROVED_SOURCE_REQUIRED:'Choose the same original November 2 customer CSV used for the first import. The reviewed decisions are specific to that file.',APPROVED_PLAN_CHANGED:'The approved mapping does not match this code. No import was performed.',INVALID_REVIEWED_PLAN:'The reviewed import code and SQL do not match. Check that update 096 was installed completely.',COMPLETE_FIRST_IMPORT:'The first customer import must be complete before applying these decisions.',REVIEWED_SOURCE_CONFLICT:'Some reviewed records already exist or match a CRM customer. No changes were made. Keep this message for review.'});
function clearPreview(){report=null;previewId=null;page=1;completed=false;el('rows').replaceChildren();el('summary').textContent='';el('contact-count').textContent='';el('archive-fields').textContent='';el('page-label').textContent='';el('confirmed').checked=false;el('preview').hidden=true;el('result').hidden=true;el('result-text').textContent='';el('confirmation').hidden=false;}
function clearPrivate(){clearPreview();el('workspace').hidden=true;el('identity').textContent='';el('csv-file').value='';el('search').value='';}
async function api(path,body){
 const r=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});
 const data=await r.json();
 if(!r.ok){if(r.status===401||r.status===403){clearPrivate();throw Error('Access ended. Open the sign-in link to continue.');}throw Error(errors[data.error]||'The result is not confirmed. Preview the same CSV again to check what is already in the CRM.');}
 return data;
}
function filtered(){const q=el('search').value.trim().toLowerCase(),s=el('filter').value;return (report?.rows||[]).filter(r=>(s==='all'||r.status===s)&&JSON.stringify([r.customer,r.contact,r.extra_contacts]).toLowerCase().includes(q));}
function controls(){const rows=filtered();el('commit').disabled=busy||completed||!previewId||!report?.counts.ready||!el('confirmed').checked;el('prev').disabled=busy||page===1;el('next').disabled=busy||page*50>=rows.length;el('download-report').disabled=busy||!report;}
function paragraph(parent,text){const p=document.createElement('p');p.textContent=text;parent.append(p);}
function render(){
 const rows=filtered();page=Math.max(1,Math.min(page,Math.ceil(rows.length/50)||1));el('rows').replaceChildren();
 for(const r of rows.slice((page-1)*50,page*50)){
  const tr=document.createElement('tr'),a=document.createElement('td'),b=document.createElement('td'),c=document.createElement('td');
  paragraph(a,r.customer.name);paragraph(a,'CSV row '+r.row);
  if(r.customer.address)paragraph(a,'Address: '+r.customer.address);if(r.customer.tax_id)paragraph(a,'VAT ID: '+r.customer.tax_id);
  paragraph(b,r.contact?.name||'No named contact');if(r.contact?.title)paragraph(b,r.contact.title);paragraph(b,r.customer.email||'No email');paragraph(b,r.customer.phone||'No phone');
  for(const contact of r.extra_contacts||[]){paragraph(b,'Additional contact: '+contact.name);if(contact.title)paragraph(b,contact.title);paragraph(b,contact.email||'No email');paragraph(b,contact.phone||'No phone');}
  paragraph(c,labels[r.status]);if(r.status==='review')c.className='held';
  for(const message of r.problems)paragraph(c,message);
  if(r.notes.length){const d=document.createElement('details'),s=document.createElement('summary');s.textContent=r.notes.length+' notes';d.append(s);for(const note of r.notes)paragraph(d,note);c.append(d);}
  tr.append(a,b,c);el('rows').append(tr);
 }
 el('page-label').textContent=rows.length+' matching rows · Page '+page;controls();
}
async function run(fn){if(busy)return;busy=true;document.querySelectorAll('button,input,select').forEach(e=>e.disabled=true);try{await fn();}catch(e){status(e.message);}finally{busy=false;document.querySelectorAll('button,input,select').forEach(e=>e.disabled=false);controls();}}
el('csv-file').onchange=()=>{clearPreview();controls();status('File selected. Preview it to review the proposed customers.');};
el('preview-form').onsubmit=e=>{e.preventDefault();run(async()=>{
 clearPreview();const file=el('csv-file').files[0];if(!file||!file.size||file.size>512*1024)throw Error(errors.CSV_TOO_LARGE_OR_EMPTY);
 status('Reading the export and checking existing customers…');
 let csv;try{csv=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(await file.arrayBuffer());}catch{throw Error('Choose the original UTF-8 customer CSV export.');}
 const result=await api(apiBase+'/preview',{csv});report=result.report;previewId=result.preview_id;
 const c=report.counts;el('summary').textContent=c.total+' source rows: '+c.ready+' ready · '+c.review+' held for review · '+c.already_added+' already added';
 if(c.combined||c.excluded)el('summary').textContent+=' · '+(c.combined||0)+' combined · '+(c.excluded||0)+' kept in archive';
 el('contact-count').textContent=c.ready+' customers and '+c.contacts_to_add+' contacts would be added.';
 el('archive-fields').textContent=Object.entries(report.archive_only_fields).map(([k,n])=>k+' ('+n+' populated rows)').join('; ')||'None';
 el('commit').textContent='Import '+c.ready+' ready customers';el('preview').hidden=false;render();status('Preview complete. Nothing has been saved.');
});};
el('filter').onchange=()=>{page=1;render();};el('search').oninput=()=>{page=1;render();};
el('prev').onclick=()=>{page--;render();};el('next').onclick=()=>{page++;render();};el('confirmed').onchange=controls;
el('commit').onclick=()=>run(async()=>{
 if(!previewId||!el('confirmed').checked||completed)return;
 status('Saving the ready customers and contacts…');
 let outcome;try{outcome=await api(apiBase+'/commit',{preview_id:previewId,confirm:true});}catch(e){el('confirmed').checked=false;previewId=null;throw e;}
 completed=true;previewId=null;el('confirmation').hidden=true;el('result').hidden=false;
 el('result-text').textContent=outcome.customers_added+' customers and '+outcome.contacts_added+' contacts added. '+outcome.held_for_review+' source rows remain held for review.';
 if(outcome.already_completed)el('result-text').textContent='These reviewed customers were already imported. No additional records were created.';
 report.import_result=outcome;status('Import completed. Download the report, then make a new CRM backup.');
});
el('download-report').onclick=()=>{if(!report)return;const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='CustomU_Customer_Import_'+(reviewed?'096':'095')+'_'+report.source_sha256.slice(0,12)+'.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);};
el('logout').onclick=()=>run(async()=>{clearPrivate();await api('/api/logout',{});status('Signed out. Open the sign-in link to return.');});
run(async()=>{const r=await api('/api/session');if(!r.crm_enabled)throw Error(errors.CUSTOMERS_NOT_ENABLED);el('identity').textContent=r.me.email;el('workspace').hidden=false;status('Choose your customer CSV to begin.');});
