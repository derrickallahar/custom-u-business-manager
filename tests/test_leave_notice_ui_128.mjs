import fs from 'node:fs';import assert from 'node:assert/strict';import {JSDOM} from 'jsdom';
const admin='12800000-0000-4000-8000-000000000001',staff='12800000-0000-4000-8000-000000000002';
const tick=()=>new Promise(r=>setTimeout(r,5));async function until(f){for(let i=0;i<200;i++){if(f())return;await tick();}throw Error('HR UI did not settle');}
async function fixture(role='admin'){
 const dom=new JSDOM(fs.readFileSync('production_history/static/hr.html','utf8'),{url:'https://fixture.invalid/hr',runScripts:'outside-only'}),w=dom.window,$=id=>w.document.getElementById(id),writes=[];w.HTMLElement.prototype.scrollIntoView=()=>{};
 const record=(id,type,eligible)=>({id,kind:'leave',employee_id:staff,version:1,created_at:'2026-11-25T15:00:00Z',data:{leave_type:type,start_date:'2026-11-26',end_date:'2026-11-26',start_time:type==='Personal'?'09:00':undefined,reason:'Private fixture',status:'pending'},notice:{required:type==='Personal'||type==='Vacation',eligible,error:eligible?null:type==='Personal'?'PERSONAL_NOTICE_REQUIRED':'VACATION_NOTICE_REQUIRED'}});
 const records=[record('late','Personal',false),record('vacation','Vacation',false),record('sick','Sick',true),record('emergency','Emergency',true)];
 let reject=false,uncertain=false;
 w.fetch=async(url,opts={})=>{const ok=data=>({ok:true,status:200,json:async()=>structuredClone(data)});
  if(url==='/api/session')return ok({me:{role,email:'fixture@example.invalid'},crm_enabled:true});
  if(url.startsWith('/api/hr?'))return ok({records,people:[{id:admin,email:'admin@example.invalid',role:'admin',active:true},{id:staff,email:'staff@example.invalid',role:'office',active:true}],now:'2026-11-25T15:00:00Z',admin:role==='admin',manager:role==='admin',user_id:role==='admin'?admin:staff,lieu_balances:[],mobile:false});
  if(url==='/api/hr/action'){const p=JSON.parse(opts.body);writes.push(p);if(uncertain){uncertain=false;throw Error('lost response');}if(reject)return {ok:false,status:409,json:async()=>({error:'PERSONAL_NOTICE_REQUIRED'})};return ok({data:{id:'saved',data:{},version:1}});}
  throw Error('Unexpected URL '+url);
 };
 w.eval(fs.readFileSync('production_history/static/hr.js','utf8'));await until(()=>!$('workspace').hidden);
 return {w,$,writes,submit:()=> $('leave-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true})),type:t=>{$('leave-form').elements.leave_type.value=t;$('leave-form').elements.leave_type.dispatchEvent(new w.Event('change',{bubbles:true}));},reject:()=>reject=true,uncertain:()=>uncertain=true,close:()=>w.close()};
}
{
 const a=await fixture();a.$('tab-leave').click();assert.equal(a.$('panel-leave').hidden,false);
 const text=a.$('leave-notice-policy').textContent;assert.match(text,/24 hours before it starts/);assert.match(text,/14 calendar days/);assert.match(text,/Submitting a request does not mean it has been approved/);assert.match(text,/do not override leave entitlements under the law/);assert.doesNotMatch(text,/overtime/i);
 const cards=[...a.$('leave-list').querySelectorAll('article')];for(const card of cards.slice(0,2)){assert.equal([...card.querySelectorAll('button')].find(b=>b.textContent==='Approve').disabled,true);assert.equal([...card.querySelectorAll('button')].find(b=>b.textContent==='Decline').disabled,false);assert.match(card.textContent,/cannot be approved/);}
 for(const card of cards.slice(2))assert.equal([...card.querySelectorAll('button')].find(b=>b.textContent==='Approve').disabled,false);
 a.type('Personal');assert.equal(a.$('personal-start-label').hidden,false);const f=a.$('leave-form');assert.equal(f.elements.start_time.required,true);f.elements.start_date.value='2026-12-01';f.elements.end_date.value='2026-12-01';f.elements.start_time.value='14:30';a.submit();await until(()=>a.writes.length===1&&!a.$('range').querySelector('button').disabled);assert.equal(a.writes[0].start_time,'14:30');
 assert.equal([...a.$('leave-list').querySelectorAll('article')][0].querySelector('[data-blocked]').disabled,true);
 a.type('Vacation');assert.equal(f.elements.start_time.disabled,true);a.submit();await until(()=>a.writes.length===2&&!a.$('range').querySelector('button').disabled);assert.equal('start_time' in a.writes[1],false);
 a.type('Emergency');assert.match(a.$('leave-type-help').textContent,/do not block sick or emergency/);a.close();
}
{
 const a=await fixture('office');assert.equal(a.$('leave-list').textContent.includes('Approve'),false);a.type('Personal');const f=a.$('leave-form');f.elements.start_date.value=f.elements.end_date.value='2026-12-03';f.elements.start_time.value='10:00';a.uncertain();a.submit();await until(()=>!a.$('retry').hidden);a.$('retry-action').click();await until(()=>a.writes.length===2&&a.$('retry').hidden&&!a.$('range').querySelector('button').disabled);assert.deepEqual(a.writes[0],a.writes[1]);
 a.reject();a.submit();await until(()=>a.writes.length===3&&!a.$('range').querySelector('button').disabled);assert.match(a.$('status').textContent,/less than 24 hours/);a.close();
}
console.log('Leave notice UI PASS: policy wording, personal start-time input, late approval disabled across refreshes, sick/emergency review, request payloads, readable errors and retry identity.');
