import fs from 'node:fs';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
const staff='13000000-0000-4000-8000-000000000001',manager='13000000-0000-4000-8000-000000000002';
const cases=JSON.parse(fs.readFileSync('/tmp/early130_cases.json','utf8')).cases;
const tick=()=>new Promise(r=>setTimeout(r,5));
async function until(f){for(let i=0;i<200;i++){if(f())return;await tick();}throw Error('Attendance UI did not settle');}
async function fixture(name='pending',role='staff',own=role==='staff'){
 const c=cases.find(x=>x.name===name),shift=structuredClone(c.row);shift.employee_id=own?staff:manager;shift.totals=c.totals;
 const dom=new JSDOM(fs.readFileSync('production_history/static/hr.html','utf8'),{url:'https://attendance.example.invalid/hr',runScripts:'outside-only'}),w=dom.window,d=w.document,writes=[];
 w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.fetch=async(url,opts={})=>{const ok=x=>({ok:true,status:200,json:async()=>structuredClone(x)});
  if(url==='/api/session')return ok({me:{user_id:staff,role:role==='admin'?'admin':'office',email:'staff@example.invalid'},crm_enabled:true});
  if(url.startsWith('/api/hr?'))return ok({user_id:staff,now:'2026-12-08T22:00:00Z',records:[shift],people:[{id:staff,email:'staff@example.invalid'},{id:manager,email:'colleague@example.invalid'}],admin:role==='admin',manager:role!=='staff',lieu_balances:[]});
  if(url==='/api/hr/action'){writes.push(JSON.parse(opts.body));return ok({data:shift});}
  throw Error(url);
 };
 w.eval(fs.readFileSync('production_history/static/hr.js','utf8'));await until(()=>!d.getElementById('workspace').hidden);
 const button=text=>[...d.querySelectorAll('#shifts button')].find(x=>x.textContent===text);
 return {w,d,writes,button,settled:()=>!d.querySelector('#range button').disabled,close:()=>w.close()};
}
{
 const a=await fixture(),form=[...a.d.querySelectorAll('#shifts form')].find(f=>f.textContent.includes('Submit early time report'));
 assert.ok(form);assert.equal(a.button('Confirm reported activity'),undefined);
 assert.match(a.d.querySelector('#shifts').textContent,/30 early minutes remain unresolved/);
 const times=form.querySelectorAll('input[type=time]');times[0].value='08:40';times[1].value='08:55';form.querySelector('textarea').value='Prepared artwork';
 form.dispatchEvent(new a.w.Event('submit',{cancelable:true}));await until(()=>a.writes.length===1&&a.settled());
 assert.equal(a.writes[0].op,'early_work_report');assert.equal(a.writes[0].intervals[0].in,'2026-12-01T08:40');assert.equal(a.writes[0].kind,'work');
 const amended=[...a.d.querySelectorAll('#shifts form')].find(f=>f.textContent.includes('Submit early time report'));
 amended.querySelector('select').value='arrival';amended.querySelector('select').dispatchEvent(new a.w.Event('change'));
 assert.ok([...amended.querySelectorAll('input[type=time]')].every(x=>x.disabled));
 amended.dispatchEvent(new a.w.Event('submit',{cancelable:true}));await until(()=>a.writes.length===2&&a.settled());assert.deepEqual(a.writes[1].intervals,[]);assert.equal(a.writes[1].kind,'arrival');
 assert.match(a.d.querySelector('#timesheet').href,/timesheet.csv/);assert.match(a.d.querySelector('#time-off-credits').href,/time-off-credits.csv/);a.close();
}
{
 const a=await fixture('pending','manager');assert.equal(a.button('Submit early time report'),undefined);
 a.button('Confirm reported activity').click();assert.equal(a.writes.length,0);assert.match(a.d.querySelector('#status').textContent,/evidence or explanation/);
 const note=[...a.d.querySelectorAll('#shifts label')].find(x=>x.textContent.startsWith('Manager review note')).querySelector('textarea');note.value='Work verified with job record';a.button('Confirm reported activity').click();await until(()=>a.writes.length===1&&a.settled());assert.equal(a.writes[0].op,'early_work_review');assert.equal(a.writes[0].decision,'confirmed');
 assert.equal([...a.d.querySelectorAll('#shifts summary')].some(x=>x.textContent==='Review separate time-off credit'),false);
 const note2=[...a.d.querySelectorAll('#shifts label')].find(x=>x.textContent.startsWith('Manager review note')).querySelector('textarea');note2.value='Please identify the job';a.button('Request clarification').click();await until(()=>a.writes.length===2&&a.settled());assert.equal(a.writes[1].decision,'clarification');a.close();
 const self=await fixture('pending','manager',true);assert.equal(self.button('Confirm reported activity'),undefined);self.close();
}
for(const [name,phrase] of [['arrival','Arrival only confirmed'],['confirmed_work','Early work confirmed'],['corrected','Manager correction applied'],['test_zero','Zero worked time']]){
 const a=await fixture(name,'admin');assert.match(a.d.querySelector('#shifts').textContent,new RegExp(phrase));
 if(name==='corrected'||name==='test_zero')assert.equal(a.button('Confirm reported activity'),undefined);
 a.close();
}
// The persistent clock surfaces unresolved attendance while keeping clock-out available.
{
 const dom=new JSDOM('<main><header><h1>Quotes</h1></header><section id="workspace"></section></main>',{url:'https://attendance.example.invalid/quotes',runScripts:'outside-only'}),w=dom.window;w.matchMedia=()=>({matches:false});
 w.fetch=async url=>({ok:true,status:200,json:async()=>url==='/api/session'?{me:{user_id:staff,role:'office',email:'staff@example.invalid'},crm_enabled:true}:{user_id:staff,now:'2026-12-01T15:00:00Z',shift:{state:'in',day:'2026-12-01',last_in:'2026-12-01T13:30:00Z',early_review_status:'pending'}}});
 w.eval(fs.readFileSync('production_history/static/workspace-shell.js','utf8'));w.eval(fs.readFileSync('production_history/static/workspace-clock.js','utf8'));await until(()=>w.document.querySelector('.cu-clock a'));
 assert.equal(w.document.querySelector('.cu-clock a').getAttribute('href'),'/hr');assert.match(w.document.querySelector('.cu-clock a').textContent,/early/i);assert.equal(w.document.querySelector('.cu-clock button').textContent,'Clock out');w.close();
}
console.log('Early work UI PASS: staff report/amendment, arrival controls, manager evidence/clarification, self-review restriction, separate exports, correction displays and persistent clock review link.');
