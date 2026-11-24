'use strict';
const creationPage=location.pathname==='/mockups/new';
const e=id=>document.getElementById(id),presets={generic:{centre:[50,50,25]},shirt:{centre:[50,40,25],'left-chest':[63,32,12],back:[50,42,30],'left-sleeve':[50,50,20],'right-sleeve':[50,50,20]},journal:{centre:[50,50,30],'bottom-right':[68,78,18],'upper-left':[32,25,18]},drinkware:{centre:[50,50,23],front:[50,52,23]}};
const labels={centre:'Centre','left-chest':'Left chest (wearer)','back':'Back','bottom-right':'Bottom right','upper-left':'Upper left',front:'Front','left-sleeve':'Left sleeve','right-sleeve':'Right sleeve'};
let manual=null,photoPending=null,options=null;
let me=null,busy=false,customer=null,product=null,preview=null,previewURL=null,savedLogo=null,saveId=null,page=1,total=0,dirty=false;
const can=k=>me?.role==='admin'||me?.permissions?.[k]===true;
const messages={INVALID_REFERENCE_AREA:'Enter the item dimensions and mark its reference area on the photo.',REFERENCE_ASPECT_MISMATCH:'Mark the reference area again to match the entered dimensions.',PRINT_OUTSIDE_REFERENCE:'The print size or rotation does not fit in the marked area. Reduce it slightly or check the reference area.',PRINT_SIZE_TOO_SMALL:'The requested print is too small to show on this photo.',ACCESS_DENIED:'Mockup access ended. Return to Workspace to sign in.',NOT_FOUND:'The customer, product or photo is unavailable or archived. Choose an active record.',INVALID_MOCKUP:'Check the logo, title and placement. Use a still PNG, JPG or WebP logo up to 12 MB.',LOGO_EMPTY:'This logo is fully transparent. Choose visible artwork.',VERSION_CONFLICT:'This record changed in another session. Refresh saved mockups before retrying.',MOCKUP_ID_CONFLICT:'This save ID already belongs to a different preview. Start a new mockup.',MOCKUP_STORAGE_LIMIT:'The mockup storage limit has been reached. Archiving retains files and does not free space.',MOCKUP_HISTORY_LIMIT:'The mockup history limit has been reached.',INVALID_IMAGE:'Choose a valid PNG, JPG or WebP product photo up to 12 MB.',IMAGE_TOO_LARGE:'Choose a product photo up to 12 MB.',IMAGE_ID_CONFLICT:'The upload could not be matched. Choose the file again and retry.',PRODUCT_IMAGE_LIMIT:'This product has reached its saved-photo limit. Review its existing photos.',PRODUCT_IMAGE_BUSY:'Image processing or backup is busy. Try again shortly.',IMAGE_INTEGRITY_FAILED:'The image integrity check failed. This result is not confirmed.'};
function status(text,error=false){e('status').textContent=text;e('status').className=error?'error':'';}
function discardPreview(){preview=null;if(previewURL)URL.revokeObjectURL(previewURL);previewURL=null;e('preview-image').removeAttribute('src');e('preview-image').hidden=true;e('preview-note').textContent='Placement changed. Click Update preview before saving.';}
function controls(){options?.controls();photoControls();manual?.controls();e('new').hidden=!can('products.edit');e('save').disabled=busy||!preview||!customer||!product||!e('title').value.trim()||!can('products.edit');e('preview').disabled=busy||!can('products.edit');previewHelp();e('preview-working').disabled=e('preview').disabled;e('previous').disabled=busy||page===1;e('next').disabled=busy||page*25>=total;}
function previewProblem(){
 if(!can('products.edit'))return {id:'identity',message:'Edit products access is required to create a mockup.'};
 if(!product)return {id:'product-search',message:'Choose the product with Find product before updating the preview.'};
 if(!e('source-image').value&&!photoPending&&!e('product-photo-file').files?.length)return {id:'product-photo-file',message:'Choose a product photo from the list, or select a file under Add a product photo.'};
 const file=e('logo').files?.[0];
 if(!file&&!savedLogo)return {id:'logo',message:'Choose the customer logo or artwork in Customer logo or image. The product photo and logo are separate images.'};
 if(file&&(file.size===0||file.size>12000000||!['image/png','image/jpeg','image/webp'].includes(file.type)))return {id:'logo',message:'Choose a PNG, JPG or WebP logo up to 12 MB.'};
 return manual?.problem?.()||null;
}
function previewHelp(){
 const problem=previewProblem(),message=busy?'Please wait for the current action to finish…':problem?problem.message:photoPending?'The photo upload is unconfirmed. Click Update preview to retry it safely.':e('product-photo-file').files?.length?'Update preview will upload your selected product photo and apply the logo.':'Ready. Click Update preview to apply the artwork.';
 for(const id of ['preview-help','preview-working-help']){const node=e(id);if(node)node.textContent=message;}
}
function showPreviewProblem(problem){
 status(problem.message,true);e('preview-note').textContent=problem.message;
 for(const id of ['preview-help','preview-working-help'])if(e(id))e(id).textContent=problem.message;
 const field=e(problem.id);field?.scrollIntoView?.({behavior:'smooth',block:'center'});field?.focus({preventScroll:true});
}
function clear(){options?.clear();clearPhoto();manual?.clear();me=null;customer=null;product=null;savedLogo=null;e('logo-note').textContent='';discardPreview();saveId=null;dirty=false;e('workspace').hidden=true;e('editor').hidden=true;e('identity').textContent='';e('saved').replaceChildren();e('customer-results').replaceChildren();e('product-results').replaceChildren();e('customer-name').textContent='';e('product-name').textContent='';e('count').textContent='';e('source-image').replaceChildren();e('workspace').querySelectorAll('input').forEach(x=>{x.value='';});}
async function api(path,body){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),60000);try{const r=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined,signal:controller.signal});let d;try{d=await r.json();}catch{if(r.status===401||r.status===403)clear();throw Error('The server response could not be read. Check saved mockups before retrying a save.');}if(!r.ok){if(r.status===401||r.status===403)clear();const error=Error(messages[d?.error]||'The request could not complete. Refresh saved mockups before retrying a save.');error.definitive=r.status>=400&&r.status<500;throw error;}return d;}catch(err){if(err.name==='AbortError'||err instanceof TypeError)throw Error('The connection did not confirm completion. Refresh saved mockups before retrying a save.');throw err;}finally{clearTimeout(timer);}}
async function run(fn){if(busy)return;busy=true;e('workspace').querySelectorAll('button,input,select').forEach(x=>x.disabled=true);try{await fn();}catch(err){status(err.message,true);}finally{busy=false;e('workspace').querySelectorAll('button,input,select').forEach(x=>x.disabled=false);controls();}}
function change(){discardPreview();saveId=null;dirty=true;controls();manual?.draw();}
function ranges(){manual?.sync();for(const k of ['x','y','width','rotation'])e(k+'-value').textContent=e(k).value+(k==='rotation'?'°':'%');}
function fit(){const p=presets[e('family').value][e('placement').value];['x','y','width'].forEach((k,i)=>e(k).value=p[i]);e('rotation').value=0;ranges();manual?.percentageChanged('width');change();}
function family(){e('placement').replaceChildren();for(const k of Object.keys(presets[e('family').value])){const o=document.createElement('option');o.value=k;o.textContent=labels[k];e('placement').append(o);}fit();}
function fresh(){options?.clear();clearPhoto();manual?.clear();customer=null;product=null;savedLogo=null;e('logo-note').textContent='';e('editor-title').textContent='Prepare a client mockup';discardPreview();saveId=null;e('customer-name').textContent='';e('product-name').textContent='';e('customer-results').replaceChildren();e('product-results').replaceChildren();e('source-image').replaceChildren();e('logo').value='';e('title').value='';e('family').value='generic';e('finish').value='colour';family();e('editor').hidden=false;dirty=false;controls();}
e('new').onclick=()=>{if(!dirty||confirm('Discard the unsaved mockup?')){if(!creationPage){location.assign('/mockups/new');return;}fresh();}};
e('family').onchange=family;e('placement').onchange=fit;e('fit').onclick=fit;
for(const k of ['x','y','width','rotation'])e(k).oninput=()=>{ranges();manual?.percentageChanged(k);change();};
e('finish').onchange=change;e('logo').onchange=()=>{manual?.clear();savedLogo=null;e('logo-note').textContent='';change();};e('source-image').onchange=()=>{manual?.clear();showProductPhoto();change();};e('title').oninput=()=>{saveId=null;dirty=true;controls();};
e('find-customer').onclick=()=>run(async()=>{const r=await api('/api/customers?q='+encodeURIComponent(e('customer-search').value)+'&page=1');e('customer-results').replaceChildren();for(const c of r.data.filter(x=>x.active)){const b=document.createElement('button');b.textContent=c.data.name;b.onclick=()=>{customer=c;e('customer-name').textContent=c.data.name;e('customer-results').replaceChildren();saveId=null;dirty=true;controls();};e('customer-results').append(b);}status(r.total>50?'Refine the search to find the customer among the first 50 matches.':'Choose a customer.');});
e('find-product').onclick=()=>run(async()=>{if(photoPending)throw Error('Retry the pending photo upload before changing products.');const r=await api('/api/products?q='+encodeURIComponent(e('product-search').value)+'&page=1&state=active');e('product-results').replaceChildren();for(const p of r.data){const b=document.createElement('button');b.type='button';b.textContent=p.data.name;b.onclick=()=>run(async()=>{if(photoPending)return;clearPhoto();manual?.clear();product=p;change();e('source-image').replaceChildren();e('product-name').textContent=p.data.name;e('product-results').replaceChildren();await loadProductPhotos();status(e('source-image').value?'Choose the photo, logo and placement.':'This product has no saved photos. Use Add a product photo below.');});e('product-results').append(b);}status(r.total>50?'Showing the first 50 matches. Refine your search.':'Choose a product.');});
function clearPhoto(){photoPending=null;e('product-photo-file').value='';e('product-photo-caption').value='';e('photo-upload-status').textContent='';e('product-photo-preview').hidden=true;e('product-photo-preview').removeAttribute('src');}
function photoControls(){
 e('product-photo-tools').hidden=!can('products.edit');
 e('upload-product-photo').disabled=busy||!can('products.edit')||!product||(!photoPending&&!e('product-photo-file').files?.length);
 e('upload-product-photo').textContent=photoPending?'Retry this photo upload':'Upload and use this photo';
 for(const id of ['product-photo-file','product-photo-caption','find-product','product-search','source-image'])e(id).disabled=busy||!!photoPending||!can('products.edit');
 e('photo-help').textContent=product?'Add a photo for '+product.data.name+'.':'Choose the product above, then upload its photo here.';
}
function showProductPhoto(){const img=e('product-photo-preview'),id=e('source-image').value;img.hidden=!product||!id;if(product&&id)img.src='/api/products/'+encodeURIComponent(product.id)+'/images/'+encodeURIComponent(id);else img.removeAttribute('src');}
async function loadProductPhotos(selected=''){
 const result=await api('/api/products/'+product.id+'/images');if(!Array.isArray(result.data))throw Error('The saved product photos could not be checked.');
 e('source-image').replaceChildren();const images=result.data.filter(x=>x.active);
 if(!images.length){const o=document.createElement('option');o.value='';o.textContent='No saved photos — upload one below';e('source-image').append(o);}
 for(const img of images){const o=document.createElement('option');o.value=img.id;o.textContent=img.caption||img.filename;e('source-image').append(o);}
 if(selected){if(!images.some(i=>i.id===selected))throw Error('The photo upload is not yet confirmed. Retry the retained upload.');e('source-image').value=selected;}
 showProductPhoto();return images;
}
e('product-photo-file').onchange=()=>{e('photo-upload-status').textContent='';manual?.clear();change();};
async function uploadProductPhoto(){
 if(!product||!can('products.edit'))throw Error('Choose a product first. Edit products access is required to upload a photo.');
 if(!photoPending){const file=e('product-photo-file').files?.[0];if(!file||file.size===0||file.size>12000000||!['image/png','image/jpeg','image/webp'].includes(file.type))throw Error('Choose a PNG, JPG or WebP product photo up to 12 MB.');photoPending={product_id:product.id,body:{id:crypto.randomUUID(),filename:file.name,caption:e('product-photo-caption').value.trim(),source_url:'',data:await base64(file)}};}
 const pending=photoPending;dirty=true;e('photo-upload-status').textContent='Uploading and checking the product photo…';
 try{
  const r=await api('/api/products/'+pending.product_id+'/images/add',pending.body);
  if(r.data?.id!==pending.body.id||r.data?.product_id!==pending.product_id)throw Error('The photo save was not confirmed. Retry this upload safely.');
  await loadProductPhotos(pending.body.id);photoPending=null;e('product-photo-file').value='';e('product-photo-caption').value='';manual?.clear();change();
  e('photo-upload-status').textContent='Product photo saved and selected. Add the customer logo, then Update preview.';status('Product photo saved and selected for this mockup.');
 }catch(error){if(error.definitive)photoPending=null;e('photo-upload-status').textContent=photoPending?'The upload is not confirmed. Retry this photo upload; an already-saved photo will be kept once.':error.message;throw error;}
}
e('upload-product-photo').onclick=()=>run(uploadProductPhoto);

const base64=file=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('The image file could not be read.'));reader.readAsDataURL(file);});
function config(){return {...Object.fromEntries(['x','y','width','rotation'].map(k=>[k,Number(e(k).value)])),family:e('family').value,placement:e('placement').value,finish:e('finish').value,...(manual?.scaleConfig()?{scale:manual.scaleConfig()}:{})};}
e('preview').onclick=()=>{
 if(busy||!can('products.edit'))return;
 // Validate while inputs are enabled: browsers skip native validity on disabled fields.
 const problem=previewProblem();if(problem){showPreviewProblem(problem);return;}
 return run(async()=>{try{
  const file=e('logo').files?.[0];
  if(photoPending||e('product-photo-file').files?.length)await uploadProductPhoto();
  discardPreview();status('Preparing the preview…');const r=await api('/api/mockups/preview',{product_id:product.id,image_id:e('source-image').value,logo:file?await base64(file):savedLogo,config:config()});if(!r.preview?.content_base64||!r.logo?.content_base64||!r.config||!r.source_sha256)throw Error('The preview could not be verified.');preview=r;manual?.load('/api/products/'+encodeURIComponent(product.id)+'/images/'+encodeURIComponent(e('source-image').value),r.logo);const bytes=Uint8Array.from(atob(r.preview.content_base64),c=>c.charCodeAt(0));previewURL=URL.createObjectURL(new Blob([bytes],{type:'image/webp'}));e('preview-image').src=previewURL;e('preview-image').hidden=false;e('preview-note').textContent='Preview ready · '+r.preview.width+' × '+r.preview.height+' pixels. Review before saving.';saveId=null;dirty=true;status('Preview ready. Nothing has been saved.');
 }catch(error){e('preview-note').textContent=error.message;throw error;}});
};
e('preview-working').onclick=()=>e('preview').click();
e('save').onclick=()=>run(async()=>{if(!preview||!customer||!product)return;saveId=saveId||crypto.randomUUID();const r=await api('/api/mockups/save',{id:saveId,product_id:product.id,image_id:e('source-image').value,customer_id:customer.id,title:e('title').value.trim(),logo:preview.logo,config:preview.config,source_sha256:preview.source_sha256});if(r.data?.id!==saveId||r.data?.preview?.sha256!==preview.preview.sha256)throw Error('The save could not be verified. Refresh saved mockups before retrying.');dirty=false;status('Mockup saved and image bytes verified. Included in the next workspace backup.');try{await list();}catch{status('Mockup saved and verified. The saved list could not refresh; click Refresh saved mockups.',true);}});
// Load all dependencies before replacing a draft. Reopening itself never writes.
async function copySaved(id){
 if(dirty&&!confirm('Discard the unsaved mockup and edit a copy of this saved design?'))return;
 const access=await api('/api/session');me=access.me;
 if(!can('products.view')||!can('customers.view')){clear();throw Error(messages.ACCESS_DENIED);}
 if(!can('products.edit')){options?.clear();clearPhoto();manual?.clear();savedLogo=null;discardPreview();e('editor').hidden=true;e('logo').value='';e('logo-note').textContent='';await list();throw Error('Edit products access is required to edit a mockup copy.');}
 const m=(await api('/api/mockups/'+id)).data;
 const c=(await api('/api/customers/'+m.customer_id)).data;
 const p=(await api('/api/products/'+m.product_id)).data;
 const images=(await api('/api/products/'+m.product_id+'/images')).data.filter(x=>x.active);
 if(!c?.active||!p?.active||!images.some(x=>x.id===m.image_id)){throw Error('This saved design uses an archived customer, product or photo. Reactivate it before editing a copy, or start a new mockup.');}
 if(!m.logo?.content_base64||!m.preview?.content_base64||!m.config)throw Error('The saved design could not be loaded. Refresh saved mockups and try again.');
 fresh();customer=c;product=p;savedLogo=m.logo;
 e('customer-name').textContent=c.data.name;e('product-name').textContent=p.data.name;
 for(const img of images){const o=document.createElement('option');o.value=img.id;o.textContent=img.caption||img.filename;e('source-image').append(o);}e('source-image').value=m.image_id;showProductPhoto();
 e('family').value=m.config.family;family();e('placement').value=m.config.placement;e('finish').value=m.config.finish;
 for(const k of ['x','y','width','rotation'])e(k).value=m.config[k];ranges();
 e('title').value=Array.from(m.title).slice(0,153).join('')+' — copy';e('editor-title').textContent='Edit a copy';
 e('logo-note').textContent='Saved logo loaded. Choose a file only if you want to replace it.';
 const bytes=Uint8Array.from(atob(m.preview.content_base64),c=>c.charCodeAt(0));previewURL=URL.createObjectURL(new Blob([bytes],{type:'image/webp'}));e('preview-image').src=previewURL;e('preview-image').hidden=false;
 e('preview-note').textContent='Saved design shown. Adjust the settings, then click Update preview before saving your copy.';
 manual?.restore(m.config.scale);manual?.load('/api/products/'+encodeURIComponent(product.id)+'/images/'+encodeURIComponent(e('source-image').value),m.logo);saveId=null;dirty=true;controls();status('Saved design loaded for editing. Saving creates a separate mockup and keeps the original unchanged.');
 e('editor').scrollIntoView?.({behavior:'smooth',block:'start'});e('editor-title').focus({preventScroll:true});
}
async function list(){const r=await api('/api/mockups?q='+encodeURIComponent(e('search').value)+'&state='+e('state').value+'&page='+page);total=r.total;e('saved').replaceChildren();e('count').textContent=total+' mockups · Page '+page;for(const m of r.data){const card=document.createElement('article');card.className='saved-card';const h=document.createElement('h3');h.textContent=m.title;const p=document.createElement('p');p.textContent=m.customer_name+' · '+m.product_name;const i=document.createElement('img');i.src='/api/mockups/'+m.id+'/image';i.alt=m.title;i.loading='lazy';const info=document.createElement('p');info.textContent=(m.active?'Active':'Archived')+' · '+m.config.finish+' · '+labels[m.config.placement]+' starting point · Width '+m.config.width+'% · Position '+m.config.x+'%, '+m.config.y+'%';const a=document.createElement('a');a.href=i.getAttribute('src')+'?download=1';a.textContent='Download saved preview';card.append(h,p,i);const presentation=document.createElement('div');presentation.className='actions';for(const [label,suffix] of [['Open presentation PDF',''],['Download presentation PDF','?download=1']]){const link=document.createElement('a');link.textContent=label;link.href='/api/mockups/'+encodeURIComponent(m.id)+'/pdf'+suffix;presentation.append(link);}card.append(presentation,info,a);if(m.config.scale){const size=document.createElement('p');size.textContent='Production print width: '+m.config.scale.print_width+' in';const sheet=document.createElement('a');sheet.href='/mockups/'+encodeURIComponent(m.id)+'/production';sheet.target='_blank';sheet.rel='noopener';sheet.textContent='Open production size sheet';card.append(size,sheet);}if(can('products.edit')){const edit=document.createElement('button');edit.textContent='Edit a copy';edit.dataset.openPage='/mockups/new?copy='+encodeURIComponent(m.id);edit.onclick=()=>run(()=>copySaved(m.id));card.append(document.createElement('br'),edit);const b=document.createElement('button');b.textContent=m.active?'Archive':'Reactivate';b.onclick=()=>run(async()=>{const result=await api('/api/mockups/'+m.id+'/active',{version:m.version,active:!m.active});if(result.data?.active!==!m.active)throw Error('The status change was not confirmed. Refresh the list.');await list();status('Mockup status saved.');});card.append(document.createElement('br'),b);}e('saved').append(card);}}
async function refresh(){const r=await api('/api/session');me=r.me;if(!can('products.view')||!can('customers.view')){clear();throw Error('View products and View customers access are required for client mockups.');}if(!can('products.edit')){options?.clear();clearPhoto();manual?.clear();savedLogo=null;e('logo-note').textContent='';saveId=null;dirty=false;discardPreview();e('editor').hidden=true;customer=null;product=null;e('logo').value='';e('title').value='';e('customer-name').textContent='';e('product-name').textContent='';e('customer-results').replaceChildren();e('product-results').replaceChildren();}if(!creationPage||e('saved').children.length)await list();}
e('refresh').onclick=()=>run(refresh);e('search-button').onclick=()=>run(async()=>{page=1;await list();});e('previous').onclick=()=>run(async()=>{page--;await list();});e('next').onclick=()=>run(async()=>{page++;await list();});
window.addEventListener('beforeunload',ev=>{if(dirty){ev.preventDefault();ev.returnValue='';}});
run(async()=>{await refresh();e('identity').textContent=me.email;e('workspace').hidden=false;if(creationPage){if(!can('products.edit'))throw Error('Edit products access is required to create mockups.');const copy=new URLSearchParams(location.search).get('copy');if(copy){if(!/^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(copy))throw Error('Invalid copy link.');await copySaved(copy);}else{fresh();status('Choose a customer, product photo and logo for the new mockup.');}}else status('Choose New mockup, Edit a copy, or download a saved preview.');});

manual=window.CustomUMockupEditor?.mount({config,onReady:controls,onChange:()=>{for(const k of ['x','y','width','rotation'])e(k+'-value').textContent=e(k).value+(k==='rotation'?'°':'%');change();},editable:()=>!busy&&can('products.edit')&&!e('editor').hidden})||null;

options=window.CustomUMockupOptions?.mount({
 state:()=>({me,busy,customer,product,preview,photoPending,family:e('family').value}),
 canEdit:()=>can('products.edit'),api,run,status,
 dirty:()=>{dirty=true;},
 configure:placement=>{
  const previous=e('placement').value;
  savedLogo=preview?.logo||savedLogo;
  e('placement').value=placement;manual?.clear();fit();
  if(placement!==previous&&(placement==='back'||placement.endsWith('sleeve'))){
   if(![...e('source-image').options].some(o=>o.value==='')){const o=document.createElement('option');o.value='';o.textContent='Choose the photo for this surface';e('source-image').prepend(o);}
   e('source-image').value='';showProductPhoto();change();
  }
  e('source-image').focus();e('product-name').scrollIntoView?.({behavior:'smooth',block:'start'});
  status('Set up '+(labels[placement]||placement)+': choose its photo, adjust the artwork, Update preview, then Use this preview below.');
 },
 navigate:url=>{dirty=false;location.assign(url);}
})||null;
