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
await who(staff);await now('2026-11-25T10:00:00-05:00');
// Prior pending requests and approvals exist before the update.
const oldLate=valid(await request('Personal','2026-11-26'));
const oldApproved=valid(await request('Vacation','2026-11-28'));
await who(admin);const oldApprovedFinal=valid(await decide(oldApproved));
await db.exec('RESET ROLE');
const oldCourse=(await db.query('SELECT * FROM custom_u_production.training_courses_127')).rows[0];
await db.query('UPDATE custom_u_production.training_courses_127 SET assigned_all=true,due_date=$1 WHERE id=$2',['2026-12-20',oldCourse.id]);
await db.query('INSERT INTO custom_u_production.training_progress_127(course_id,employee_id,read_lessons) VALUES($1,$2,$3)',[oldCourse.id,staff,[0,1]]);
await db.query('INSERT INTO custom_u_production.training_assignments_127(course_id,employee_id,due_date,assigned_by) VALUES($1,$2,$3,$4)',[oldCourse.id,staff,'2026-12-20',admin]);
await db.exec(migration('_leave_notice_128.sql'));await db.exec(migration('_leave_notice_128.sql'));
let courses=(await db.query('SELECT * FROM custom_u_production.training_courses_127')).rows;
assert.equal(courses.length,2);const current=courses.find(x=>x.data.edition==='2'),archived=courses.find(x=>x.data.edition==='1');
assert.equal(archived.status,'archived');assert.deepEqual(archived.data,oldCourse.data);assert.equal(current.status,'published');assert.equal(current.assigned_all,true);
assert.equal((await db.query('SELECT count(*)::int n FROM custom_u_production.training_progress_127 WHERE course_id=$1',[current.id])).rows[0].n,0);
assert.equal((await db.query('SELECT count(*)::int n FROM custom_u_production.training_assignments_127 WHERE course_id=$1',[current.id])).rows[0].n,1);
assert.equal((await db.query('SELECT count(*)::int n FROM custom_u_production.training_progress_127 WHERE course_id=$1',[archived.id])).rows[0].n,1);
await who(null);assert.equal((await call({op:'view',from:'2026-11-01',to:'2026-12-31'})).error,'ACCESS_DENIED');
await who(staff,'no');assert.equal((await request('Personal','2026-12-15')).error,'ACCESS_DENIED');
await who(manager);assert.equal((await decide(oldLate)).error,'PERSONAL_NOTICE_REQUIRED');
await who(admin);assert.equal((await decide(oldLate)).error,'PERSONAL_NOTICE_REQUIRED');valid(await decide(oldLate,'declined'));
await db.exec('RESET ROLE');assert.deepEqual((await db.query('SELECT * FROM custom_u_production.hr_records_115 WHERE id=$1',[oldApproved.id])).rows[0].data,oldApprovedFinal.data);
// Exactly 24 hours passes, one second short fails, and later review does not change eligibility.
await who(staff);await now('2026-12-01T09:00:00-05:00');const exact=valid(await request('Personal','2026-12-02',{start_time:'09:00'}));
await now('2026-12-02T09:00:01-05:00');const short=valid(await request('Personal','2026-12-03',{start_time:'09:00'}));
await who(staff);assert.equal((await decide(exact)).error,'ACCESS_DENIED');await who(manager);valid(await decide(exact));assert.equal((await decide(short)).error,'PERSONAL_NOTICE_REQUIRED');valid(await decide(short,'declined'));
// Fourteen local calendar days passes even when less than 336 elapsed hours remain.
await who(staff);await now('2026-12-02T23:59:59-05:00');const vacation=valid(await request('Vacation','2026-12-16')),vacationShort=valid(await request('Vacation','2026-12-15'));
await now('2026-12-16T09:00:00-05:00');await who(admin);valid(await decide(vacation));assert.equal((await decide(vacationShort)).error,'VACATION_NOTICE_REQUIRED');valid(await decide(vacationShort,'declined'));
// Sick and emergency notices may be same-day or retrospective and still require manager approval.
await who(staff);const sick=valid(await request('Sick','2026-12-17')),emergency=valid(await request('Emergency','2026-12-14'));
assert.equal(sick.data.status,'pending');assert.equal(emergency.data.status,'pending');await who(manager);valid(await decide(sick));valid(await decide(emergency));
await who(staff);assert.equal((await request('Personal','2026-12-20',{start_time:'25:00'})).error,'INVALID_HR_DATA');
assert.equal((await request('Vacation','2026-12-20',{start_time:'10:00'})).error,'INVALID_HR_DATA');
assert.equal((await request('Personal','2026-12-20',{submitted_at:'2026-01-01T00:00:00Z'})).error,'INVALID_HR_DATA');
assert.equal((await request('Personal','2026-12-20',{notice:{eligible:true}})).error,'INVALID_HR_DATA');
const payload={op:'leave_request',request_id:randomUUID(),leave_type:'Personal',start_date:'2026-12-22',end_date:'2026-12-22',start_time:'14:30',reason:'Retry test'};
const original=valid(await call(payload));await now('2026-12-21T20:00:00-05:00');assert.deepEqual(valid(await call(payload)),original);
assert.equal((await call({...payload,start_time:'15:00'})).error,'REQUEST_CONFLICT');
await who(manager);valid(await decide(original));
// Local-calendar and elapsed-hour checks across both DST transitions.
await db.exec('RESET ROLE');
const notice=async(type,date,time,submitted)=>(await db.query('SELECT custom_u_production.leave_notice_128($1::jsonb,$2::timestamptz) n',[JSON.stringify({leave_type:type,start_date:date,start_time:time}),submitted])).rows[0].n;
assert.equal((await notice('Personal','2027-03-14','09:00','2027-03-13T09:00:00-05:00')).eligible,false);
assert.equal((await notice('Personal','2027-11-07','09:00','2027-11-06T09:00:00-04:00')).eligible,true);
assert.equal((await notice('Vacation','2027-03-14',null,'2027-02-28T23:59:59-05:00')).eligible,true);
await who(manager);let view=await call({op:'view',from:'2026-11-01',to:'2026-12-31'});assert.equal(view.records.find(x=>x.id===short.id).notice.eligible,false);assert.equal(view.records.find(x=>x.id===exact.id).notice.eligible,true);
await assert.rejects(()=>db.query('SELECT custom_u_production.leave_notice_128($1::jsonb,now())',['{}']),/permission denied/);
// The attendance and lieu workflow remains intact.
await who(staff);await now('2026-12-26T10:00:00-05:00');valid(await act({op:'clock_in'}));await now('2026-12-26T10:37:45-05:00');let shift=valid(await act({op:'clock_out'}));await who(admin);shift=valid(await act({op:'lieu_decide',id:shift.id,version:shift.version,decision:'approved',note:'Weekend work'}));assert.equal(shift.data.lieu.minutes,37);
await who(staff);const lieu=valid(await request('Time in lieu','2026-12-28',{lieu_minutes:20}));await who(admin);valid(await decide(lieu));
view=await call({op:'view',from:'2026-11-01',to:'2026-12-31'});assert.equal(view.lieu_balances.find(b=>b.employee_id===staff).available_minutes,17);
await db.exec('RESET ROLE');const backup={hr_records:(await db.query('SELECT * FROM custom_u_production.hr_records_115')).rows};fs.writeFileSync('/tmp/leave128_records.json',JSON.stringify(backup));
await db.close();console.log('Leave notice SQL PASS: exact 24 hours, calendar days, DST, original submission time, late approvals blocked for admin/manager, sick/emergency review, retry/tamper protection, legacy approvals, course edition history and weekend lieu.');
