'use strict';
const el=id=>document.getElementById(id);
const fields=['code','name','category','description','unit','unit_price','vat_rate','finish','placement'];
const supplierLimits={supplier:160,url:2048,sku:100,cost:10,currency:3,colours:800,sizes:800,specifications:4000};
const emptySupplier=()=>Object.fromEntries(Object.keys(supplierLimits).map(k=>[k,'']));
let me=null,record=null,supplierRecord=null,page=1,total=0,busy=false,dirty=false,importPreview=null,candidate=null,candidateObjectURL=null,uploadId=null;
// Product details have their own URL. Filter state travels with Back to products.
const productPath=location.pathname.toLowerCase().match(/^\/products\/([a-f0-9-]{36}|new)$/i);
const detailPage=!!productPath;
const listQuery=new URLSearchParams(location.search);
const initialState=['active','inactive','all'].includes(listQuery.get('state'))?listQuery.get('state'):'active';
const initialPage=Math.max(1,Math.min(100000,Number.parseInt(listQuery.get('page')||'1',10)||1));
el('search').value=(listQuery.get('q')||'').slice(0,200);el('state').value=initialState;page=initialPage;
document.body.classList.add(detailPage?'product-detail':'product-index');
el('back-products').hidden=!detailPage;el('catalogue-list').hidden=detailPage;el('catalogue-intro').hidden=detailPage;
function catalogueQuery(){return new URLSearchParams({q:el('search').value,state:el('state').value,page:String(page)}).toString();}
function catalogueURL(){return '/products?'+catalogueQuery();}
function productURL(id){return '/products/'+encodeURIComponent(id)+'?'+catalogueQuery();}
function navigateProduct(url){if(busy||!leave())return;dirty=false;location.assign(url);}
function syncProductURL(id){if(detailPage)history.replaceState(null,'',productURL(id));}
const optionGroup=['flyers','brochures'].includes(listQuery.get('group'))?listQuery.get('group'):'';
if(optionGroup)el('back-products').textContent='← Back to '+optionGroup;
el('back-products').href=optionGroup?'/products/options/'+optionGroup:catalogueURL();
el('back-products').addEventListener('click',e=>{if(busy||!leave()){e.preventDefault();return;}dirty=false;});
const can=k=>me?.role==='admin'||me?.permissions?.[k]===true;
const errors={PRICING_MODE_REQUIRED:'Keep a pricing method for this product. Use Unit price with quantity for simple pricing.',PRICING_REQUIRED:'Enter VAT, a minimum line price (0 for none), and a positive price before activating this product.',STARTER_SETUP_UNCONFIRMED:'Setup was not confirmed. Refresh the list, then retry setup; existing products will be kept.',PRODUCT_HISTORY_LIMIT:'The catalogue has reached its change-history limit. Contact your administrator before making further changes.',VERSION_CONFLICT:'This product changed in another session. Your changes are still here. Copy them before reloading the saved product.',PRODUCT_CODE_EXISTS:'That product code is already in use, including archived products. Choose a unique code.',INVALID_PRODUCT:'Check the product code, required fields, selling price and VAT rate.',PRODUCT_LIMIT:'The catalogue has reached its limit of 5,000 products.',NOT_FOUND:'This product could not be found. Refresh the catalogue.'};
function status(message,kind='info',focus=false){
 el('status').textContent=message;
 if(!el('edit').hidden){el('edit-status').textContent=message;const box=el('save-status');box.hidden=false;box.textContent=message;box.dataset.kind=kind;box.setAttribute('role',kind==='error'?'alert':'status');if(focus){box.focus();box.scrollIntoView?.({block:'nearest'});}}
 else if(focus){el('status').setAttribute('tabindex','-1');el('status').focus();el('status').scrollIntoView?.({block:'nearest'});}
}
function clear(){clearStarterProgress();el('starter-setup').hidden=true;fillPricing({});el('csv-import-link').hidden=true;me=null;record=null;supplierRecord=null;dirty=false;el('workspace').hidden=true;el('edit').hidden=true;el('rows').replaceChildren();for(const k of fields)el('p-'+k).value='';for(const k of Object.keys(supplierLimits))el('s-'+k).value='';el('identity').textContent='';el('heading').textContent='';el('page-heading').textContent='Products';document.title='Custom U · Products';el('internal-reference').open=false;el('revision').textContent='';el('edit-status').textContent='';el('save-status').textContent='';el('save-status').hidden=true;el('count').textContent='';el('active').checked=false;el('search').value='';clearImport();el('product-images').hidden=true;el('image-gallery').replaceChildren();el('image-count').textContent='';el('image-file').value='';el('image-caption').value='';el('image-status').textContent='';uploadId=null;}
const safeCodes=new Set([...Object.keys(errors),'INVALID_REQUEST','INVALID_PROVIDER_RESPONSE','REQUEST_FAILED','REQUEST_REJECTED','PROVIDER_REQUEST_FAILED','PROVIDER_UNAVAILABLE','RESPONSE_TOO_LARGE','CUSTOMERS_NOT_ENABLED','PLEASE_WAIT_AND_TRY_AGAIN']);
async function api(path,body){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),path.includes('import-')||path.includes('/images')?45000:20000);
 try{
  let r;try{r=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});}catch{throw Error(controller.signal.aborted?'The request timed out. A save may still have completed. Search for this product before retrying. Code: PRODUCT_REQUEST_TIMEOUT.':'The connection failed. The save is not confirmed. Keep your entries and search for this product before retrying. Code: PRODUCT_CONNECTION_FAILED.');}
  let d;try{d=await r.json();}catch{if(r.status===401||r.status===403)clear();throw Error('The response could not be read (HTTP '+r.status+'). A save is not confirmed. Code: PRODUCT_RESPONSE_UNREADABLE.');}
  if(!r.ok){if(r.status===401||r.status===403){clear();throw Error('Product access ended. Return to Workspace to sign in.');}const code=safeCodes.has(d?.error)?d.error:'PRODUCT_REQUEST_FAILED';throw Error((errors[code]||'The save is not confirmed. Keep your entries and search for this product before retrying.')+' Code: '+code+' (HTTP '+r.status+').');}
  return d;
 }finally{clearTimeout(timer);}
}
function controls(){el('starter-setup').hidden=detailPage||me?.role!=='admin';pricingControls();el('csv-import-link').hidden=me?.role!=='admin';const editable=can(record?.version?'products.edit':'products.create');el('fields').disabled=busy||!editable;el('save').hidden=!editable;el('save').disabled=busy;el('new').hidden=!can('products.create');el('duplicate').hidden=!record?.version||!can('products.create');el('reload').hidden=!record?.version;el('prev').disabled=busy||page===1;el('next').disabled=busy||page*50>=total;el('backup-link').hidden=me?.role!=='admin';el('quotes-link').hidden=!can('quotes.view');el('supplier-import').hidden=!detailPage||!(can('products.create')||can('products.edit'));el('apply-import').disabled=busy||!importPreview||!editable;el('preview-image').disabled=busy||!el('candidate-list').value;el('save-candidate').disabled=busy||!candidate||!record?.version||!can('products.edit');el('image-upload-controls').hidden=!can('products.edit');el('upload-image').disabled=busy||!record?.version||!el('image-file').files?.length;}
async function run(fn){if(busy)return;busy=true;document.querySelectorAll('#workspace button,#workspace input,#workspace select,#workspace textarea').forEach(e=>e.disabled=true);try{await fn();}catch(e){if(/PRODUCT_CODE_EXISTS|INVALID_SUPPLIER|SUPPLIER_URL_INVALID/.test(e.message||''))el('internal-reference').open=true;status(e.message||'The action could not complete. Code: PRODUCT_ACTION_FAILED.','error',true);}finally{busy=false;el('save').textContent='Save product';document.querySelectorAll('#workspace button,#workspace input,#workspace select,#workspace textarea').forEach(e=>e.disabled=false);controls();}}
function leave(){return !dirty||window.confirm('Discard your unsaved product changes?');}
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
async function list(){
 const r=await api('/api/products?grouped=1&q='+encodeURIComponent(el('search').value)+'&state='+el('state').value+'&page='+page);total=r.total;el('rows').replaceChildren();
 for(const p of r.data){
  const tr=document.createElement('tr'),nameCell=document.createElement('td'),name=document.createElement('a');name.className='product-link';name.href=p.group?'/products/options/'+p.group+'?'+catalogueQuery():productURL(p.id);name.textContent=p.data.name;nameCell.append(name);tr.append(nameCell);
  for(const v of [p.data.category,p.group?'Choose options':p.data.pricing?.mode==='grid'?'Option prices':p.data.unit_price?p.data.unit_price+' / '+p.data.unit:'Price not set',p.group?'Per option':p.data.vat_rate!==''?p.data.vat_rate+'%':'Not set',p.active?'Active':p.data.pricing?'Inactive / pricing setup':'Archived']){const td=document.createElement('td');td.textContent=v;tr.append(td);}
  const td=document.createElement('td'),link=document.createElement('a');link.className='product-open';link.textContent='Open';link.href=p.group?'/products/options/'+p.group+'?'+catalogueQuery():productURL(p.id);link.setAttribute('aria-label','Open '+p.data.name);td.append(link);tr.append(td);el('rows').append(tr);
 }
 el('count').textContent=r.total+' products · Page '+page;if(!detailPage)history.replaceState(null,'',catalogueURL());controls();
}
function fill(p,supplier=null){const changed=record?.id!==p.id;record=p;supplierRecord=supplier;fillPricing(p.data);for(const k of fields)el('p-'+k).value=p.data[k]??'';for(const k of Object.keys(supplierLimits))el('s-'+k).value=supplier?.data?.[k]??'';el('active').checked=p.active;el('edit').hidden=false;el('heading').textContent=p.version?'Product details':'New product';if(detailPage){el('page-heading').textContent=p.version?p.data.name:'New product';document.title='Custom U · '+(p.version?p.data.name:'New product');}el('internal-reference').open=false;el('revision').textContent=p.version?'Saved · product revision '+p.version+' · supplier revision '+(supplier?.version||0):'Unsaved';el('edit-status').textContent='';el('save-status').hidden=true;el('save-status').textContent='';if(changed){el('image-gallery').replaceChildren();el('image-count').textContent='';el('image-file').value='';el('image-caption').value='';uploadId=null;}el('product-images').hidden=!p.version;dirty=false;controls();}
function fresh(source){const supplier=source&&supplierRecord?{data:{...supplierRecord.data},version:0}:null;const id=crypto.randomUUID();fill({id,version:0,active:true,data:source?{...source.data,code:'P-'+id.replaceAll('-','')}:{unit:'Each',code:'P-'+id.replaceAll('-','')}},supplier);syncProductURL('new');dirty=!!source;status(source?'Copy ready. Review and save as a new product. Images are not copied.':'Enter the product details, selling price and VAT rate.');}
el('new').onclick=()=>navigateProduct(productURL('new'));el('duplicate').onclick=()=>{if(leave())fresh(record);};
el('fields').oninput=()=>{dirty=true;status('Unsaved changes. Click Save product to apply them.');};
const fieldLabels={code:'Product code',name:'Product name',category:'Category',description:'Description',unit:'Unit',unit_price:'Selling price',vat_rate:'VAT rate',finish:'Finish / branding method',placement:'Placement'};
const fieldLimits={code:40,name:160,category:80,description:800,unit:20,finish:160,placement:160};
function validatedProduct(){
 const data={},pricing=readPricing();
 for(const k of fields){
  const input=el('p-'+k),v=input.value.trim(),label=fieldLabels[k];
  if((['code','name','unit'].includes(k)||!pricing&&['unit_price','vat_rate'].includes(k))&&!v)throw Error(label+': enter a value before saving.');
  if(k==='code'&&!/^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$/.test(v))throw Error('Product code: use letters, numbers, dots, underscores or ordinary hyphens, for example TEST-CAT-105.');
  if(fieldLimits[k]&&v.length>fieldLimits[k])throw Error(label+': use no more than '+fieldLimits[k]+' characters.');
  if(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/.test(v)||k!=='description'&&/[\t\r\n]/.test(v))throw Error(label+': remove line breaks or control characters.');
  if(k==='unit_price'||k==='vat_rate'){
   if(pricing&&v===''){data[k]='';continue;}
   const max=k==='unit_price'?1000000:100;
   if(input.validity.badInput||!/^[0-9]{1,7}(\.[0-9]{1,2})?$/.test(v)||Number(v)>max)throw Error(label+': enter a number from 0 to '+max+' with at most two decimal places, for example 10.00.');
  }
  data[k]=v;
 }
 if(pricing){data.pricing=pricing;if(pricing.mode==='grid')data.unit_price='';if(el('active').checked&&(data.vat_rate===''||pricing.minimum===''||(pricing.mode==='grid'?!pricing.options.some(o=>Number(o.price)>0):!(Number(data.unit_price)>0))))throw Error('Keep Active unchecked until VAT, minimum line price (0 for none), and a positive price are entered.');}
 return data;
}
function savedMatches(saved,payload){
 return saved&&saved.id===payload.id&&Number.isInteger(saved.version)&&saved.version>=1&&[payload.version,payload.version+1].includes(saved.version)&&saved.active===payload.active&&saved.data&&samePricing(saved.data.pricing,payload.data.pricing)&&fields.every(k=>typeof saved.data[k]==='string'&&(k==='unit_price'||k==='vat_rate'?(saved.data[k]===''||payload.data[k]===''?saved.data[k]===payload.data[k]:Number(saved.data[k])===Number(payload.data[k])):saved.data[k]===payload.data[k]));
}
el('edit').onsubmit=e=>{
 e.preventDefault();if(busy)return;
 if(!record){status('Open New product or a saved product before saving.','error',true);return;}
 if(!can(record.version?'products.edit':'products.create')){status('Your account does not have permission to save this product.','error',true);return;}
 let payload;try{payload={op:'save',id:record.id,version:record.version,active:el('active').checked,data:validatedProduct(),supplier:validatedSupplier(),supplier_version:supplierRecord?.version||0};}catch(error){if(error.message.startsWith('Product code:')||error.message.startsWith('Supplier '))el('internal-reference').open=true;status(error.message,'error',true);return;}
 run(async()=>{
  el('save').textContent='Saving…';status('Saving product…');
  const r=await api('/api/products/save',payload);
  if(!savedMatches(r?.data,payload)||!supplierMatches(r?.supplier,payload))throw Error('The server did not confirm the saved values. Keep your entries and search for this product before retrying. Code: PRODUCT_SAVE_RESPONSE.');
  fill(r.data,r.supplier);syncProductURL(r.data.id);let imagesRefreshed=true;
  try{await loadImages();}catch(error){if(!me)throw error;imagesRefreshed=false;el('image-status').textContent='Product saved, but images could not refresh. Reopen the product to try again.';}
  const savedMessage=imagesRefreshed?'Product saved · revision '+r.data.version+'.':'Product saved · revision '+r.data.version+'. Images could not refresh; reopen the product.';
  status(savedMessage,'success',true);
  try{if(!detailPage)await list();if(me)status(savedMessage,'success');}catch(error){if(me)status('Product saved, but the list could not refresh. Use Refresh catalogue.','success',true);else status(error.message,'error',true);}
 });
};
el('reload').onclick=()=>run(async()=>{if(record?.version&&leave()){const r=await api('/api/products/'+record.id);fill(r.data,r.supplier);await loadImages();status('Reloaded the saved product.');}});
el('close').onclick=()=>navigateProduct(catalogueURL());
el('search-button').onclick=()=>run(async()=>{page=1;await list();});el('state').onchange=()=>run(async()=>{page=1;await list();});
el('prev').onclick=()=>run(async()=>{if(page>1){page--;await list();}});el('next').onclick=()=>run(async()=>{if(page*50<total){page++;await list();}});
el('refresh').onclick=()=>run(async()=>{await list();status(dirty?'Catalogue refreshed. Your unsaved product changes are still here.':'Catalogue refreshed.');});
el('logout').onclick=()=>run(async()=>{if(!leave())return;clear();await api('/api/logout',{});status('Signed out.');});
Object.assign(errors,{
 INVALID_SUPPLIER:'Check the supplier URL, currency and unit cost. Use a three-letter currency such as USD when entering a cost.',
 SUPPLIER_URL_INVALID:'Use a complete public HTTPS product link without a login or password in the address.',
 SUPPLIER_INPUT_URL_INVALID:'The pasted link could not be read as a public HTTPS address. Paste the product address beginning with https://, without any surrounding sentence or login details.',
 SUPPLIER_REDIRECT_INVALID:'Your original link was accepted, but the supplier redirected to an address the importer cannot follow. Use the final public HTTPS product address from your browser, or enter the details manually.',
 SUPPLIER_ADDRESS_BLOCKED:'This link is not a permitted public website. Enter the details manually.',
 SUPPLIER_UNAVAILABLE:'The supplier could not be reached. You can enter the details manually and upload your own image.',
 SUPPLIER_TIMEOUT:'The supplier took too long to respond. Try later or enter the details manually.',
 SUPPLIER_PAGE_RESTRICTED:'This supplier requires browser access, sign-in or has blocked automated imports. Enter the details manually and upload your own image.',
 SUPPLIER_REDIRECT_LIMIT:'The supplier link redirected too many times. Use its final public product-page link.',
 SUPPLIER_CONTENT_UNSUPPORTED:'This page or image format cannot be imported. Enter the details manually or upload a PNG, JPG or WebP image.',
 SUPPLIER_FILE_TOO_LARGE:'The supplier response is too large. Save an appropriate image locally and use the upload option.',
 SUPPLIER_NO_PRODUCT_DETAILS:'No product details were found. Enter them manually.',
 PRODUCT_IMAGE_BUSY:'Another image or import is being processed. Please try again shortly.',
 IMAGE_INPUT_SIZE:'Choose an image up to 12 MB.',IMAGE_PIXEL_LIMIT:'Choose an image up to 24 megapixels.',
 IMAGE_ANIMATED:'Choose a still PNG, JPG or WebP image.',IMAGE_INVALID:'This image could not be opened. Choose a valid PNG, JPG or WebP.',
 IMAGE_OUTPUT_SIZE:'This image could not be made small enough for the catalogue.',INVALID_IMAGE:'Check the selected image and caption.',
 IMAGE_STORAGE_LIMIT:'The retained catalogue images have reached their limit. Contact your administrator.',
 IMAGE_ID_CONFLICT:'This upload ID already belongs to a different image. Select the file again before uploading.',
 IMAGE_INTEGRITY_FAILED:'The saved image could not be verified. Keep your original and report this code.'
});
for(const code of Object.keys(errors))safeCodes.add(code);
function validatedSupplier(){
 const d={};
 for(const [k,limit] of Object.entries(supplierLimits)){
  let v=el('s-'+k).value.trim();if(k==='currency')v=v.toUpperCase();
  if(v.length>limit||/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/.test(v)||k!=='specifications'&&/[\r\n\t]/.test(v))throw Error('Supplier '+k+': check the length and remove control characters.');
  if(k==='cost'&&v&&(!/^[0-9]{1,7}(\.[0-9]{1,2})?$/.test(v)||Number(v)>1000000))throw Error('Supplier unit cost: enter a number from 0 to 1000000 with up to two decimal places.');
  if(k==='currency'&&v&&!/^[A-Z]{3}$/.test(v))throw Error('Supplier currency: use a three-letter code such as USD.');
  if(k==='url'&&v){try{const u=new URL(v);if(u.protocol!=='https:'||u.username||u.password||u.port&&u.port!=='443'||/[\s\\<>"']/.test(v))throw Error();u.hash='';v=u.href;if(v.length>2048)throw Error();}catch{throw Error('Supplier URL: use a complete HTTPS link.');}}
  d[k]=v;
 }
 if(d.cost&&!d.currency)throw Error('Enter the supplier currency when entering a supplier unit cost.');
 return d;
}
function supplierMatches(s,p){return s&&s.id===p.id&&Number.isInteger(s.version)&&s.version>=1&&[p.supplier_version,p.supplier_version+1].includes(s.version)&&s.data&&Object.keys(supplierLimits).every(k=>typeof s.data[k]==='string'&&(k==='cost'&&p.supplier.cost!==''?Number(s.data[k])===Number(p.supplier.cost):s.data[k]===p.supplier[k]));}
function clearCandidate(){candidate=null;if(candidateObjectURL){URL.revokeObjectURL(candidateObjectURL);candidateObjectURL=null;}el('candidate-image').removeAttribute('src');el('candidate-review').hidden=true;el('candidate-info').textContent='';}
function clearImportReport(){el('import-diagnostics').hidden=true;el('import-diagnostics').open=false;el('import-report').value='';el('import-report-status').textContent='';el('import-report-label').hidden=true;el('download-import-report').hidden=true;}
function showImportReport(report){
 clearImportReport();if(me?.role!=='admin')return;
 el('import-diagnostics').hidden=false;
 if(!report||report.report_format!=='custom-u-supplier-import-1'){
  el('import-report-status').textContent='This server did not provide an import report. Deploy all production_history files from update 106.3, then try Preview supplier details again.';return;
 }
 el('import-report').value=JSON.stringify(report,null,2);el('import-report-label').hidden=false;el('download-import-report').hidden=false;
 el('import-report-status').textContent='This report describes the same page used for this preview. It contains counts and version information, without page contents, login details or URL query strings. Download it to help investigate missing image choices.';
}
el('download-import-report').onclick=()=>run(async()=>{
 const current=await api('/api/session');me=current.me;
 if(me?.role!=='admin'){clearImportReport();return;}
 if(!el('import-report').value)return;
 const url=URL.createObjectURL(new Blob([el('import-report').value+'\n'],{type:'application/json'}));
 const link=document.createElement('a');link.href=url;link.download='CustomU_Supplier_Import_Report_106_3.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
function clearImport(){importPreview=null;clearCandidate();clearImportReport();el('supplier-url').value='';el('candidate-list').replaceChildren();el('candidate-status').textContent='';el('candidate-controls').hidden=true;el('import-preview').textContent='';el('import-status').textContent='';el('import-review').hidden=true;}
async function messageWork(id,fn){el(id).textContent='Working…';try{await fn();}catch(e){if(me)el(id).textContent=e.message;throw e;}}
el('preview-supplier').onclick=()=>run(()=>messageWork('import-status',async()=>{
 clearCandidate();clearImportReport();importPreview=null;el('import-review').hidden=true;el('candidate-list').replaceChildren();el('candidate-status').textContent='';el('candidate-controls').hidden=true;
 const r=await api('/api/products/import-preview',{url:el('supplier-url').value.trim()});
 if(!r||!r.product||!r.supplier||!Object.keys(supplierLimits).every(k=>typeof r.supplier[k]==='string')||!['name','description','category'].every(k=>typeof r.product[k]==='string')||!Array.isArray(r.images)||r.images.length>12||!r.images.every(x=>typeof x==='string'&&x.startsWith('https://'))||!Array.isArray(r.warnings)||!r.warnings.every(x=>typeof x==='string'))throw Error('The supplier preview could not be verified.');
 importPreview=r;showImportReport(r.diagnostics);const parts=['Product: '+r.product.name,'Description: '+r.product.description,'Category: '+r.product.category,'Supplier: '+r.supplier.supplier,'Supplier code: '+r.supplier.sku,'Supplier cost: '+(r.supplier.cost?r.supplier.currency+' '+r.supplier.cost:'Not found'),'Colours: '+r.supplier.colours,'Sizes: '+r.supplier.sizes,'Specifications: '+r.supplier.specifications,...r.warnings];
 el('import-preview').textContent=parts.join('\n\n');for(const [i,url] of r.images.entries()){const option=document.createElement('option');option.value=url;option.textContent='Image '+(i+1)+' — '+new URL(url).hostname;el('candidate-list').append(option);}el('candidate-controls').hidden=r.images.length===0;el('candidate-status').textContent=r.images.length?r.images.length+' supplier image '+(r.images.length===1?'choice':'choices')+' found. Choose one and click Preview selected image. Confirm it shows the correct product and option.':'No supplier images were found in the page received. You can save the product details, then use Choose image under Product images to upload a PNG, JPG or WebP.';el('import-review').hidden=false;el('import-status').textContent='Preview ready. Nothing has been saved. Review it, then apply the details.';
}));
el('apply-import').onclick=()=>{
 if(busy||!importPreview)return;
 if(record&&!can(record.version?'products.edit':'products.create'))return;
 if(record&&(dirty||record.version)&&!window.confirm('Replace the name, description, category and supplier fields in this form with the preview? Your selling price, VAT, code, unit and branding fields will stay as entered. Nothing is saved until Save product.'))return;
 if(!record)fresh();
 for(const k of ['name','description','category'])el('p-'+k).value=importPreview.product[k];
 for(const k of Object.keys(supplierLimits))el('s-'+k).value=importPreview.supplier[k];
 dirty=true;status('Supplier details applied to the form. Review them and enter your selling price and VAT before saving.');el('heading').scrollIntoView?.({block:'start'});controls();
};
el('candidate-list').onchange=()=>{clearCandidate();controls();};
el('preview-image').onclick=()=>run(()=>messageWork('import-status',async()=>{
 clearCandidate();const r=await api('/api/products/import-image',{url:el('candidate-list').value});
 if(!r||typeof r.content_base64!=='string'||r.content_base64.length>682668||!Number.isInteger(r.width)||!Number.isInteger(r.height)||typeof r.source_url!=='string')throw Error('The image preview could not be verified.');
 const bytes=Uint8Array.from(atob(r.content_base64),c=>c.charCodeAt(0));candidate={...r,id:crypto.randomUUID(),product:null};candidateObjectURL=URL.createObjectURL(new Blob([bytes],{type:'image/webp'}));el('candidate-image').src=candidateObjectURL;el('candidate-info').textContent=r.width+' × '+r.height+' pixels · '+Math.ceil(bytes.length/1024)+' KB catalogue copy';el('candidate-review').hidden=false;el('import-status').textContent='Review the image. It has not been saved to the product.';
}));
async function loadImages(){
 el('image-gallery').replaceChildren();el('image-count').textContent='';el('image-status').textContent='';if(!record?.version){el('product-images').hidden=true;return;}
 const product=record.id,r=await api('/api/products/'+product+'/images');if(!record||record.id!==product)return;
 if(!r||!Array.isArray(r.data)||r.data.length>50)throw Error('The image list could not be verified.');
 el('product-images').hidden=false;el('image-count').textContent=r.data.filter(i=>i.active).length+' active images · '+r.data.length+' of 50 retained slots · '+(Number(r.bytes_used||0)/1000000).toFixed(2)+' of 40 MB used across the catalogue';
 for(const item of r.data){
  const card=document.createElement('div');card.className='image-card';
  const image=document.createElement('img');image.alt=item.caption||item.filename;image.loading='lazy';image.src='/api/products/'+product+'/images/'+item.id;card.append(image);
  const text=document.createElement('p');text.textContent=(item.active?'Active':'Archived')+' · '+item.filename+(item.caption?' — '+item.caption:'');card.append(text);
  const link=document.createElement('a');link.textContent='Download catalogue copy';link.href=image.getAttribute('src')+'?download=1';card.append(link);
  if(can('products.edit')){const button=document.createElement('button');button.type='button';button.textContent=item.active?'Archive image':'Reactivate image';button.onclick=()=>run(()=>messageWork('image-status',async()=>{const result=await api('/api/products/'+product+'/images/'+item.id+'/active',{version:item.version,active:!item.active});if(!result?.data||result.data.id!==item.id||result.data.active!==!item.active)throw Error('The image status was not confirmed. Reopen the product.');await loadImages();el('image-status').textContent='Image status saved.';}));card.append(document.createElement('br'),button);}
  el('image-gallery').append(card);
 }
}
function readBase64(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('The selected file could not be read.'));reader.readAsDataURL(file);});}
el('image-file').onchange=()=>{uploadId=crypto.randomUUID();el('image-status').textContent='';controls();};
el('upload-image').onclick=()=>run(()=>messageWork('image-status',async()=>{
 const file=el('image-file').files?.[0];if(!file||!record?.version)return;if(file.size>12000000)throw Error('Choose an image up to 12 MB.');
 const product=record.id;uploadId=uploadId||crypto.randomUUID();const result=await api('/api/products/'+product+'/images/add',{id:uploadId,filename:file.name,caption:el('image-caption').value.trim(),source_url:'',data:await readBase64(file)});
 if(!result?.data||result.data.id!==uploadId||result.data.product_id!==product)throw Error('The image save was not confirmed. Keep the file selected and retry.');
 await loadImages();el('image-file').value='';uploadId=null;el('image-status').textContent='Catalogue image saved and verified. Included in the next workspace backup.';
}));
el('save-candidate').onclick=()=>run(()=>messageWork('import-status',async()=>{
 if(!candidate||!record?.version||!can('products.edit'))return;
 if(candidate.product&&candidate.product!==record.id)candidate.id=crypto.randomUUID();candidate.product=record.id;
 const result=await api('/api/products/'+record.id+'/images/add',{id:candidate.id,filename:'supplier-image.webp',caption:record.data.name.slice(0,200),source_url:candidate.source_url,data:candidate.content_base64});
 if(!result?.data||result.data.id!==candidate.id||result.data.product_id!==record.id)throw Error('The supplier image save was not confirmed. Keep this preview and retry.');
 await loadImages();el('import-status').textContent='Supplier image saved and verified for '+record.data.name+'.';
}));

run(async()=>{const r=await api('/api/session');me=r.me;if(!r.crm_enabled||!can('products.view')){clear();throw Error('Product catalogue access is required. Return to Workspace.');}el('workspace').hidden=false;el('identity').textContent=me.email;
 if(detailPage){
  if(productPath[1]==='new'){if(!can('products.create'))throw Error('Your account cannot create products. Use Back to products.');fresh();}
  else{const saved=await api('/api/products/'+productPath[1]);if(!saved?.data||saved.data.id!==productPath[1])throw Error('The saved product could not be verified. Use Back to products.');fill(saved.data,saved.supplier);await loadImages();status('Saved product opened.');}
 }else{await list();status('Choose a product or add a new one.');}
});

function pricingControls(){
 const mode=el('pricing-mode').value,configured=mode!=='legacy';
 el('pricing-settings').hidden=!configured;
 el('pricing-grid').hidden=mode!=='grid';
 el('p-unit_price').closest('label').hidden=mode==='grid';
 el('price-label').textContent=mode==='area'?'Rate per square foot (BSD, before VAT)':'Selling price (BSD, before VAT)';
 el('p-unit').disabled=busy||['area','grid'].includes(mode);
 el('pricing-help').textContent=mode==='area'?'Quotes and invoices will ask for width, height, inches or feet, and number of pieces. The saved rate is per square foot.':mode==='grid'?'Each row is an exact option at a whole-run price. Put size, sides and finish in its customer-visible label. Blank or zero prices cannot be selected. No interpolation between quantities.':'Quotes and invoices will ask for a whole-number quantity. Use a custom item for fractional quantities.';
}
function priceOption(row={label:'',copies:'1',price:''}){
 if(el('pricing-options').children.length>=50)throw Error('Use up to 50 pricing options per product.');
 const box=document.createElement('div');box.className='line grid';
 for(const [key,label] of [['label','Option label (shown to customer)'],['copies','Copies / pieces in one run'],['price','Whole-run price BSD, before VAT']]){
  const l=document.createElement('label');l.textContent=label;const i=document.createElement('input');i.dataset.option=key;i.value=row[key];
  if(key==='label')i.maxLength=100;else{i.type='number';i.min=key==='copies'?'1':'0.01';i.max='1000000';i.step=key==='copies'?'1':'0.01';}
  l.append(i);box.append(l);
 }
 const b=document.createElement('button');b.type='button';b.textContent='Remove option';b.onclick=()=>{box.remove();dirty=true;status('Unsaved pricing changes.');};box.append(b);el('pricing-options').append(box);
}
function fillPricing(data){el('pricing-mode').querySelector('[value=legacy]').disabled=!!data.pricing;el('pricing-mode').value=data.pricing?.mode||'legacy';el('pricing-minimum').value=data.pricing?.minimum??'';el('pricing-options').replaceChildren();for(const o of data.pricing?.options||[])priceOption(o);pricingControls();}
function readPricing(){
 const mode=el('pricing-mode').value;if(mode==='legacy')return null;
 const minimum=el('pricing-minimum').value.trim();
 const normal=(v,label)=>{if(v==='')return '';if(!/^\d{1,7}(\.\d{1,2})?$/.test(v)||Number(v)>1000000)throw Error(label+': enter a price with at most two decimals.');return Number(v).toFixed(2);};
 const p={mode,minimum:normal(minimum,'Minimum line price'),options:[]},seen=new Set();
 if(mode==='grid')for(const box of el('pricing-options').children){
  const o=Object.fromEntries([...box.querySelectorAll('input')].map(i=>[i.dataset.option,i.value.trim()]));
  if(!o.label||o.label.length>100||/[\x00-\x1f\x7f]/.test(o.label)||seen.has(o.label.toLowerCase()))throw Error('Give every pricing option a different label.');
  seen.add(o.label.toLowerCase());
  if(!/^[1-9][0-9]{0,6}$/.test(o.copies)||Number(o.copies)>1000000)throw Error('Copies per run must be a positive whole number.');
  o.price=normal(o.price,'Option price');p.options.push(o);
 }
 return p;
}
el('pricing-mode').onchange=()=>{const mode=el('pricing-mode').value;if(mode==='area')el('p-unit').value='Sqft';if(mode==='grid'){el('p-unit').value='Run';el('p-unit_price').value='';}pricingControls();dirty=true;};
el('pricing-add').onclick=()=>{try{priceOption();dirty=true;}catch(e){status(e.message,'error',true);}};
// Only this create-only setup operation is retried. Product saves are never
// automatically retried here. The database keeps existing IDs/codes/names.
let starterProgress=null;
function starterMessage(text){
 const progress=el('starter-progress');if(progress)progress.textContent=text;
 status(text);
}
function clearStarterProgress(){starterProgress=null;const p=el('starter-progress');if(p)p.textContent='';el('setup-starters').textContent='Add unpriced product starters';}
function starterError(message,retryable=false){const e=new Error(message);e.retryable=retryable;return e;}
async function starterRequest(path,body){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
 try{
  let r;try{r=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});}
  catch{throw starterError('The setup request timed out or lost its connection.',true);}
  if(r.status===401||r.status===403){clear();throw starterError('Product access ended. Return to Workspace to sign in, then resume catalogue setup.');}
  if(r.status===404)throw starterError('The setup update is not available yet. Wait for deployment to finish and reload Products.');
  const retryable=r.status===408||r.status===429||r.status>=500;
  let data;try{data=await r.json();}catch{throw starterError('The setup response could not be read (HTTP '+r.status+').',retryable||r.ok);}
  if(!r.ok){
   if(data?.error==='STARTER_SOURCE_CHANGED')throw starterError('The product starter file changed. Reload Products and run setup again; existing products will be kept.');
   throw starterError('The server did not confirm this setup request (HTTP '+r.status+').',retryable);
  }
  return data;
 }finally{clearTimeout(timer);}
}
async function starterWithRetry(path,body){
 try{return await starterRequest(path,body);}
 catch(e){
  if(!e.retryable||me?.role!=='admin')throw e;
  starterMessage('Connection interrupted. Rechecking the same small batch; any products already saved will be kept.');
  await new Promise(resolve=>setTimeout(resolve,750));
  return await starterRequest(path,body);
 }
}
el('setup-starters').onclick=()=>run(async()=>{
 try{
  starterMessage('Checking the product starter list…');
  const plan=await starterWithRetry('/api/products/setup-starters/plan');
  if(!plan||!Number.isInteger(plan.total)||plan.total<1||plan.total>250||plan.batch_size!==10||typeof plan.source_sha256!=='string'||!/^[a-f0-9]{64}$/.test(plan.source_sha256))throw starterError('The setup plan could not be verified. Reload Products and try again.');
  if(!starterProgress||starterProgress.source_sha256!==plan.source_sha256||starterProgress.total!==plan.total||starterProgress.offset===plan.total)
   starterProgress={source_sha256:plan.source_sha256,total:plan.total,offset:0,added:0,existing:0};
  const progress=starterProgress;
  el('setup-starters').textContent='Setting up catalogue…';
  while(progress.offset<progress.total){
   if(me?.role!=='admin'||starterProgress!==progress)throw starterError('Product access ended. Sign in and resume catalogue setup.');
   const offset=progress.offset,next=Math.min(offset+plan.batch_size,progress.total);
   starterMessage('Checking products '+(offset+1)+'–'+next+' of '+progress.total+'. Existing products and prices are kept.');
   const r=await starterWithRetry('/api/products/setup-starters/batch',{add_unpriced_starters:true,source_sha256:progress.source_sha256,offset});
   if(starterProgress!==progress||me?.role!=='admin')throw starterError('Product access ended. Sign in and resume catalogue setup.');
   if(!r||r.source_sha256!==progress.source_sha256||r.total!==progress.total||r.offset!==offset||r.next_offset!==next||!Number.isInteger(r.added)||!Number.isInteger(r.existing)||r.added<0||r.existing<0||r.added+r.existing!==next-offset)
    throw starterError('The last batch could not be verified.');
   progress.added+=r.added;progress.existing+=r.existing;progress.offset=next;
  }
  const done='Catalogue setup complete: all '+progress.total+' starters checked. '+progress.added+' additions confirmed; '+progress.existing+' already present and kept. Unpriced products remain inactive.';
  el('setup-starters').textContent='Check catalogue setup';starterMessage(done);
  el('state').value='inactive';el('search').value='';page=1;
  try{await list();if(me)starterMessage(done);}
  catch(e){if(!me)throw e;starterMessage(done+' The list did not refresh. Click Refresh catalogue.');}
 }catch(e){
  if(!me)throw e;
  el('setup-starters').textContent='Resume catalogue setup';
  const count=starterProgress?.offset||0;
  const paused='Setup paused after '+count+' starters were checked in this pass. '+e.message+' Click Resume catalogue setup to continue safely; anything already saved will be kept.';
  starterMessage(paused);throw Error(paused);
 }
});


function samePricing(a,b){if(!a||!b)return !a&&!b;return a.mode===b.mode&&a.minimum===b.minimum&&a.options.length===b.options.length&&a.options.every((o,i)=>['label','copies','price'].every(k=>o[k]===b.options[i][k]));}
