import {JSDOM,VirtualConsole} from 'jsdom';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const cases=JSON.parse(fs.readFileSync('/tmp/invoice_payments132_views.json','utf8'));
const tick=()=>new Promise(r=>setTimeout(r,10));
const settle=async()=>{for(let n=0;n<5;n++)await tick();};
function domFor(page,query){
 const errors=[],vc=new VirtualConsole();vc.on('jsdomError',e=>{if(!e.message.includes('navigation'))errors.push(e);});
 const dom=new JSDOM(fs.readFileSync('production_history/static/'+page+'.html','utf8'),{url:'https://example.invalid/'+page+query,runScripts:'outside-only',virtualConsole:vc});
 dom.window.HTMLElement.prototype.scrollIntoView=()=>{};dom.window.confirm=()=>true;
 return {dom,w:dom.window,el:id=>dom.window.document.getElementById(id),errors};
}
const script=(w,name)=>w.eval(fs.readFileSync('production_history/static/'+name+'.js','utf8'));
const response=(result,status=200)=>({ok:status===200,status,json:async()=>structuredClone(result)});
{
 const {dom,w,el,errors}=domFor('invoices','?id='+cases.partial.data.id);let current=cases.partial,fail=false,pending=null,hold=false;
 w.fetch=async url=>{
  if(url==='/api/session')return response({me:{role:'admin',email:'test@example.invalid'},crm_enabled:true});
  if(url==='/api/invoices/defaults')return response({terms:'Terms'});
  if(url.startsWith('/api/invoices?'))return response({data:[],page:1,total:0});
  if(url==='/api/invoices/'+current.data.id){if(hold)return new Promise(resolve=>{pending=resolve;});return fail?response({error:'INVOICE_PAYMENTS_UNAVAILABLE'},503):response(current);}
  if(url==='/api/logout')return response({ok:true});
  throw Error(url);
 };
 script(w,'invoices');await settle();assert.equal(el('payment-state').textContent,'Partially paid');assert.match(el('payment-date').textContent,/24 Nov 2026/);assert.match(el('payment-totals').textContent,/Balance due: BSD 12.00/);
 current=cases.full;el('refresh-payments').click();await settle();assert.equal(el('payment-state').textContent,'Paid in full');assert.equal(el('payment-date').textContent,'Date paid: 26 Nov 2026');assert.equal(el('payment-history').querySelectorAll('tbody tr').length,2);
 current=cases.reversed;w.dispatchEvent(new w.PageTransitionEvent('pageshow',{persisted:true}));await settle();assert.equal(el('payment-state').textContent,'Partially paid');assert.equal(el('payment-history').querySelectorAll('tbody tr').length,1);
 fail=true;el('refresh-payments').click();await settle();assert.match(el('payment-state').textContent,/could not be confirmed/);assert.equal(el('payment-totals').textContent,'');assert.equal(el('payment-date').textContent,'');
 fail=false;current={...cases.full,data:{...cases.full.data,version:cases.full.data.version+1}};el('refresh-payments').click();await settle();assert.match(el('payment-state').textContent,/Reopen/);
 current=cases.full;hold=true;el('refresh-payments').click();await settle();assert.ok(pending);el('logout').click();await settle();pending(response(cases.full));await settle();assert.equal(el('payment-status').hidden,true);assert.equal(el('payment-history').textContent,'');assert.equal(el('workspace').hidden,true);assert.equal(errors.length,0,errors.map(e=>e.message));dom.window.close();
}
for(const kind of ['quote','invoice','catalogue']){
 const {dom,w,el,errors}=domFor('email','?kind='+kind+'&id='+cases.full.data.id),created=[],revoked=[],calls=[];
 w.URL.createObjectURL=blob=>{created.push(blob);return 'blob:https://example.invalid/review-'+kind;};w.URL.revokeObjectURL=url=>revoked.push(url);
 const context={send_allowed:true,configured:true,ready:true,number:'1440',version:2,recipient:'client@example.invalid',subject:'Document',message:'Please review',sender:'Custom U',reply_to:'office@example.invalid',test_delivery:false};
 w.fetch=async(url,opt={})=>{calls.push(url);if(url==='/api/session')return response({me:{email:'test@example.invalid'}});if(url.startsWith('/api/email/context'))return response(context);if(url.startsWith('/api/email/history'))return response({data:[]});if(url==='/api/email/preview')return response({review_token:'synthetic-token',pdf_base64:btoa('%PDF-exact-reviewed-bytes'),data:{...context,pdf_filename:'CustomU_'+kind+'.pdf'}});throw Error(url);};
 script(w,'page-navigation');script(w,'email');await settle();el('compose').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await settle();
 assert.equal(el('review').hidden,false);assert.equal(created.length,1);assert.equal(created[0].type,'application/pdf');
 assert.equal(el('pdf').hasAttribute('download'),false);assert.equal(el('pdf').target,'_blank');assert.ok(el('pdf').relList.contains('noopener'));assert.ok(el('pdf').relList.contains('noreferrer'));
 assert.equal(el('pdf-download').href,el('pdf').href);assert.equal(el('pdf-download').download,'CustomU_'+kind+'.pdf');assert.equal(el('back').target,'_self');
 assert.equal(el('send').disabled,true);el('pdf').dispatchEvent(new w.MouseEvent('click',{bubbles:true,cancelable:true}));await settle();assert.equal(el('pdf').target,'_blank');assert.equal(el('send').disabled,true);
 el('confirm').checked=true;el('confirm').dispatchEvent(new w.Event('change'));assert.equal(el('send').disabled,false);assert.ok(!calls.includes('/api/email/send'));
 w.dispatchEvent(new w.PageTransitionEvent('pagehide',{persisted:true}));assert.equal(revoked.length,0);
 el('message').value='Changed';el('message').dispatchEvent(new w.Event('input'));assert.equal(el('review').hidden,true);assert.equal(el('send').disabled,true);assert.equal(el('pdf').hasAttribute('href'),false);assert.equal(el('pdf-download').hasAttribute('href'),false);assert.equal(revoked.length,1);
 assert.equal(errors.length,0,errors.map(e=>e.message));dom.window.close();
}
console.log('PASS: payment status/date/history refresh, return navigation, unavailable/stale/cleared state; invoice/quote/catalogue pre-send PDF opens new tab, matching download, same-tab ordinary links, no automatic send, review invalidation.');
