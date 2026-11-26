import {JSDOM,VirtualConsole} from 'jsdom';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const fixture=JSON.parse(fs.readFileSync('/tmp/documents131_cases.json','utf8'));
const tick=()=>new Promise(r=>setTimeout(r,10));
async function boot(area,role='admin',permission=true){
 const rec=area==='quotes'?fixture.beforeQuote:fixture.invoice,requests=[],downloads=[],errors=[];
 const vc=new VirtualConsole();vc.on('jsdomError',e=>{if(!e.message.includes('navigation'))errors.push(e);});
 const dom=new JSDOM(fs.readFileSync('production_history/static/'+area+'.html','utf8'),{url:'https://example.invalid/'+area+'?id='+rec.id,runScripts:'outside-only',virtualConsole:vc});
 const w=dom.window;w.confirm=()=>true;w.HTMLElement.prototype.scrollIntoView=()=>{};w.URL.createObjectURL=()=> 'blob:test';w.URL.revokeObjectURL=()=>{};
 w.HTMLAnchorElement.prototype.click=function(){downloads.push({href:this.href,name:this.download,target:this.target});};
 w.fetch=async(url,opt={})=>{const body=opt.body?JSON.parse(opt.body):null;requests.push({url,body});let result;
  if(url==='/api/session')result={me:{role,email:'manager@example.invalid',permissions:{[area+'.view']:true,[area+'.edit']:true,[area+'.amend']:permission,'invoices.create':true,'invoices.view':true,'customers.view':true}},crm_enabled:true};
  else if(url==='/api/quotes/profile')result={data:{data:fixture.profile},default_terms:'Terms'};
  else if(url==='/api/invoices/defaults')result={terms:'Terms'};
  else if(url.includes('/api/customers/'))result={data:{id:fixture.customer,data:fixture.party,active:true},contacts:[]};
  else if(url==='/api/'+area+'/'+rec.id)result={data:rec};
  else if(url.startsWith('/api/'+area+'?'))result={data:[{...rec,customer:fixture.party.name,title:'Test',total_cents:2200,due_date:'2026-12-26'}],total:1,page:1};
  else if(url.endsWith('/pdf'))return {ok:true,status:200,headers:{get:k=>k==='Content-Type'?'application/pdf':'attachment; filename="CustomU_Test.pdf"'},blob:async()=>new w.Blob(['%PDF-test'])};
  else if(body?.op==='convert')result={data:{id:fixture.invoice.id}};
  else if(body?.op==='amend')result={data:{...rec,version:rec.version+1,...(area==='quotes'?{data:{...rec.data,title:body.data.title}}:{details:body.details,quote_snapshot:{...rec.quote_snapshot,data:{...rec.quote_snapshot.data,title:body.data.title}}})}};
  else throw Error('Unexpected request '+url+' '+JSON.stringify(body));
  return {ok:true,status:200,json:async()=>structuredClone(result)};
 };
 w.eval(fs.readFileSync('production_history/static/document-downloads.js','utf8'));
 w.eval(fs.readFileSync('production_history/static/'+area+'.js','utf8'));
 for(let n=0;n<10;n++)await tick();
 assert.equal(errors.length,0,errors.map(e=>e.stack).join('\n'));
 const el=id=>w.document.getElementById(id);
 assert.equal(el('workspace').hidden,false,el('status').textContent);assert.equal(el(area==='quotes'?'quote-form':'form').hidden,false,el('status').textContent);
 return {dom,w,el,requests,downloads,errors};
}
for(const area of ['quotes','invoices']){
 const s=await boot(area,'office',false);assert.equal(s.el('edit-finalised').hidden,true);assert.equal(s.el('save').disabled,true);s.dom.window.close();
 const {dom,w,el,requests,downloads}=await boot(area,'office',true);
 assert.equal(el('edit-finalised').hidden,false);el('edit-finalised').click();
 assert.equal(el('save').disabled,false);assert.equal(el('save').textContent,'Save revision');assert.equal(el('contact').disabled,true);
 assert.equal(el('issue-section').hidden,true);
 const title=el(area==='quotes'?'q-title':'direct-title');assert.equal(title.matches(':disabled'),false);title.value='UI revised title';title.dispatchEvent(new w.Event('input',{bubbles:true}));
 assert.equal(el('download-pdf').hidden,false);
 if(area==='invoices'){assert.equal(el('direct-fields').hidden,false);assert.equal(el('direct-lines').children.length,1);assert.equal(el('direct-lines').querySelector('[data-field="unit_price"]').matches(':disabled'),false);}
 el(area==='quotes'?'quote-form':'form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));for(let n=0;n<10;n++)await tick();
 const save=requests.find(r=>r.body?.op==='amend');assert.ok(save,el('status').textContent);assert.equal(save.body.data.title,'UI revised title');assert.equal(el('edit-finalised').hidden,false);assert.equal(el('cancel-revision').hidden,true);
 el('download-pdf').click();for(let n=0;n<5;n++)await tick();assert.equal(downloads.length,1);assert.equal(downloads[0].name,'CustomU_Test.pdf');assert.equal(downloads[0].target,'');assert.ok(el('status').textContent.includes('download started'));
 el('edit-finalised').click();title.value='Unsaved edit';title.dispatchEvent(new w.Event('input',{bubbles:true}));el('cancel-revision').click();assert.equal(title.value,'UI revised title');assert.equal(el('save').disabled,true);
 if(area==='quotes'){el('create-invoice').click();el('create-invoice').click();for(let n=0;n<10;n++)await tick();assert.equal(requests.filter(r=>r.body?.op==='convert').length,1);}
 dom.window.close();
}
{
 const downloads=[],paths=[],dom=new JSDOM(fs.readFileSync('production_history/static/catalogues.html','utf8'),{url:'https://example.invalid/catalogues',runScripts:'outside-only'}),w=dom.window;
 w.URL.createObjectURL=()=> 'blob:catalogue';w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=function(){downloads.push(this.download);};
 w.fetch=async path=>{paths.push(path);if(path.includes('/pdf'))return {ok:true,headers:{get:k=>k==='Content-Type'?'application/pdf':'attachment; filename="CustomU_Catalogue.pdf"'},blob:async()=>new w.Blob(['%PDF'])};return {ok:true,json:async()=>path==='/api/session'?{me:{role:'admin',email:'test@example.invalid'}}:{total:1,data:[{id:fixture.invoice.id,title:'Test catalogue',customer_name:'Test',item_count:1,active:true,version:1}]}};};
 w.eval(fs.readFileSync('production_history/static/document-downloads.js','utf8'));w.eval(fs.readFileSync('production_history/static/catalogues.js','utf8'));
 for(let n=0;n<10;n++)await tick();
 const button=[...w.document.querySelectorAll('#saved button')].find(b=>b.textContent==='Download PDF');assert.ok(button);button.click();for(let n=0;n<5;n++)await tick();assert.deepEqual(downloads,['CustomU_Catalogue.pdf']);assert.ok(paths.some(p=>p.endsWith('/pdf?download=1')));dom.window.close();
}
console.log('PASS: manager-only finalised editing, editable item dimensions/prices, immutable customer, revision save/cancel, download attachment without a new tab, one-click conversion double-click guard.');
