-- Permit an authorised, audited zero-time correction for a test or accidental clock-in.
-- Normal clock-out retains the 24-hour missed-clock-out guard.
SELECT pg_advisory_xact_lock(115,115);
CREATE OR REPLACE FUNCTION custom_u_production.hr_rpc_115(payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE who jsonb; u uuid:=auth.uid(); op text:=payload->>'op'; admin boolean; manager boolean; t timestamptz:=custom_u_production.hr_now_115(); today date;
 ident uuid; target uuid; rid uuid; previous custom_u_production.hr_records_115%ROWTYPE; rec custom_u_production.hr_records_115%ROWTYPE;
 d jsonb; result jsonb; receipt custom_u_production.hr_requests_115%ROWTYPE; a jsonb; items jsonb; people jsonb; k text;
 allowed text[]; day date; finish date; starttime time; sched timestamptz; started timestamptz; ended timestamptz; intervals jsonb; lastidx integer; why text; minutes integer; max_minutes integer; balance jsonb; banks jsonb;
BEGIN
 PERFORM 1 FROM custom_u_production.staff_members WHERE user_id=u FOR SHARE;
 PERFORM 1 FROM custom_u_production.staff_access_102 WHERE user_id=u FOR SHARE;
 who:=custom_u_production.session_access_102();IF u IS NULL OR who IS NULL THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 IF jsonb_typeof(payload) IS DISTINCT FROM 'object' OR octet_length(payload::text)>64000 THEN RETURN jsonb_build_object('error','INVALID_HR_DATA');END IF;
 admin:=who->>'role'='admin';manager:=admin OR EXISTS(SELECT 1 FROM custom_u_production.hr_records_115 WHERE kind='manager' AND employee_id=u AND data->'active'='true'::jsonb);
 today:=(t AT TIME ZONE 'America/Nassau')::date;
 IF op='device_check' THEN
  RETURN jsonb_build_object('approved',admin OR EXISTS(SELECT 1 FROM custom_u_production.hr_records_115 WHERE kind='device' AND data->>'digest'=payload->>'digest' AND data->'active'='true'::jsonb));
 END IF;
 IF op='clock_view' THEN
  IF payload-ARRAY['op']<>'{}'::jsonb THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  SELECT * INTO rec FROM custom_u_production.hr_records_115 WHERE kind='shift' AND employee_id=u
   AND (data->>'state'='in' OR data->>'day'=today::text) ORDER BY (data->>'state'='in') DESC LIMIT 1;
  RETURN jsonb_build_object('user_id',u,'now',t,'shift',CASE WHEN rec.id IS NULL THEN NULL ELSE
   jsonb_build_object('state',rec.data->>'state','day',rec.data->>'day','last_in',rec.data->'intervals'->-1->>'in',
    'corrected',rec.data->'correction'<>'null'::jsonb) END);
 END IF;
 IF op='view' THEN
  day:=custom_u_production.hr_date_115(payload->'from');finish:=custom_u_production.hr_date_115(payload->'to');IF finish<day OR finish-day>93 THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  SELECT coalesce(jsonb_agg(to_jsonb(r)||CASE WHEN r.kind='leave' THEN jsonb_build_object('notice',custom_u_production.leave_notice_128(r.data,r.created_at)) ELSE '{}'::jsonb END ORDER BY r.updated_at DESC),'[]') INTO items FROM custom_u_production.hr_records_115 r WHERE
   (r.kind IN ('manager','device') AND admin) OR
   (r.kind='policy' AND (manager OR r.data->>'status'='published')) OR
   (r.kind='ack' AND (manager OR r.employee_id=u)) OR
   (r.kind IN ('shift','early','leave','kpi') AND (manager OR r.employee_id=u) AND (
    (r.kind='shift' AND ((r.data->>'day')::date BETWEEN day AND finish OR r.data->>'state'='in')) OR
    (r.kind='early' AND ((r.data->>'day')::date BETWEEN day AND finish OR r.data->>'status'='pending')) OR
    (r.kind='leave' AND ((r.data->>'start_date')::date<=finish AND (r.data->>'end_date')::date>=day OR r.data->>'status'='pending')) OR
    (r.kind='kpi' AND (r.data->>'period')::date BETWEEN date_trunc('month',day)::date AND finish)));
  IF jsonb_array_length(items)>2000 THEN RETURN jsonb_build_object('error','HR_VIEW_LIMIT');END IF;
  SELECT coalesce(jsonb_agg(jsonb_build_object('id',m.user_id,'email',au.email,'role',m.role,'active',m.active AND (m.role='admin' OR sa.active)) ORDER BY au.email),'[]') INTO people
   FROM custom_u_production.staff_members m JOIN auth.users au ON au.id=m.user_id LEFT JOIN custom_u_production.staff_access_102 sa ON sa.user_id=m.user_id WHERE manager OR m.user_id=u;
  SELECT coalesce(jsonb_agg(custom_u_production.lieu_balance_1152(m.user_id)),'[]') INTO banks FROM custom_u_production.staff_members m WHERE manager OR m.user_id=u;
  RETURN jsonb_build_object('records',items,'people',people,'manager',manager,'admin',admin,'user_id',u,'now',t,'lieu_balances',banks);
 END IF;
 IF op='audit' THEN
  ident:=(payload->>'id')::uuid;SELECT * INTO rec FROM custom_u_production.hr_records_115 WHERE id=ident;
  IF rec.id IS NULL OR NOT (admin OR manager AND rec.kind NOT IN ('manager','device') OR rec.employee_id=u AND rec.kind IN ('shift','early','leave','kpi','ack')) THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
  RETURN jsonb_build_object('data',(SELECT coalesce(jsonb_agg(to_jsonb(a) ORDER BY a.id),'[]') FROM custom_u_production.hr_audit_115 a WHERE record_id=ident));
 END IF;
 IF op IS NULL OR op NOT IN ('clock_in','clock_out','early_request','early_decide','leave_request','leave_decide','leave_cancel','shift_correct','lieu_decide','kpi_save','kpi_progress','policy_save','policy_publish','policy_ack','manager_save','device_save') THEN RETURN jsonb_build_object('error','INVALID_OPERATION');END IF;
 IF op IN ('early_decide','leave_decide','shift_correct','lieu_decide','kpi_save','policy_save','policy_publish') AND NOT manager OR op IN ('manager_save','device_save') AND NOT admin THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 IF coalesce(payload->>'request_id','')!~'^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$' THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
 allowed:=CASE op
 WHEN 'clock_in' THEN ARRAY['op','request_id'] WHEN 'clock_out' THEN ARRAY['op','request_id']
 WHEN 'early_request' THEN ARRAY['op','request_id','day','start','reason']
 WHEN 'early_decide' THEN ARRAY['op','request_id','id','version','decision','note']
 WHEN 'leave_decide' THEN ARRAY['op','request_id','id','version','decision','note']
 WHEN 'leave_request' THEN ARRAY['op','request_id','start_date','end_date','leave_type','reason','lieu_minutes','start_time']
 WHEN 'lieu_decide' THEN ARRAY['op','request_id','id','version','decision','note']
 WHEN 'leave_cancel' THEN ARRAY['op','request_id','id','version','note']
 WHEN 'shift_correct' THEN ARRAY['op','request_id','id','version','start','end','reason']
 WHEN 'kpi_save' THEN ARRAY['op','request_id','id','version','employee_id','period','title','target','unit','direction','manager_note']
 WHEN 'kpi_progress' THEN ARRAY['op','request_id','id','version','actual','notes']
 WHEN 'policy_save' THEN ARRAY['op','request_id','id','version','title','body','edition']
 WHEN 'policy_publish' THEN ARRAY['op','request_id','id','version']
 WHEN 'policy_ack' THEN ARRAY['op','request_id','policy_id']
 WHEN 'manager_save' THEN ARRAY['op','request_id','employee_id','version','active']
 WHEN 'device_save' THEN ARRAY['op','request_id','digest','name','version','active'] END;
 IF (payload ? 'version' AND (jsonb_typeof(payload->'version') IS DISTINCT FROM 'number' OR coalesce(payload->>'version','')!~'^[0-9]{1,9}$')) OR payload-allowed<>'{}'::jsonb THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
 rid:=(payload->>'request_id')::uuid;
 -- Small team: serialize transitions, approvals and corrections in one transaction.
 PERFORM pg_advisory_xact_lock(115,115);
 manager:=admin OR EXISTS(SELECT 1 FROM custom_u_production.hr_records_115 WHERE kind='manager' AND employee_id=u AND data->'active'='true'::jsonb);
 IF op IN ('early_decide','leave_decide','shift_correct','lieu_decide','kpi_save','policy_save','policy_publish') AND NOT manager THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 SELECT * INTO receipt FROM custom_u_production.hr_requests_115 WHERE actor_id=u AND request_id=rid;
 IF FOUND THEN IF receipt.payload=payload THEN RETURN receipt.result;ELSE RETURN jsonb_build_object('error','REQUEST_CONFLICT');END IF;END IF;
 IF (SELECT count(*) FROM custom_u_production.hr_audit_115)>=100000 THEN RETURN jsonb_build_object('error','HR_HISTORY_LIMIT');END IF;
 IF payload ? 'id' THEN
  ident:=(payload->>'id')::uuid;SELECT * INTO previous FROM custom_u_production.hr_records_115 WHERE id=ident FOR UPDATE;
  IF previous.id IS NULL THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;
  IF previous.id IS NOT NULL AND (jsonb_typeof(payload->'version') IS DISTINCT FROM 'number' OR (payload->>'version')::integer<>previous.version) THEN RETURN jsonb_build_object('error','VERSION_CONFLICT');END IF;
 ELSE ident:=gen_random_uuid();END IF;
 target:=u;
 IF op IN ('clock_in','clock_out') THEN
  SELECT * INTO previous FROM custom_u_production.hr_records_115 WHERE kind='shift' AND employee_id=u AND (data->>'state'='in' OR data->>'day'=today::text) ORDER BY (data->>'state'='in') DESC LIMIT 1;
  IF op='clock_in' THEN
   IF previous.id IS NOT NULL AND previous.data->>'state'='in' THEN RETURN jsonb_build_object('error','ALREADY_CLOCKED_IN');END IF;
   sched:=(today+CASE WHEN extract(isodow FROM today)>5 THEN time '00:00' ELSE time '09:00' END) AT TIME ZONE 'America/Nassau';
   SELECT (today+(data->>'start')::time) AT TIME ZONE 'America/Nassau' INTO started FROM custom_u_production.hr_records_115 WHERE kind='early' AND employee_id=u AND data->>'day'=today::text AND data->>'status'='approved';
   sched:=coalesce(started,sched);
   IF previous.id IS NULL THEN
    d:=jsonb_build_object('day',today,'scheduled_start',sched,'regular_minutes',480,'time_policy','weekends_1153','intervals','[]'::jsonb,'state','out','correction',NULL);
   ELSE
    ident:=previous.id;d:=previous.data;
    IF d->'correction'<>'null'::jsonb THEN RETURN jsonb_build_object('error','SHIFT_CORRECTED');END IF;
   END IF;
   IF jsonb_array_length(d->'intervals')>=100 THEN RETURN jsonb_build_object('error','SHIFT_INTERVAL_LIMIT');END IF;
   intervals:=(d->'intervals')||jsonb_build_array(jsonb_build_object('in',t,'out',NULL));
   d:=d||jsonb_build_object('state','in','intervals',intervals);
  ELSE
   IF previous.id IS NULL OR previous.data->>'state'<>'in' THEN RETURN jsonb_build_object('error','NOT_CLOCKED_IN');END IF;
   ident:=previous.id;d:=previous.data;intervals:=d->'intervals';lastidx:=jsonb_array_length(intervals)-1;
   IF t-(intervals->lastidx->>'in')::timestamptz>interval '24 hours' THEN RETURN jsonb_build_object('error','MISSED_CLOCK_OUT');END IF;
   intervals:=jsonb_set(intervals,ARRAY[lastidx::text,'out'],to_jsonb(t));d:=d||jsonb_build_object('state','out','intervals',intervals);
  END IF;k:='shift';
 ELSIF op='early_request' THEN
  IF previous.id IS NOT NULL THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  day:=custom_u_production.hr_date_115(payload->'day');starttime:=custom_u_production.hr_text_115(payload->'start',5,true)::time;
  IF day<today OR day>today+366 OR extract(isodow FROM day)>5 OR starttime<time '04:00' OR starttime>=time '09:00' OR (day+starttime) AT TIME ZONE 'America/Nassau'<=t THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  IF EXISTS(SELECT 1 FROM custom_u_production.hr_records_115 WHERE kind='early' AND employee_id=u AND data->>'day'=day::text AND data->>'status' IN ('pending','approved')) THEN RETURN jsonb_build_object('error','REQUEST_ALREADY_EXISTS');END IF;
  k:='early';d:=jsonb_build_object('day',day,'start',to_char(starttime,'HH24:MI'),'reason',custom_u_production.hr_text_115(payload->'reason',1000,true),'status','pending');
 ELSIF op IN ('early_decide','leave_decide') THEN
  k:=CASE WHEN op='early_decide' THEN 'early' ELSE 'leave' END;
  IF previous.id IS NULL OR previous.kind<>k OR previous.data->>'status'<>'pending' THEN RETURN jsonb_build_object('error','REQUEST_NOT_PENDING');END IF;
  IF previous.employee_id=u AND NOT admin THEN RETURN jsonb_build_object('error','SELF_APPROVAL_NOT_ALLOWED');END IF;
  IF coalesce(payload->>'decision','') NOT IN ('approved','declined') THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  IF k='early' AND payload->>'decision'='approved' AND ((previous.data->>'day')::date+(previous.data->>'start')::time) AT TIME ZONE 'America/Nassau'<=t THEN RETURN jsonb_build_object('error','EARLY_APPROVAL_TOO_LATE');END IF;
  IF k='leave' AND payload->>'decision'='approved' THEN
   a:=custom_u_production.leave_notice_128(previous.data,previous.created_at);
   IF a->'eligible'='false'::jsonb THEN RETURN jsonb_build_object('error',a->>'error');END IF;
  END IF;
  IF k='leave' AND payload->>'decision'='approved' AND EXISTS(SELECT 1 FROM custom_u_production.hr_records_115 WHERE kind='leave' AND employee_id=previous.employee_id AND data->>'status'='approved' AND (data->>'start_date')::date<=(previous.data->>'end_date')::date AND (data->>'end_date')::date>=(previous.data->>'start_date')::date) THEN RETURN jsonb_build_object('error','LEAVE_OVERLAP');END IF;
  IF k='leave' AND previous.data->>'leave_type'='Time in lieu' AND payload->>'decision'='approved' THEN
   balance:=custom_u_production.lieu_balance_1152(previous.employee_id);
   IF (balance->>'available_minutes')::bigint<(previous.data->>'lieu_minutes')::int THEN RETURN jsonb_build_object('error','INSUFFICIENT_LIEU_BALANCE');END IF;
  END IF;
  -- Approval before the requested start also updates a clock-in made while approval was pending.
  IF k='early' AND payload->>'decision'='approved' THEN
   SELECT * INTO rec FROM custom_u_production.hr_records_115 WHERE kind='shift' AND employee_id=previous.employee_id AND data->>'day'=previous.data->>'day';
   IF rec.id IS NOT NULL THEN
    sched:=((previous.data->>'day')::date+(previous.data->>'start')::time) AT TIME ZONE 'America/Nassau';
    a:=custom_u_production.hr_put_115(rec.id,'shift',rec.employee_id,rec.data||jsonb_build_object('scheduled_start',sched),u,t);
   END IF;
  END IF;
  target:=previous.employee_id;d:=previous.data||jsonb_build_object('status',payload->>'decision','decision_note',custom_u_production.hr_text_115(payload->'note',1000),'decided_by',u,'decided_at',t);
 ELSIF op='leave_request' THEN
  IF previous.id IS NOT NULL THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  day:=custom_u_production.hr_date_115(payload->'start_date');finish:=custom_u_production.hr_date_115(payload->'end_date');
  IF finish<day OR finish-day>366 OR day<today-90 OR day>today+730 THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  IF coalesce(payload->>'leave_type','') NOT IN ('Vacation','Sick','Emergency','Personal','Unpaid','Other','Time in lieu') THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  IF EXISTS(SELECT 1 FROM custom_u_production.hr_records_115 WHERE kind='leave' AND employee_id=u AND data->>'status' IN ('pending','approved') AND (data->>'start_date')::date<=finish AND (data->>'end_date')::date>=day) THEN RETURN jsonb_build_object('error','LEAVE_OVERLAP');END IF;
  k:='leave';d:=jsonb_build_object('start_date',day,'end_date',finish,'leave_type',payload->>'leave_type','reason',custom_u_production.hr_text_115(payload->'reason',1000),'status','pending');
  IF payload->>'leave_type'='Personal' THEN
   IF payload ? 'start_time' AND (jsonb_typeof(payload->'start_time') IS DISTINCT FROM 'string' OR coalesce(payload->>'start_time','')!~'^([01][0-9]|2[0-3]):[0-5][0-9]$') THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
   d:=d||jsonb_build_object('start_time',coalesce(payload->>'start_time','09:00'));
  ELSIF payload ? 'start_time' THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  IF payload->>'leave_type'='Time in lieu' THEN
   IF jsonb_typeof(payload->'lieu_minutes') IS DISTINCT FROM 'number' OR coalesce(payload->>'lieu_minutes','')!~'^[1-9][0-9]{0,5}$' THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
   minutes:=(payload->>'lieu_minutes')::int;
   SELECT count(*)*480 INTO max_minutes FROM generate_series(day,finish,interval '1 day') days(d) WHERE extract(isodow FROM days.d)<=5;
   IF minutes>max_minutes THEN RETURN jsonb_build_object('error','LIEU_DURATION_EXCEEDS_DATES');END IF;
   d:=d||jsonb_build_object('lieu_minutes',minutes);
  ELSIF payload ? 'lieu_minutes' THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;

 ELSIF op='leave_cancel' THEN
  IF previous.kind IS DISTINCT FROM 'leave' OR NOT (previous.employee_id=u OR manager) OR previous.data->>'status' NOT IN ('pending','approved') OR previous.data->>'status'='approved' AND NOT manager THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
  k:='leave';target:=previous.employee_id;d:=previous.data||jsonb_build_object('status','cancelled','decision_note',custom_u_production.hr_text_115(payload->'note',1000,true),'decided_by',u,'decided_at',t);
 ELSIF op='lieu_decide' THEN
  IF previous.kind IS DISTINCT FROM 'shift' OR previous.data->>'state'<>'out' THEN RETURN jsonb_build_object('error','CLOSE_SHIFT_FIRST');END IF;
  IF previous.employee_id=u AND NOT admin THEN RETURN jsonb_build_object('error','SELF_APPROVAL_NOT_ALLOWED');END IF;
  IF coalesce(payload->>'decision','') NOT IN ('approved','declined') THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  minutes:=custom_u_production.hr_overtime_minutes_1152(previous.data);
  IF minutes IS NULL THEN RETURN jsonb_build_object('error','SHIFT_REVIEW_REQUIRED');END IF;
  IF payload->>'decision'='approved' AND minutes=0 THEN RETURN jsonb_build_object('error','NO_ELIGIBLE_OVERTIME');END IF;
  k:='shift';target:=previous.employee_id;
  d:=previous.data||jsonb_build_object('lieu',jsonb_build_object('status',payload->>'decision','minutes',CASE WHEN payload->>'decision'='approved' THEN minutes ELSE 0 END,'decided_by',u,'decided_at',t,'note',custom_u_production.hr_text_115(payload->'note',1000,true)));
 ELSIF op='shift_correct' THEN
  IF previous.kind IS DISTINCT FROM 'shift' THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  IF previous.employee_id=u AND NOT admin THEN RETURN jsonb_build_object('error','SELF_APPROVAL_NOT_ALLOWED');END IF;
  started:=(payload->>'start')::timestamptz;ended:=(payload->>'end')::timestamptz;
  IF started IS NULL OR ended IS NULL OR ended<started OR ended-started>interval '16 hours' OR ended>t OR (started AT TIME ZONE 'America/Nassau')::date<>(previous.data->>'day')::date THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  k:='shift';target:=previous.employee_id;
  d:=previous.data||jsonb_build_object('state','out','correction',jsonb_build_object('in',started,'out',ended,'reason',custom_u_production.hr_text_115(payload->'reason',1000,true),'by',u,'at',t));
 ELSIF op IN ('kpi_save','kpi_progress') THEN
  k:='kpi';IF op='kpi_save' THEN
   IF previous.id IS NOT NULL AND previous.kind<>'kpi' THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
   target:=(payload->>'employee_id')::uuid;IF target IS NULL THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;IF previous.id IS NOT NULL AND previous.employee_id<>target THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;day:=custom_u_production.hr_date_115(payload->'period');IF extract(day FROM day)<>1 THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
   IF coalesce(payload->>'target','')!~'^[0-9]{1,9}(\.[0-9]{1,2})?$' OR coalesce(payload->>'direction','') NOT IN ('at_least','at_most') THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
   d:=jsonb_build_object('title',custom_u_production.hr_text_115(payload->'title',160,true),'period',day,'target',payload->>'target','unit',custom_u_production.hr_text_115(payload->'unit',30,true),'direction',payload->>'direction','actual',coalesce(previous.data->>'actual','0'),'notes',coalesce(previous.data->>'notes',''),'manager_note',custom_u_production.hr_text_115(payload->'manager_note',1000));
  ELSE
   IF previous.kind IS DISTINCT FROM 'kpi' OR NOT (manager OR previous.employee_id=u) THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
   IF coalesce(payload->>'actual','')!~'^[0-9]{1,9}(\.[0-9]{1,2})?$' THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
   target:=previous.employee_id;d:=previous.data||jsonb_build_object('actual',payload->>'actual','notes',custom_u_production.hr_text_115(payload->'notes',1000));
  END IF;
 ELSIF op='policy_save' THEN
  IF previous.id IS NOT NULL AND (previous.kind<>'policy' OR previous.data->>'status'<>'draft') THEN RETURN jsonb_build_object('error','POLICY_LOCKED');END IF;
  k:='policy';target:=NULL;d:=jsonb_build_object('title',custom_u_production.hr_text_115(payload->'title',160,true),'body',custom_u_production.hr_text_115(payload->'body',20000,true),'edition',custom_u_production.hr_text_115(payload->'edition',40,true),'status','draft');
 ELSIF op='policy_publish' THEN
  IF previous.kind IS DISTINCT FROM 'policy' OR previous.data->>'status'<>'draft' THEN RETURN jsonb_build_object('error','POLICY_LOCKED');END IF;
  k:='policy';target:=NULL;d:=previous.data||jsonb_build_object('status','published','published_at',t,'published_by',u);
 ELSIF op='policy_ack' THEN
  SELECT * INTO rec FROM custom_u_production.hr_records_115 WHERE id=(payload->>'policy_id')::uuid AND kind='policy' AND data->>'status'='published';
  IF rec.id IS NULL THEN RETURN jsonb_build_object('error','POLICY_NOT_PUBLISHED');END IF;
  SELECT * INTO previous FROM custom_u_production.hr_records_115 WHERE kind='ack' AND employee_id=u AND data->>'policy_id'=rec.id::text;
  IF previous.id IS NOT NULL THEN RETURN jsonb_build_object('data',to_jsonb(previous));END IF;
  k:='ack';d:=jsonb_build_object('policy_id',rec.id,'edition',rec.data->>'edition','acknowledged_at',t);
 ELSIF op='manager_save' THEN
  target:=(payload->>'employee_id')::uuid;IF target IS NULL THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;IF jsonb_typeof(payload->'active') IS DISTINCT FROM 'boolean' THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  SELECT * INTO previous FROM custom_u_production.hr_records_115 WHERE kind='manager' AND employee_id=target;
  IF coalesce((payload->>'version')::integer,0)<>coalesce(previous.version,0) THEN RETURN jsonb_build_object('error','VERSION_CONFLICT');END IF;
  IF previous.id IS NOT NULL THEN ident:=previous.id;END IF;
  k:='manager';d:=jsonb_build_object('active',payload->'active');
 ELSIF op='device_save' THEN
  IF coalesce(payload->>'digest','')!~'^[a-f0-9]{64}$' OR jsonb_typeof(payload->'active') IS DISTINCT FROM 'boolean' THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
  SELECT * INTO previous FROM custom_u_production.hr_records_115 WHERE kind='device' AND data->>'digest'=payload->>'digest';IF coalesce((payload->>'version')::integer,0)<>coalesce(previous.version,0) THEN RETURN jsonb_build_object('error','VERSION_CONFLICT');END IF;IF previous.id IS NOT NULL THEN ident:=previous.id;END IF;
  k:='device';target:=NULL;d:=jsonb_build_object('digest',payload->>'digest','name',custom_u_production.hr_text_115(payload->'name',100,true),'active',payload->'active');
 END IF;
 IF k='shift' AND op IN ('clock_in','clock_out','shift_correct') AND d ? 'lieu' THEN
  d:=d||jsonb_build_object('lieu',(d->'lieu')||jsonb_build_object('status','review_required','decided_by',u,'decided_at',t,'note','Shift changed. Review overtime again before crediting time in lieu.'));
 END IF;
 IF target IS NOT NULL AND NOT EXISTS(SELECT 1 FROM custom_u_production.staff_members WHERE user_id=target) THEN RETURN jsonb_build_object('error','STAFF_REQUIRED');END IF;
 result:=jsonb_build_object('data',custom_u_production.hr_put_115(ident,k,target,d,u,t));
 INSERT INTO custom_u_production.hr_requests_115(actor_id,request_id,payload,result,created_at) VALUES(u,rid,payload,result,t);
 RETURN result;
EXCEPTION WHEN invalid_text_representation OR invalid_datetime_format OR datetime_field_overflow OR numeric_value_out_of_range OR check_violation OR unique_violation THEN RETURN jsonb_build_object('error','INVALID_HR_DATA');
 WHEN raise_exception THEN IF SQLERRM='INVALID_HR_DATA' THEN RETURN jsonb_build_object('error','INVALID_HR_DATA');ELSE RAISE;END IF;
END; $function$
;
