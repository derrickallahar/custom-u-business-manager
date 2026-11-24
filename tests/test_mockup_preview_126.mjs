import {JSDOM,requestInterceptor,VirtualConsole} from 'jsdom';
import fs from 'node:fs';import assert from 'node:assert/strict';
const uid=n=>'12600000-0000-4000-8000-'+String(n).padStart(12,'0');
const product={id:uid(1),active:true,data:{name:'Journal',code:'TEST'}};
const record={content_base64:'AQ==',sha256:'a'.repeat(64),width:720,height:900};
let images=[],uploads=[],previews=[],failUpload=true,releasePreview=null,holdPreview=false,failCanvas=false,permissions=true;
const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
const resources={interceptors:[requestInterceptor(req=>new Response(fs.readFileSync('production_history/static/'+new URL(req.url).pathname.split('/').pop(),'utf8'),{headers:{'Content-Type':'text/javascript'}}))]};
const dom=new JSDOM(fs.readFileSync('production_history/static/mockups.html','utf8'),{url:'https://fixture.invalid/mockups/new',runScripts:'dangerously',resources,pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){
 w.confirm=()=>true;w.URL.createObjectURL=()=> 'blob:preview';w.URL.revokeObjectURL=()=>{};w.HTMLElement.prototype.scrollIntoView=()=>{};
 const ctx={drawImage(){},clearRect(){},save(){},restore(){},translate(){},rotate(){},setLineDash(){},strokeRect(){},fillRect(){},getImageData(x,y,width,height){const data=new Uint8ClampedArray(width*height*4);for(let i=3;i<data.length;i+=4)data[i]=255;return {data};}};
 w.HTMLCanvasElement.prototype.getContext=()=>ctx;w.HTMLCanvasElement.prototype.getBoundingClientRect=function(){return {left:0,top:0,width:this.width,height:this.height};};
 w.Image=class{set src(v){this.naturalWidth=v.startsWith('/api/products')?720:100;this.naturalHeight=v.startsWith('/api/products')?900:50;queueMicrotask(()=>failCanvas?this.onerror?.():this.onload?.());}};
 w.fetch=async(path,opts={})=>{
  const reply=data=>({ok:true,status:200,json:async()=>structuredClone(data)});
  if(path==='/api/session')return reply({me:{role:'office',email:'test@example.invalid',permissions:{'products.view':true,'customers.view':true,'products.edit':permissions}}});
  if(path.endsWith('/images/add')){const body=JSON.parse(opts.body);uploads.push(body);if(!images.some(x=>x.id===body.id))images.push({id:body.id,product_id:product.id,active:true,filename:body.filename});if(failUpload){failUpload=false;throw new w.TypeError('Lost response');}return reply({data:images.find(x=>x.id===body.id)});}
  if(path.endsWith('/images'))return reply({data:images});
  if(path.startsWith('/api/products'))return reply({data:[product],total:1});
  if(path==='/api/mockups/preview'){const body=JSON.parse(opts.body);previews.push(body);if(holdPreview)await new Promise(r=>releasePreview=r);return reply({preview:record,logo:record,source_sha256:'b'.repeat(64),config:body.config});}
  return reply({data:[],total:0});
 };
}});
await new Promise(r=>dom.window.addEventListener('load',r,{once:true}));
const w=dom.window,e=id=>w.document.getElementById(id),event=(id,type='input')=>e(id).dispatchEvent(new w.Event(type,{bubbles:true}));
const tick=()=>new Promise(r=>setTimeout(r,5));async function until(fn){for(let i=0;i<200;i++){if(fn())return;await tick();}throw Error('Page did not settle');}const idle=()=>until(()=>!e('refresh').disabled);
const files=new Map();for(const id of ['logo','product-photo-file']){files.set(id,[]);Object.defineProperty(e(id),'files',{get:()=>files.get(id)});Object.defineProperty(e(id),'value',{get:()=>files.get(id).length?'selected.png':'',set:v=>{if(v==='')files.set(id,[]);}});}
function choose(id){files.set(id,[new w.File(['fixture'],'test.png',{type:'image/png'})]);event(id,'change');}
await idle();assert.deepEqual(errors,[]);
assert.equal(e('preview').disabled,false);e('preview').click();assert.match(e('preview-help').textContent,/Choose the product/);assert.equal(previews.length,0);
e('find-product').click();await idle();e('product-results').firstChild.click();await idle();assert.equal(e('source-image').value,'');
choose('product-photo-file');choose('logo');assert.equal(e('preview-working').disabled,false);assert.match(e('preview-help').textContent,/will upload/);
e('preview-working').click();await idle();assert.equal(uploads.length,1);assert.equal(previews.length,0);assert.equal(e('preview').disabled,false);assert.match(e('preview-help').textContent,/retry/i);
holdPreview=true;e('preview').click();await until(()=>releasePreview!==null);assert.equal(e('preview').disabled,true);assert.equal(e('preview-working').disabled,true);assert.deepEqual(uploads[0],uploads[1]);releasePreview();holdPreview=false;await idle();await until(()=>!e('manual-stage').hidden);
assert.equal(images.length,1);assert.equal(previews.length,1);assert.equal(previews[0].image_id,images[0].id);assert.equal(e('preview-image').hidden,false);assert.equal(files.get('product-photo-file').length,0);
e('preview').click();await idle();assert.equal(uploads.length,2,'Repeated preview does not upload another photo');assert.equal(previews.length,2);
files.set('logo',[]);event('logo','change');e('preview-working').click();assert.equal(previews.length,2);assert.match(e('preview-working-help').textContent,/customer logo or artwork/);assert.equal(w.document.activeElement,e('logo'));choose('logo');
e('width-number').value='';event('width-number');assert.equal(e('preview').disabled,false);e('preview').click();assert.equal(previews.length,2);assert.match(e('preview-help').textContent,/Check logo width/);assert.equal(w.document.activeElement,e('width-number'));
e('width-number').value='25';event('width-number');e('preview').click();await idle();await until(()=>!e('manual-stage').hidden);assert.equal(previews.length,3);
// Inch sizing remains enforced at submission, with actionable messages instead of a locked button.
e('measure-enabled').checked=true;event('measure-enabled','change');e('preview-working').click();assert.equal(previews.length,3);assert.match(e('preview-working-help').textContent,/width and height/);
e('reference-width').value='8';event('reference-width');e('reference-height').value='10';event('reference-height');e('preview').click();assert.equal(previews.length,3);assert.match(e('preview-help').textContent,/Mark area/);
e('mark-reference').click();e('preview').click();assert.match(e('preview-help').textContent,/Finish marking/);
const canvas=e('manual-canvas');function pointer(type,x,y){const ev=new w.MouseEvent(type,{clientX:x,clientY:y,button:0,bubbles:true,cancelable:true});Object.defineProperty(ev,'pointerId',{value:1});canvas.dispatchEvent(ev);}pointer('pointerdown',72,90);pointer('pointerup',648,810);
e('print-width-in').value='9';event('print-width-in');e('preview').click();assert.equal(previews.length,3);assert.match(e('preview-help').textContent,/do not fit/);
e('print-width-in').value='3';event('print-width-in');e('preview-working').click();await idle();assert.equal(previews.at(-1).config.scale.print_width,3);
// A manual-canvas image failure must leave a retry path available.
failCanvas=true;e('preview').click();await idle();await until(()=>e('manual-note').textContent.includes('could not be loaded'));assert.equal(e('preview').disabled,false);failCanvas=false;e('preview').click();await idle();await until(()=>!e('manual-stage').hidden);
permissions=false;e('refresh').click();await idle();assert.equal(e('editor').hidden,true);assert.equal(e('preview').disabled,true);assert.equal(e('preview-working').disabled,true);assert.deepEqual(errors,[]);
w.close();console.log('Preview 126 PASS: actual scripts, one-click photo upload, confirmed selection, lost-response retry, no duplicate uploads, both preview buttons, busy guard, missing-logo feedback, numeric and inch validation, canvas recovery and permissions.');
