import fs from 'node:fs';import assert from 'node:assert/strict';import {JSDOM} from 'jsdom';
const uid='12900000-0000-4000-8000-000000000001',tick=()=>new Promise(r=>setTimeout(r,5));
async function until(f){for(let i=0;i<200;i++){if(f())return;await tick();}throw Error('Clock UI did not settle');}
async function fixture(path='/quotes/new',mode='normal',storage=null){
 const dom=new JSDOM('<main><header><h1>Quotes</h1></header><section id="workspace"></section></main>',{url:'https://clock.example.invalid'+path,runScripts:'outside-only'}),w=dom.window,d=w.document;
 w.matchMedia=()=>({matches:false});let shift=null,denied=false,reads=0;const writes=[],receipts=new Map();
 if(mode==='stale')shift={state:'in',last_in:'2026-11-22T14:34:20Z',day:'2026-11-22',corrected:false};
 if(storage)w.sessionStorage.setItem('customu.clock.pending.129.'+uid,storage);
 w.fetch=async(url,opts={})=>{const ok=data=>({ok:true,status:200,json:async()=>structuredClone(data)});
  if(url==='/api/session')return ok({me:{user_id:uid,role:'admin',email:'fixture@example.invalid'},crm_enabled:true});
  if(url==='/api/hr/clock'){reads++;if(denied)return {ok:false,status:403,json:async()=>({error:'ACCESS_DENIED'})};return ok({user_id:uid,now:'2026-11-25T15:00:00Z',shift});}
  if(url==='/api/hr/action'){
   const p=JSON.parse(opts.body);writes.push(p);let receipt=receipts.get(p.request_id);
   if(!receipt){shift={state:p.op==='clock_in'?'in':'out',last_in:'2026-11-25T15:00:00Z',day:'2026-11-25',corrected:false};receipt={data:{id:uid,data:shift,version:1}};receipts.set(p.request_id,receipt);}
   if(mode==='lost'){mode='normal';throw Error('response lost after commit');}
   return ok(receipt);
  }throw Error('Unexpected URL '+url);
 };
 w.eval(fs.readFileSync('production_history/static/workspace-shell.js','utf8'));w.eval(fs.readFileSync('production_history/static/workspace-clock.js','utf8'));
 await until(()=>d.querySelector('.cu-clock button')&&!d.querySelector('.cu-clock button').disabled);
 return {w,d,writes,reads:()=>reads,button:()=>d.querySelector('.cu-clock button'),text:()=>d.querySelector('.cu-clock').textContent,deny:()=>denied=true,close:()=>w.close()};
}
for(const path of ['/','/quotes/new','/invoices/new','/mockups','/products','/hr/training']){
 const a=await fixture(path);assert.equal(a.d.querySelector('.cu-brand').nextElementSibling.id,'cu-clock');assert.equal(a.d.querySelector('#cu-clock').nextElementSibling.className,'cu-nav');assert.equal(a.button().textContent,'Clock in');assert.equal(a.writes.length,0);a.close();
}
{
 const a=await fixture();a.button().click();await until(()=>a.writes.length===1&&a.button().textContent==='Clock out'&&!a.button().disabled);assert.match(a.text(),/Clock-in saved/);assert.match(a.text(),/Nassau/);
 a.button().click();await until(()=>a.writes.length===2&&a.button().textContent==='Clock in'&&!a.button().disabled);assert.match(a.text(),/Clock-out saved/);assert.notEqual(a.writes[0].request_id,a.writes[1].request_id);
 a.deny();a.w.dispatchEvent(new a.w.Event('focus'));await until(()=>a.text().includes('access is unavailable'));assert.equal(a.button().textContent,'Refresh status');assert.doesNotMatch(a.text(),/Since/);
 a.w.CustomUShell.clear();assert.equal(a.d.querySelector('#cu-clock'),null);a.close();
}
{
 const a=await fixture('/invoices','lost');a.button().click();await until(()=>a.button().textContent==='Retry clock-in'&&!a.button().disabled);const stored=a.w.sessionStorage.getItem('customu.clock.pending.129.'+uid);assert.ok(stored);
 // Recreate the panel, as navigation/remount would, without losing the request identity.
 const host=a.d.getElementById('cu-clock');a.w.CustomUClock.mount(host);await until(()=>a.button().textContent==='Retry clock-in'&&!a.button().disabled);assert.equal(a.writes.length,1);a.button().click();await until(()=>a.writes.length===2&&a.button().textContent==='Clock out'&&!a.button().disabled);assert.deepEqual(a.writes[0],a.writes[1]);assert.equal(a.w.sessionStorage.getItem('customu.clock.pending.129.'+uid),null);
 const b=await fixture('/products','normal',stored);assert.equal(b.button().textContent,'Retry clock-in');assert.equal(b.writes.length,0);b.close();a.close();
}
{
 const a=await fixture('/hr','stale');assert.match(a.text(),/Missed clock-out/);assert.equal(a.button().textContent,'Open time records');await a.w.CustomUClock.action('clock_out');assert.equal(a.writes.length,0);a.close();
}
// The HR page explains stale shifts and limits correction controls to authorised users.
async function hr(admin){
 const dom=new JSDOM(fs.readFileSync('production_history/static/hr.html','utf8'),{url:'https://clock.example.invalid/hr',runScripts:'outside-only'}),w=dom.window,d=w.document,writes=[];
 const shift={id:uid,employee_id:uid,kind:'shift',version:1,data:{day:'2026-11-22',state:'in',intervals:[{in:'2026-11-22T14:34:20Z',out:null}],correction:null,scheduled_start:'2026-11-22T05:00:00Z'},totals:{worked_minutes:4000,regular_minutes:0,overtime_minutes:4000,needs_review:true}};
 w.fetch=async(url,opts={})=>{const ok=data=>({ok:true,status:200,json:async()=>structuredClone(data)});
  if(url==='/api/session')return ok({me:{user_id:uid,email:'fixture@example.invalid',role:admin?'admin':'office'},crm_enabled:true});
  if(url.startsWith('/api/hr?'))return ok({user_id:uid,now:'2026-11-25T15:00:00Z',records:[shift],people:[{id:uid,email:'fixture@example.invalid'}],admin,manager:admin,lieu_balances:[]});
  if(url==='/api/hr/action'){writes.push(JSON.parse(opts.body));return ok({data:shift});}throw Error(url);
 };
 w.HTMLElement.prototype.scrollIntoView=()=>{};w.confirm=()=>false;w.eval(fs.readFileSync('production_history/static/hr.js','utf8'));await until(()=>d.querySelector('#missed-clock-out'));
 return {w,d,writes,close:()=>w.close()};
}
{
 const a=await hr(true),notice=a.d.querySelector('#missed-clock-out');assert.equal(notice.querySelector('details').open,true);const b=[...notice.querySelectorAll('button')].find(b=>b.textContent.startsWith('Close test'));b.click();assert.equal(a.writes.length,0);a.w.confirm=()=>true;b.click();await until(()=>a.writes.length===1);assert.equal(a.writes[0].start,a.writes[0].end);assert.equal(a.writes[0].op,'shift_correct');a.close();
 const s=await hr(false);assert.equal(s.d.querySelector('#missed-clock-out button'),null);assert.match(s.d.querySelector('#clock').textContent,/Ask an HR manager or administrator/);s.close();
}
console.log('Clock UI PASS: above-menu placement across pages, saved statuses, clock actions, persistent safe retry, stale shifts, session revocation and authorised test correction.');
