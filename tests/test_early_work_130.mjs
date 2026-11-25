import {PGlite} from '@electric-sql/pglite';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
const db=new PGlite(),admin=randomUUID(),staff=randomUUID(),manager=randomUUID();
await db.exec(`CREATE ROLE anon;CREATE ROLE authenticated;CREATE SCHEMA auth;CREATE SCHEMA custom_u_production;
CREATE TABLE auth.users(id uuid PRIMARY KEY,email text);
CREATE TABLE custom_u_production.staff_members(user_id uuid PRIMARY KEY,role text,active boolean);
CREATE TABLE custom_u_production.staff_access_102(user_id uuid PRIMARY KEY,active boolean);
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql AS $$ SELECT nullif(current_setting('test.uid',true),'')::uuid $$;
CREATE FUNCTION custom_u_production.session_access_102() RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path='' AS $$ SELECT jsonb_build_object('user_id',user_id,'role',role) FROM custom_u_production.staff_members WHERE user_id=auth.uid() AND active AND current_setting('test.allowed',true)='yes' $$;
CREATE FUNCTION custom_u_production.catalogue_text_108(v jsonb,maxlen int,required boolean) RETURNS boolean LANGUAGE sql IMMUTABLE SET search_path='' AS $$ SELECT jsonb_typeof(v)='string' AND length(v#>>'{}')<=maxlen AND (NOT required OR length(btrim(v#>>'{}'))>0); $$;
GRANT USAGE ON SCHEMA custom_u_production TO authenticated;
`);
await db.exec(fs.readFileSync('tests/support/hr_before_128.sql','utf8'));
const migration=suffix=>fs.readFileSync('supabase/migrations/'+fs.readdirSync('supabase/migrations').find(x=>x.endsWith(suffix)),'utf8');
await db.exec(migration('_hr_training_127.sql'));
for(const [id,role] of [[admin,'admin'],[staff,'office'],[manager,'production']]){
 await db.query('INSERT INTO auth.users VALUES($1,$2)',[id,role+'@example.invalid']);
 await db.query('INSERT INTO custom_u_production.staff_members VALUES($1,$2,true)',[id,role]);
 await db.query('INSERT INTO custom_u_production.staff_access_102 VALUES($1,true)',[id]);
}
const who=async(id,allowed='yes')=>{await db.exec('RESET ROLE');await db.query("SELECT set_config('test.uid',$1,false),set_config('test.allowed',$2,false)",[id||'',allowed]);await db.exec('SET ROLE authenticated');};
const now=async t=>{await db.exec('RESET ROLE');await db.exec(`CREATE OR REPLACE FUNCTION custom_u_production.hr_now_115() RETURNS timestamptz LANGUAGE sql VOLATILE SET search_path='' AS $$ SELECT '${t}'::timestamptz $$;SET ROLE authenticated;`);};
const call=async p=>(await db.query('SELECT public.custom_u_hr_115($1::jsonb) r',[JSON.stringify(p)])).rows[0].r;
const act=p=>call({request_id:randomUUID(),...p});
const valid=r=>{assert.ok(r.data,JSON.stringify(r));return r.data;};
const request=(type,date,extra={})=>act({op:'leave_request',leave_type:type,start_date:date,end_date:date,reason:'Isolated test',...extra});
const decide=(r,decision='approved')=>act({op:'leave_decide',id:r.id,version:r.version,decision,note:'Test review'});
await who(admin);valid(await act({op:'manager_save',employee_id:manager,version:0,active:true}));
await db.exec('RESET ROLE');await db.exec(migration('_leave_notice_128.sql'));await db.exec(migration('_clock_recovery_129.sql'));await db.exec(migration('_clock_recovery_129.sql'));
const train=async p=>(await db.query('SELECT public.custom_u_training_127($1::jsonb) r',[JSON.stringify(p)])).rows[0].r;
await who(admin);const prior=(await train({op:'list'})).courses.find(c=>c.status==='published');const priorCourse=(await train({op:'get',id:prior.id})).course;
await who(staff);for(let lesson=0;lesson<10;lesson++)assert.ok((await train({op:'read',id:prior.id,lesson,request_id:randomUUID()})).progress);
const completed=await train({op:'submit',id:prior.id,answers:priorCourse.data.questions.map(q=>q.correct_index),acknowledge:true,request_id:randomUUID()});assert.equal(completed.attempt.passed,true);
await db.exec('RESET ROLE');const oldData=(await db.query('SELECT data FROM custom_u_production.training_courses_127 WHERE id=$1',[prior.id])).rows[0].data;
const oldAttempts=(await db.query('SELECT to_jsonb(x) r FROM custom_u_production.training_attempts_127 x')).rows;
const oldProgress=(await db.query('SELECT to_jsonb(x) r FROM custom_u_production.training_progress_127 x')).rows;
await db.exec(migration('_early_work_review_130.sql'));await db.exec(migration('_early_work_review_130.sql'));
assert.deepEqual((await db.query('SELECT to_jsonb(x) r FROM custom_u_production.training_attempts_127 x')).rows,oldAttempts);assert.deepEqual((await db.query('SELECT to_jsonb(x) r FROM custom_u_production.training_progress_127 x')).rows,oldProgress);
let courses=(await db.query('SELECT * FROM custom_u_production.training_courses_127')).rows;assert.equal(courses.length,3);assert.equal(courses.find(c=>c.id===prior.id).status,'archived');assert.deepEqual(courses.find(c=>c.id===prior.id).data,oldData);const edition=courses.find(c=>c.status==='published');assert.equal(edition.data.edition,'3');assert.equal(edition.data.questions[15].correct_index,1);
await who(null);assert.equal((await call({op:'clock_view'})).error,'ACCESS_DENIED');await who(staff,'no');assert.equal((await act({op:'early_work_report'})).error,'ACCESS_DENIED');
const totals=async r=>{await db.exec('RESET ROLE');return (await db.query('SELECT custom_u_production.attendance_totals_130($1::jsonb,custom_u_production.hr_now_115()) t',[JSON.stringify(r.data)])).rows[0].t;};
const clock=async(day,start='08:30',end='17:00')=>{await who(staff);await now(day+'T'+start+':00-05:00');const original=valid(await act({op:'clock_in'}));await now(day+'T'+end+':00-05:00');const row=valid(await act({op:'clock_out'}));return {row,original};};
const report=async(r,kind='work',spans)=>{await who(staff);return valid(await act({op:'early_work_report',id:r.id,version:r.version,kind,intervals:spans??(kind==='arrival'?[]:[{in:r.data.day+'T08:30:00-05:00',out:r.data.day+'T09:00:00-05:00'}]),note:kind==='arrival'?'Arrived early but no work before 9':'Prepared customer artwork before 9'}));};
const review=async r=>{await who(manager);return valid(await act({op:'early_work_review',id:r.id,version:r.version,decision:'confirmed',note:'Verified actual activity separately from scheduling approval'}));};
const cases=[];
// 1. Arrival alone is not work, and does not earn a time-off credit.
let {row,original}=await clock('2026-11-30');assert.equal((await totals(row)).early_review_status,'unreported');row=await report(row,'arrival');assert.equal((await totals(row)).needs_review,true);row=await review(row);let t=await totals(row);assert.equal(t.worked_minutes,480);assert.equal(t.included_early_minutes,0);assert.equal(t.needs_review,false);assert.deepEqual(row.data.intervals,original.data.intervals.map((p,i)=>({...p,out:row.data.intervals[i].out})));cases.push({name:'arrival',row,totals:t});
// 2. Actual early work is reportable without scheduling approval; unresolved time stays visible.
({row,original}=await clock('2026-12-01'));const originalPunches=structuredClone(row.data.intervals);assert.equal((await totals(row)).unresolved_early_minutes,30);row=await report(row);t=await totals(row);assert.equal(t.reported_early_minutes,30);assert.equal(t.worked_minutes,480);assert.equal(t.needs_review,true);cases.push({name:'pending',row,totals:t});
await who(staff);assert.equal((await act({op:'early_work_review',id:row.id,version:row.version,decision:'confirmed',note:'self'})).error,'ACCESS_DENIED');
await who(manager);const clarification=valid(await act({op:'early_work_review',id:row.id,version:row.version,decision:'clarification',note:'Please identify the job'}));assert.equal((await totals(clarification)).needs_review,true);row=await report(clarification);row=await review(row);t=await totals(row);assert.equal(t.worked_minutes,510);assert.equal(t.included_early_minutes,30);assert.equal(t.needs_review,false);assert.deepEqual(row.data.intervals,originalPunches);assert.equal(row.data.lieu,undefined);cases.push({name:'confirmed_work',row,totals:t});
// Report amendments reopen review and invalidate only the separate credit decision.
await who(manager);row=valid(await act({op:'lieu_decide',id:row.id,version:row.version,decision:'approved',note:'Separate discretionary credit; payroll reviewed independently'}));assert.equal(row.data.lieu.minutes,30);
row=await report(row,'work',[{in:'2026-12-01T08:45:00-05:00',out:'2026-12-01T09:00:00-05:00'}]);assert.equal(row.data.lieu.status,'review_required');assert.equal((await totals(row)).needs_review,true);await who(manager);assert.equal((await act({op:'lieu_decide',id:row.id,version:row.version,decision:'approved',note:'blocked'})).error,'SHIFT_REVIEW_REQUIRED');
row=await review(row);assert.equal((await totals(row)).worked_minutes,495);
// 3. A separate correction includes actual work before 9; original punches are immutable.
({row,original}=await clock('2026-12-02','09:15'));const punches=structuredClone(row.data.intervals);await who(manager);const correction={op:'shift_correct',id:row.id,version:row.version,start:'2026-12-02T08:30:00-05:00',end:'2026-12-02T17:00:00-05:00',reason:'Actual start verified',request_id:randomUUID()};row=valid(await call(correction));assert.deepEqual(valid(await call(correction)),row);assert.deepEqual(row.data.intervals,punches);t=await totals(row);assert.equal(t.worked_minutes,510);assert.equal(t.early_review_status,'corrected');cases.push({name:'corrected',row,totals:t});
// 4. A test punch is closed at zero without deleting history or creating credits.
await who(staff);await now('2026-12-03T08:30:00-05:00');original=valid(await act({op:'clock_in'}));await who(admin);row=valid(await act({op:'shift_correct',id:original.id,version:1,start:'2026-12-03T08:30:00-05:00',end:'2026-12-03T08:30:00-05:00',reason:'Confirmed test only'}));t=await totals(row);assert.equal(t.worked_minutes,0);assert.equal(t.overtime_minutes,0);assert.equal(t.needs_review,false);assert.deepEqual(row.data.intervals,original.data.intervals);cases.push({name:'test_zero',row,totals:t});
// Missing early punches can be reported, while overlaps, late ranges and another employee are rejected.
({row}=await clock('2026-12-04','09:00'));await who(manager);assert.equal((await act({op:'early_work_report',id:row.id,version:row.version,kind:'arrival',intervals:[],note:'not owner'})).error,'ACCESS_DENIED');await who(staff);
const p={op:'early_work_report',id:row.id,version:row.version,kind:'work',note:'Missing early punch',intervals:[{in:'2026-12-04T08:30:00-05:00',out:'2026-12-04T09:00:00-05:00'}],request_id:randomUUID()};const saved=valid(await call(p));assert.deepEqual(valid(await call(p)),saved);assert.equal((await call({...p,note:'changed'})).error,'REQUEST_CONFLICT');assert.equal((await act({...p,request_id:randomUUID()})).error,'VERSION_CONFLICT');
await who(manager);row=await review(saved);assert.equal((await totals(row)).worked_minutes,510);
await who(staff);assert.equal((await act({...p,version:row.version,request_id:randomUUID(),intervals:[p.intervals[0],p.intervals[0]]})).error,'INVALID_HR_DATA');
// Scheduling approvals still operate prospectively and do not imply payroll approval.
await who(staff);await now('2026-12-07T07:00:00-05:00');let early=valid(await act({op:'early_request',day:'2026-12-07',start:'08:30',reason:'Scheduled artwork'}));await who(manager);valid(await act({op:'early_decide',id:early.id,version:1,decision:'approved',note:'Schedule approved'}));({row}=await clock('2026-12-07','08:30','16:30'));assert.equal((await totals(row)).worked_minutes,480);row=await report(row,'arrival');row=await review(row);assert.equal((await totals(row)).worked_minutes,450); // Arrival alone is excluded even with scheduling approval.
// Leave notice enforcement is untouched.
await who(staff);await now('2026-12-08T09:00:01-05:00');const late=valid(await request('Personal','2026-12-09',{start_time:'09:00'}));const vac=valid(await request('Vacation','2026-12-21'));await who(admin);assert.equal((await decide(late)).error,'PERSONAL_NOTICE_REQUIRED');assert.equal((await decide(vac)).error,'VACATION_NOTICE_REQUIRED');
await who(staff);await now('2026-12-08T09:00:00-05:00');const exact=valid(await request('Personal','2026-12-10',{start_time:'09:00'}));const vacation=valid(await request('Vacation','2026-12-22'));await who(admin);valid(await decide(exact));valid(await decide(vacation));
await who(admin);const view=await call({op:'view',from:'2026-12-01',to:'2026-12-31'});const training=await train({op:'backup'});
await db.exec('RESET ROLE');const backup={hr_people:(await db.query('SELECT a.id,a.email,s.role FROM auth.users a JOIN custom_u_production.staff_members s ON s.user_id=a.id')).rows,training_127:training};
for(const name of ['records','audit','requests'])backup['hr_'+name]=(await db.query('SELECT to_jsonb(r) row FROM custom_u_production.hr_'+name+'_115 r')).rows.map(x=>x.row);
fs.writeFileSync('/tmp/early130_cases.json',JSON.stringify({cases,backup,view}));
await db.close();console.log('Early work SQL PASS: four required cases, unresolved reports, reviewed work, immutable punches, retries, access controls, scheduling approvals, leave deadlines and preserved training results.');
