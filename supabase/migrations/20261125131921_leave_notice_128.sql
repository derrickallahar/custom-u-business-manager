-- Planned leave notice is measured at submission, never at the later approval time.
-- Existing approvals, attendance and lieu balances are preserved.
SET lock_timeout='5s';
SELECT pg_advisory_xact_lock(115,115);
CREATE OR REPLACE FUNCTION custom_u_production.leave_notice_128(d jsonb, submitted_at timestamptz)
RETURNS jsonb LANGUAGE plpgsql STABLE SET search_path='' AS $$
DECLARE first_day date; starts_at timestamptz; eligible boolean;
BEGIN
 IF d->>'leave_type' NOT IN ('Personal','Vacation') THEN RETURN jsonb_build_object('required',false,'eligible',true);END IF;
 first_day:=(d->>'start_date')::date;
 IF d->>'leave_type'='Vacation' THEN
  eligible:=first_day-(submitted_at AT TIME ZONE 'America/Nassau')::date>=14;
  RETURN jsonb_build_object('required',true,'eligible',coalesce(eligible,false),'calendar_days',14,'error',CASE WHEN eligible THEN NULL ELSE 'VACATION_NOTICE_REQUIRED' END);
 END IF;
 starts_at:=(first_day+coalesce(d->>'start_time','09:00')::time) AT TIME ZONE 'America/Nassau';
 eligible:=extract(epoch FROM starts_at-submitted_at)>=86400;
 RETURN jsonb_build_object('required',true,'eligible',coalesce(eligible,false),'hours',24,'starts_at',starts_at,'error',CASE WHEN eligible THEN NULL ELSE 'PERSONAL_NOTICE_REQUIRED' END);
END $$;
REVOKE ALL ON FUNCTION custom_u_production.leave_notice_128(jsonb,timestamptz) FROM PUBLIC,anon,authenticated;

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
  IF started IS NULL OR ended IS NULL OR ended<=started OR ended-started>interval '16 hours' OR ended>t OR (started AT TIME ZONE 'America/Nassau')::date<>(previous.data->>'day')::date THEN RAISE EXCEPTION 'INVALID_HR_DATA';END IF;
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

-- A fresh edition keeps earlier reading and test records tied to their original content.
DO $edition128$
DECLARE previous custom_u_production.training_courses_127%ROWTYPE; next_id uuid; new_course jsonb:=$course128${"title":"Operating Custom U Business Manager","edition":"2","summary":"A practical guide to daily work, customer documents, mockups, production handover and staff responsibilities. Read all ten lessons, then complete the final knowledge test.","pass_percent":80,"estimated_minutes":45,"lessons":[{"title":"Start safely and find your work","body":"Use your own Business Manager account. Staff need both an approved computer browser and an approved office network, unless an administrator has granted a network exception. Office Wi-Fi alone does not approve a computer. A new browser, private window or cleared cookies can require approval again. Administrators manage access; do not share accounts to get around a restriction.\n\nOpen My account for your account and password options. Sign out on shared computers when you finish. Signing in does not clock you in.\n\nUse the left menu to open Customers, Quotes, Invoices, Production, Products & pricing, Client mockups, Client catalogues, HR & time clock and Team hub. Only areas your account may use are shown. New records and record links open in the same tab; use the page's Back link or main menu to return. Save before leaving a form.\n\nCheck whether a document is TEST or LIVE before saving or finalising it. Practice only with a manager-approved test exercise. Never send a practice document to a customer, record a practice payment against a live invoice, or use a real customer's information in training notes."},{"title":"Customers and product pricing","body":"Search Customers before creating a record. Open the existing customer when one is already present. Check the customer name, contact person, email, billing details and agreed payment terms. Report duplicates or conflicting details to your manager.\n\nOnly an administrator can approve discounts or apply a discount to a customer profile. Ask for approval instead of lowering a price to imitate a discount. Do not change another customer's details just to make a document fit.\n\nUse Products & pricing to review saved products. Unpriced or inactive items need manager or administrator attention before they can be used normally. Selling prices are in BSD before VAT; the configured standard rate for these products is 10%. Review the actual document's VAT setting and total before saving.\n\nFor products with options, choose the product line and then its run quantity, finish or other available choices. Quantity breaks apply at their minimum threshold: if mugs cost BSD 12.50 at 24 and BSD 12.00 at 50, an order of 25 still uses BSD 12.50 each. Do not assume every product is priced per piece.\n\nFor area-priced products, enter width and height for one piece, select inches or feet, enter the number of pieces and calculate the price. For example, 24 by 36 inches is 6 square feet; two pieces are 12 square feet. The calculator may add the result as one Job. Keep its dimensions and piece count in the description.\n\nPrint-run pricing is for the whole run. A 500-copy brochure run priced at BSD 220 is quantity 1, unit Run, price BSD 220, with 500 copies in the description. The agreed brochure specification is double-sided, 100 lb text. Production sheet size is internal and should not appear in the customer description unless specifically needed."},{"title":"Create and check a quote","body":"Open Quotes and choose New quote. Select the intended customer and contact, enter a clear job title and select TEST or LIVE deliberately. Add saved products using their relevant options or calculators. For each line check the description, quantity, unit, price, finish, placement, VAT and any approved discount.\n\nReview the complete price, deposit requirement, notes and terms. Save the draft and confirm that the app reports success. Open its preview or PDF and check the customer's name, specifications, totals, official Custom U logo and bank details. A saved draft can still need editing.\n\nFinalising locks the reviewed document; it does not send an email. Only finalise when the saved version is correct and you have the appropriate permission. If a finalised document needs a change, ask the authorised person to use the available correction workflow. Do not invent a new document number or edit a downloaded PDF to hide a discrepancy.\n\nFor an error or timeout, a save is not confirmed. Reopen or refresh the saved record before creating another one. Give the administrator the record number and the visible error message if you cannot establish what saved."},{"title":"Invoices and customer email","body":"Open Invoices and choose New invoice, or use the available action from a finalised quote. Confirm the source and customer. Check the invoice date, due date, document type, billing details, items, VAT, payment terms and notes. Save the draft, review the PDF, and then finalise only when correct and permitted.\n\nTo send a quote, invoice or catalogue, use its Email / history action. Review the recipient, subject, message and exact PDF attachment. Follow the preview and confirmation steps, then send once. Finalising and sending are separate actions.\n\nRead send history after sending. Accepted by Resend means the provider accepted the request; it does not prove inbox delivery or that the customer read it. A rejected result needs review. An uncertain or unconfirmed result needs an administrator to check the provider and history before another send. Do not repeatedly click Send to resolve uncertainty.\n\nCheck for a history entry for the correct document revision and recipient. If the document changes, prepare and review a fresh PDF before sending it. The bank details should identify Scotiabank, Custom U, Checking, transit 50385 at Bay St. East Branch, account 3337316. Report a mismatch to the administrator."},{"title":"Payments and production handover","body":"Only record a payment when you have permission and evidence of the payment. Check the customer, invoice number, amount, method, date and reference against the actual receipt or bank confirmation. Check existing payments first so the same receipt is not applied twice. A sent invoice is not a paid invoice.\n\nAfter recording a payment, confirm the saved result and remaining balance. If a payment is duplicated or entered incorrectly, ask the authorised person to use the reversal or correction workflow. Do not enter another payment or a negative amount merely to force the balance to look right.\n\nOpen Production to see job stages such as Planning / approvals, In production, Ready for collection / installation, Completed and On hold. Open the saved job and review its source, specifications, due date, artwork and handover information.\n\nUse the available stage-change controls only when the work has actually reached that stage. Enter a useful reason or handover note and confirm the change. Observe the job's approval and artwork requirements; a mockup by itself is not permission to produce. Keep a blocked job On hold and explain what is needed rather than marking it complete to remove it from the board."},{"title":"Build an accurate client mockup","body":"Open Client mockups and choose New mockup. Select the correct customer and product. Choose an existing product photo or select a new photo file, then select the customer's logo or artwork. Use clear images of the actual surface being branded.\n\nChoose the branding finish and position. Use the manual controls to move, resize and rotate the artwork. Update preview shows the result. Selecting a new product photo and pressing Update preview also uploads that selected photo when the required fields are complete. If the preview cannot proceed, read the nearby message, supply the missing information and try again.\n\nTo size a print in inches, enter the measured reference dimensions and mark the corresponding area on the photo. Set the print width and check the resulting size and fit. The measurement is only as accurate as the reference area and photograph: a perspective view, curved surface or incorrect measurement can mislead. Verify final production dimensions against the actual item or production artwork.\n\nReview the logo, finish, placement, size and customer before saving. Saved mockups are retained copies; create and save a new version for later changes. Use the presentation PDF for the customer and the production information for the team. A preview is not saved until the save action succeeds."},{"title":"Combine branding options and create a catalogue","body":"For alternative finishes such as UV printing and engraving, use the branding-options controls in the mockup editor. Select the finishes you want the customer to compare. For a shirt, add the required placements, such as left chest and back, centre chest and back, or sleeves.\n\nConfigure each placement with its correct product photo, artwork, position and size. Update preview and choose Use this preview for that placement. Use a back photo for the back and an appropriate sleeve view for a sleeve. A front photo does not become a back photo automatically.\n\nGenerate the selected options and inspect every generated result. Save options & create catalogue retains the mockups and opens the catalogue draft. Each finish becomes a catalogue option with its selected views together. Check all views belong to the intended product and customer.\n\nEnter and review the selling price for the complete branding combination. A left-chest-and-back option has one price for the combination; do not assume a single-placement price covers both. Review the VAT, description, finish and placement for each option, preview the catalogue PDF, then save it. Send through Email / history only after the customer details, options and attachment are correct."},{"title":"Time clock and time off","body":"Open HR & time clock, then Time clock. Click Clock in when you start work and Clock out when you stop. Signing in to Business Manager is separate. Check that each clock action is confirmed. Tell a manager about a missed or wrong event; do not create false clock entries to compensate.\n\nThe standard weekday shift is 9:00 a.m. to 5:00 p.m. Counted work before 9:00 a.m. needs an approved early start. Clocking in at 8:30 a.m. without approval does not create extra eligible time. If an approved shift starts at 8:30 a.m., eight counted hours finish at 4:30 p.m. A 9:30 a.m. start reaches eight counted hours at 5:30 p.m., if there is no clocked-out interval. No lunch deduction is automatic; time clocked out is excluded.\n\nRequesting time off\n\nSubmit planned time-off requests in Business Manager under HR → Time Off. Personal time off must be requested at least 24 hours before it starts. Vacation must be requested at least 14 calendar days before the first day of vacation. Planned requests that don’t meet these deadlines won’t be approved. Submitting a request does not mean it has been approved.\n\nIf you’re sick or have an emergency, notify your manager as soon as you can. These deadlines do not override leave entitlements under the law."},{"title":"Team information and employee privacy","body":"Use the small chat window or Team hub to message the intended colleague. Check the recipient before sending. Use clear job numbers and useful handover details. Keep sensitive employee identifiers and documents out of team chat and public bulletins.\n\nRead published bulletin-board notices and acknowledge those that require acknowledgement. In HR, read each published policy edition before acknowledging it. Acknowledgement records the edition and date; a new edition can need a new acknowledgement.\n\nIn KPIs, review the measure, period, target and whether it is an at-least or at-most target. Update your actual result and supporting notes honestly. The manager sets the target; saving a number does not automatically verify the work.\n\nAt first sign-in, employees can submit their own requested identification details. HR managers and administrators manage the private employee records and documents, including NIB, licence, passport, emergency contact and employment information. If those details need correction, contact HR privately. Never copy them into customer documents, training answers or team messages."},{"title":"Complete training and ask for help","body":"Open HR & time clock and select Training. Open the assigned course, read each lesson and mark it read. Progress is saved to your account so you can return later. Download the guide if you want a reading copy. A PDF download alone does not record course completion.\n\nAfter reading all lessons, complete every question in the final test and confirm that you completed the training yourself. The course displays its pass mark. This first course uses 80 percent: at least 16 of 20 answers must be correct. A pass records completion against this course edition, with the score and time. A failed attempt stays in the history; review the lessons and retake the test. Later attempts do not erase an earlier pass.\n\nHR managers and administrators can review progress and results, assign a course with an optional due date, and create future training. Save a draft, review its lessons, questions and correct answers, then publish. Published content is locked so earlier completion records keep their meaning. Use a new edition for revised material and assign that edition when retraining is needed.\n\nA knowledge test records understanding of the guide; it is not proof that every practical task has been mastered. Ask your supervisor to observe a test-mode quote, a mockup and catalogue preview, and an explanation of sending and clock-in rules. Do not send a customer email or change a live payment as a practice exercise.\n\nIf something fails, record the page, record number if any, steps and visible error. Do not share passwords or employee identification numbers in the report. Check saved state before retrying a financial or sending action, and ask the administrator for help when the outcome is uncertain."}],"questions":[{"prompt":"A staff member is on office Wi-Fi but sees “approved computer required”. What should happen?","options":["Use another employee’s account","Ask an administrator to approve that computer browser","Use a private window to bypass it"],"correct_index":1,"explanation":"Office network approval and computer-browser approval are separate."},{"prompt":"What happens when you sign in to Business Manager?","options":["You are automatically clocked in","Eight hours are credited immediately","You can use your authorised areas, but must clock in separately"],"correct_index":2,"explanation":"Use the Time clock action to record work."},{"prompt":"Who can approve a discount or apply one to a customer profile?","options":["An administrator","Any person preparing a quote","Any employee on office Wi-Fi"],"correct_index":0,"explanation":"Discount approval and customer-profile discounts are administrator actions."},{"prompt":"Mugs are BSD 12.50 each at 24 and BSD 12.00 at 50. Which rate applies to 25?","options":["BSD 12.00","BSD 12.50","An average of the two rates"],"correct_index":1,"explanation":"The lower rate starts when the quantity reaches 50."},{"prompt":"A 500-copy brochure run costs BSD 220 before VAT. Which line is correct?","options":["Quantity 500, price BSD 220 each","Quantity 1 Run, price BSD 220, description says 500 copies","Quantity 1, price BSD 0.44 for the whole job"],"correct_index":1,"explanation":"Run pricing represents the whole print run."},{"prompt":"Two pieces each measure 24 by 36 inches. What is their combined area?","options":["6 square feet","1,728 square feet","12 square feet"],"correct_index":2,"explanation":"One piece is 864 square inches, or 6 square feet. Two pieces are 12 square feet."},{"prompt":"Before finalising a live quote, what should you do?","options":["Review the saved details and PDF, including totals and customer","Assume the first calculation is correct","Remove the VAT so the total is lower"],"correct_index":0,"explanation":"Check the saved version before locking it."},{"prompt":"Does finalising an invoice automatically email it?","options":["Yes, always","No; sending uses the separate Email / history workflow","Only when a payment is due"],"correct_index":1,"explanation":"Finalising and sending are separate actions."},{"prompt":"Email history says “Accepted by Resend”. What does that prove?","options":["The customer read it","The invoice is paid","The email provider accepted the sending request"],"correct_index":2,"explanation":"Provider acceptance is not proof of inbox delivery or reading."},{"prompt":"An email result is uncertain. What is the safest next action?","options":["Keep clicking Send","Check history and ask an administrator to verify the provider before resending","Create three replacement invoices"],"correct_index":1,"explanation":"Avoid duplicate customer emails while the outcome is uncertain."},{"prompt":"You discover a payment was entered twice. What should you do?","options":["Ask the authorised person to review and reverse or correct the duplicate","Enter another payment","Change the invoice total to hide the balance"],"correct_index":0,"explanation":"Review the original evidence and use the authorised correction workflow."},{"prompt":"When should a job be marked Completed?","options":["As soon as a mockup exists","When someone asks about its status","When the work has actually reached that stage and required checks are satisfied"],"correct_index":2,"explanation":"Stages must describe real work and approval state."},{"prompt":"What makes an inch measurement on a mockup dependable?","options":["Typing any reference size","Using a measured reference area and verifying the final production dimensions","Enlarging the photo until it looks right"],"correct_index":1,"explanation":"Calibration depends on the measured area and the accuracy of the photograph."},{"prompt":"How should you prepare a left-chest-and-back mockup option?","options":["Reuse a front view and label it Back","Capture only the cheapest placement","Configure and review each placement using the correct surface photo"],"correct_index":2,"explanation":"Each surface needs the correct photo, artwork, position and size."},{"prompt":"A catalogue option has left-chest and back views. What price should you review?","options":["One selling price covering the complete combination","Only the left-chest price","A separate invoice total for each picture"],"correct_index":0,"explanation":"The combined option has one price for the agreed branding combination."},{"prompt":"An employee clocks in at 8:30 a.m. on a weekday without an approved early start. When does counted work normally begin?","options":["8:30 a.m.","9:00 a.m.","Whenever the employee signs out"],"correct_index":1,"explanation":"Unapproved time before the scheduled 9:00 a.m. start does not count."},{"prompt":"What should you do if you are sick or have an emergency?","options":["Wait until you can give 14 days of notice","Notify your manager as soon as you can; planned-leave deadlines do not override legal leave entitlements","Treat your request as automatically approved"],"correct_index":1,"explanation":"Notify your manager as soon as possible. Sickness and emergencies need manager review, and these planned-leave deadlines do not override legal entitlements."},{"prompt":"How much notice is required for planned personal time off and vacation?","options":["Personal: at least 24 hours before it starts. Vacation: at least 14 calendar days before the first day. Submission still requires approval.","Personal: the same day. Vacation: two working days.","No notice is needed if you submit the request online."],"correct_index":0,"explanation":"Planned personal time off requires 24 hours of notice and vacation requires 14 calendar days. Requests missing these deadlines cannot be approved; submitting is not approval."},{"prompt":"Where should private NIB, passport or employee-document corrections be handled?","options":["In a customer quote","Privately with HR or an administrator","On the general bulletin board"],"correct_index":1,"explanation":"Keep sensitive employee details within the authorised HR workflow."},{"prompt":"What records completion of this training course?","options":["Opening the PDF","Marking only the first lesson read","Reading all lessons, confirming your own participation and passing the final test"],"correct_index":2,"explanation":"Completion is linked to the signed-in account and the published course edition."}]}$course128$::jsonb;
BEGIN
 IF NOT custom_u_production.training_valid_127(new_course) THEN RAISE EXCEPTION 'INVALID_TRAINING_DATA';END IF;
 IF EXISTS(SELECT 1 FROM custom_u_production.training_courses_127 WHERE data->>'title'=new_course->>'title' AND data->>'edition'=new_course->>'edition') THEN RETURN;END IF;
 SELECT * INTO previous FROM custom_u_production.training_courses_127 WHERE data->>'title'=new_course->>'title' AND data->>'edition'='1' AND status='published' ORDER BY created_at LIMIT 1 FOR UPDATE;
 INSERT INTO custom_u_production.training_courses_127(data,status,published_at,assigned_all,due_date) VALUES(new_course,'published',now(),coalesce(previous.assigned_all,false),previous.due_date) RETURNING id INTO next_id;
 IF previous.id IS NOT NULL THEN
  INSERT INTO custom_u_production.training_assignments_127(course_id,employee_id,due_date,assigned_by,assigned_at) SELECT next_id,employee_id,due_date,assigned_by,assigned_at FROM custom_u_production.training_assignments_127 WHERE course_id=previous.id;
  UPDATE custom_u_production.training_courses_127 SET status='archived',version=version+1 WHERE id=previous.id;
 END IF;
END $edition128$;
RESET lock_timeout;
