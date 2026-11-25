-- Private training data. Browser clients use the gated RPC, never the tables.
CREATE TABLE IF NOT EXISTS custom_u_production.training_courses_127 (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), data jsonb NOT NULL,
 status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','archived')),
 version integer NOT NULL DEFAULT 1 CHECK(version>0), assigned_all boolean NOT NULL DEFAULT false,
 due_date date, created_by uuid, created_at timestamptz NOT NULL DEFAULT now(), published_at timestamptz
);
CREATE TABLE IF NOT EXISTS custom_u_production.training_assignments_127 (
 course_id uuid REFERENCES custom_u_production.training_courses_127(id), employee_id uuid NOT NULL,
 due_date date, assigned_by uuid NOT NULL, assigned_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(course_id,employee_id)
);
CREATE INDEX IF NOT EXISTS training_assignments_employee_127 ON custom_u_production.training_assignments_127(employee_id);
CREATE TABLE IF NOT EXISTS custom_u_production.training_progress_127 (
 course_id uuid REFERENCES custom_u_production.training_courses_127(id), employee_id uuid NOT NULL,
 read_lessons integer[] NOT NULL DEFAULT '{}', started_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
 best_score integer CHECK(best_score BETWEEN 0 AND 100), PRIMARY KEY(course_id,employee_id)
);
CREATE INDEX IF NOT EXISTS training_progress_employee_127 ON custom_u_production.training_progress_127(employee_id);
CREATE TABLE IF NOT EXISTS custom_u_production.training_attempts_127 (
 id uuid PRIMARY KEY, course_id uuid NOT NULL REFERENCES custom_u_production.training_courses_127(id), employee_id uuid NOT NULL,
 answers jsonb NOT NULL, correct_count integer NOT NULL, question_count integer NOT NULL,
 score integer NOT NULL CHECK(score BETWEEN 0 AND 100), passed boolean NOT NULL, submitted_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS training_attempts_employee_course_127 ON custom_u_production.training_attempts_127(employee_id,course_id,submitted_at);
CREATE INDEX IF NOT EXISTS training_attempts_course_127 ON custom_u_production.training_attempts_127(course_id);
CREATE TABLE IF NOT EXISTS custom_u_production.training_audit_127 (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, actor_id uuid NOT NULL, course_id uuid NOT NULL,
 action text NOT NULL, details jsonb NOT NULL, happened_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS training_audit_course_127 ON custom_u_production.training_audit_127(course_id);
CREATE TABLE IF NOT EXISTS custom_u_production.training_requests_127 (
 actor_id uuid NOT NULL, request_id uuid NOT NULL, payload jsonb NOT NULL, result jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(actor_id,request_id)
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['training_courses_127','training_assignments_127','training_progress_127','training_attempts_127','training_audit_127','training_requests_127'] LOOP
  EXECUTE format('ALTER TABLE custom_u_production.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('REVOKE ALL ON custom_u_production.%I FROM PUBLIC, anon, authenticated',t);
  IF NOT EXISTS(SELECT 1 FROM pg_policies WHERE schemaname='custom_u_production' AND tablename=t AND policyname='rpc_only') THEN
   EXECUTE format('CREATE POLICY rpc_only ON custom_u_production.%I AS RESTRICTIVE FOR ALL TO authenticated USING (false) WITH CHECK (false)',t);
  END IF;
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION custom_u_production.training_valid_127(d jsonb) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE SET search_path='' AS $$
DECLARE item jsonb; v jsonb; s text;
BEGIN
 IF jsonb_typeof(d) IS DISTINCT FROM 'object' OR d-ARRAY['title','edition','summary','lessons','questions','pass_percent','estimated_minutes']<>'{}'::jsonb THEN RETURN false; END IF;
 FOREACH s IN ARRAY ARRAY['title','edition','summary'] LOOP
  IF jsonb_typeof(d->s) IS DISTINCT FROM 'string' OR length(btrim(d->>s))<1 OR length(d->>s)>(CASE s WHEN 'summary' THEN 2000 WHEN 'edition' THEN 40 ELSE 160 END) THEN RETURN false;END IF;
 END LOOP;
 IF jsonb_typeof(d->'pass_percent') IS DISTINCT FROM 'number' OR coalesce(d->>'pass_percent','')!~'^[0-9]{1,3}$' OR (d->>'pass_percent')::int NOT BETWEEN 1 AND 100
 OR jsonb_typeof(d->'estimated_minutes') IS DISTINCT FROM 'number' OR coalesce(d->>'estimated_minutes','')!~'^[0-9]{1,3}$' OR (d->>'estimated_minutes')::int NOT BETWEEN 1 AND 999 THEN RETURN false;END IF;
 IF jsonb_typeof(d->'lessons') IS DISTINCT FROM 'array' OR jsonb_typeof(d->'questions') IS DISTINCT FROM 'array' THEN RETURN false;END IF;
 IF jsonb_array_length(d->'lessons') NOT BETWEEN 1 AND 30 OR jsonb_array_length(d->'questions') NOT BETWEEN 1 AND 50 THEN RETURN false;END IF;
 FOR item IN SELECT value FROM jsonb_array_elements(d->'lessons') LOOP
  IF jsonb_typeof(item) IS DISTINCT FROM 'object' OR item-ARRAY['title','body']<>'{}'::jsonb OR custom_u_production.catalogue_text_108(item->'title',160,true) IS DISTINCT FROM true OR custom_u_production.catalogue_text_108(item->'body',20000,true) IS DISTINCT FROM true THEN RETURN false;END IF;
 END LOOP;
 FOR item IN SELECT value FROM jsonb_array_elements(d->'questions') LOOP
  IF jsonb_typeof(item) IS DISTINCT FROM 'object' OR item-ARRAY['prompt','options','correct_index','explanation']<>'{}'::jsonb OR custom_u_production.catalogue_text_108(item->'prompt',1000,true) IS DISTINCT FROM true OR custom_u_production.catalogue_text_108(item->'explanation',2000,true) IS DISTINCT FROM true OR jsonb_typeof(item->'options') IS DISTINCT FROM 'array' THEN RETURN false;END IF;
  IF jsonb_array_length(item->'options') NOT BETWEEN 2 AND 6 OR jsonb_typeof(item->'correct_index') IS DISTINCT FROM 'number' OR coalesce(item->>'correct_index','')!~'^[0-5]$' OR (item->>'correct_index')::int>=jsonb_array_length(item->'options') THEN RETURN false;END IF;
  FOR v IN SELECT value FROM jsonb_array_elements(item->'options') LOOP IF custom_u_production.catalogue_text_108(v,500,true) IS DISTINCT FROM true THEN RETURN false;END IF;END LOOP;
 END LOOP;
 RETURN octet_length(d::text)<=200000;
EXCEPTION WHEN OTHERS THEN RETURN false;
END $$;

CREATE OR REPLACE FUNCTION custom_u_production.training_public_127(d jsonb) RETURNS jsonb LANGUAGE sql IMMUTABLE SET search_path='' AS $$
 SELECT jsonb_set(d,'{questions}',(SELECT jsonb_agg(q-ARRAY['correct_index','explanation'] ORDER BY ord) FROM jsonb_array_elements(d->'questions') WITH ORDINALITY e(q,ord)));
$$;

CREATE OR REPLACE FUNCTION custom_u_production.training_rpc_127(payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE u uuid:=auth.uid(); who jsonb; manager boolean; op text:=payload->>'op'; c custom_u_production.training_courses_127%ROWTYPE;
 p custom_u_production.training_progress_127%ROWTYPE; receipt custom_u_production.training_requests_127%ROWTYPE;
 ident uuid; rid uuid; result jsonb; allowed text[]; i integer; correct integer:=0; total integer; score integer; passed boolean; ans jsonb; target uuid; t timestamptz:=clock_timestamp();
BEGIN
 PERFORM 1 FROM custom_u_production.staff_members WHERE user_id=u FOR SHARE;
 PERFORM 1 FROM custom_u_production.staff_access_102 WHERE user_id=u FOR SHARE;
 who:=custom_u_production.session_access_102();
 IF u IS NULL OR who IS NULL THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 -- Shares the HR approval lock, so permission changes cannot race a training write.
 PERFORM pg_advisory_xact_lock(115,115);
 manager:=who->>'role'='admin' OR EXISTS(SELECT 1 FROM custom_u_production.hr_records_115 WHERE kind='manager' AND employee_id=u AND data->'active'='true'::jsonb);
 IF jsonb_typeof(payload) IS DISTINCT FROM 'object' OR octet_length(payload::text)>240000 THEN RETURN jsonb_build_object('error','INVALID_TRAINING_DATA');END IF;
 IF op='list' THEN
  RETURN jsonb_build_object('manager',manager,'user_id',u,'courses',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'id',cc.id,'title',cc.data->>'title','edition',cc.data->>'edition','summary',cc.data->>'summary','pass_percent',cc.data->'pass_percent','estimated_minutes',cc.data->'estimated_minutes',
   'status',cc.status,'version',cc.version,'lesson_count',jsonb_array_length(cc.data->'lessons'),'question_count',jsonb_array_length(cc.data->'questions'),
   'assigned',cc.assigned_all OR aa.employee_id IS NOT NULL,'due_date',CASE WHEN cc.assigned_all THEN cc.due_date ELSE aa.due_date END,
   'progress',to_jsonb(pp)) ORDER BY cc.created_at DESC),'[]') FROM custom_u_production.training_courses_127 cc
   LEFT JOIN custom_u_production.training_progress_127 pp ON pp.course_id=cc.id AND pp.employee_id=u
   LEFT JOIN custom_u_production.training_assignments_127 aa ON aa.course_id=cc.id AND aa.employee_id=u
   WHERE manager OR cc.status='published' OR cc.status='archived' AND pp.employee_id IS NOT NULL),
   'people',CASE WHEN manager THEN (SELECT coalesce(jsonb_agg(jsonb_build_object('id',m.user_id,'email',au.email,'active',m.active AND (m.role='admin' OR coalesce(sa.active,false))) ORDER BY au.email),'[]') FROM custom_u_production.staff_members m JOIN auth.users au ON au.id=m.user_id LEFT JOIN custom_u_production.staff_access_102 sa ON sa.user_id=m.user_id) ELSE '[]'::jsonb END);
 END IF;
 IF op='backup' THEN
  IF who->>'role'<>'admin' THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
  RETURN jsonb_build_object('courses',(SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY id),'[]') FROM custom_u_production.training_courses_127 x),
  'assignments',(SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY course_id,employee_id),'[]') FROM custom_u_production.training_assignments_127 x),
  'progress',(SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY course_id,employee_id),'[]') FROM custom_u_production.training_progress_127 x),
  'attempts',(SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY submitted_at,id),'[]') FROM custom_u_production.training_attempts_127 x),
  'audit',(SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY id),'[]') FROM custom_u_production.training_audit_127 x),
  'requests',(SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY actor_id,request_id),'[]') FROM custom_u_production.training_requests_127 x));
 END IF;
 IF op NOT IN ('get','report','save','publish','archive','assign','read','submit') OR op IS NULL THEN RETURN jsonb_build_object('error','INVALID_OPERATION');END IF;
 IF op IN ('report','save','publish','archive','assign') AND NOT manager THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 ident:=(payload->>'id')::uuid;
 IF ident IS NULL THEN RETURN jsonb_build_object('error','INVALID_TRAINING_DATA');END IF;
 SELECT * INTO c FROM custom_u_production.training_courses_127 WHERE id=ident FOR UPDATE;
 IF c.id IS NULL AND op<>'save' THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;
 IF c.id IS NOT NULL AND NOT manager AND (c.status='draft' OR c.status='archived' AND NOT EXISTS(SELECT 1 FROM custom_u_production.training_progress_127 WHERE course_id=ident AND employee_id=u)) THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;
 IF op='get' THEN
  RETURN jsonb_build_object('course',to_jsonb(c)||jsonb_build_object('data',CASE WHEN manager THEN c.data ELSE custom_u_production.training_public_127(c.data) END),
  'progress',(SELECT to_jsonb(x) FROM custom_u_production.training_progress_127 x WHERE course_id=ident AND employee_id=u),
  'attempts',(SELECT coalesce(jsonb_agg(to_jsonb(x)-'answers' ORDER BY submitted_at DESC),'[]') FROM (SELECT * FROM custom_u_production.training_attempts_127 WHERE course_id=ident AND employee_id=u ORDER BY submitted_at DESC LIMIT 100) x),
  'assignments',CASE WHEN manager THEN (SELECT coalesce(jsonb_agg(to_jsonb(x)),'[]') FROM custom_u_production.training_assignments_127 x WHERE course_id=ident) ELSE '[]'::jsonb END);
 END IF;
 IF op='report' THEN
  RETURN jsonb_build_object('course',jsonb_build_object('id',c.id,'title',c.data->>'title','edition',c.data->>'edition'),
  'rows',(SELECT coalesce(jsonb_agg(jsonb_build_object('employee_id',m.user_id,'email',au.email,'active',m.active AND (m.role='admin' OR coalesce(sa.active,false)),
  'assigned',c.assigned_all OR aa.employee_id IS NOT NULL,'due_date',CASE WHEN c.assigned_all THEN c.due_date ELSE aa.due_date END,
  'progress',to_jsonb(pp),'attempt_count',(SELECT count(*) FROM custom_u_production.training_attempts_127 ta WHERE ta.course_id=ident AND ta.employee_id=m.user_id)) ORDER BY au.email),'[]')
  FROM custom_u_production.staff_members m JOIN auth.users au ON au.id=m.user_id LEFT JOIN custom_u_production.staff_access_102 sa ON sa.user_id=m.user_id
  LEFT JOIN custom_u_production.training_progress_127 pp ON pp.course_id=ident AND pp.employee_id=m.user_id LEFT JOIN custom_u_production.training_assignments_127 aa ON aa.course_id=ident AND aa.employee_id=m.user_id),
  'attempts',(SELECT coalesce(jsonb_agg(to_jsonb(x)-'answers' ORDER BY submitted_at DESC),'[]') FROM (SELECT * FROM custom_u_production.training_attempts_127 WHERE course_id=ident ORDER BY submitted_at DESC LIMIT 1000) x));
 END IF;
 allowed:=CASE op WHEN 'save' THEN ARRAY['op','id','request_id','version','data'] WHEN 'publish' THEN ARRAY['op','id','request_id','version'] WHEN 'archive' THEN ARRAY['op','id','request_id','version'] WHEN 'assign' THEN ARRAY['op','id','request_id','version','all','employees','due_date'] WHEN 'read' THEN ARRAY['op','id','request_id','lesson'] WHEN 'submit' THEN ARRAY['op','id','request_id','answers','acknowledge'] END;
 IF payload-allowed<>'{}'::jsonb OR coalesce(payload->>'request_id','')!~'^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$' THEN RETURN jsonb_build_object('error','INVALID_TRAINING_DATA');END IF;
 rid:=(payload->>'request_id')::uuid;
 SELECT * INTO receipt FROM custom_u_production.training_requests_127 WHERE actor_id=u AND request_id=rid;
 IF FOUND THEN IF receipt.payload=payload THEN RETURN receipt.result;ELSE RETURN jsonb_build_object('error','REQUEST_CONFLICT');END IF;END IF;
 IF (SELECT count(*) FROM custom_u_production.training_requests_127)>200000 THEN RETURN jsonb_build_object('error','TRAINING_HISTORY_LIMIT');END IF;
 IF op IN ('save','publish','archive','assign') THEN
  IF jsonb_typeof(payload->'version') IS DISTINCT FROM 'number' OR coalesce(payload->>'version','')!~'^[0-9]{1,9}$' OR (payload->>'version')::int<>coalesce(c.version,0) THEN RETURN jsonb_build_object('error','VERSION_CONFLICT');END IF;
 END IF;
 IF op='save' THEN
  IF c.id IS NOT NULL AND c.status<>'draft' THEN RETURN jsonb_build_object('error','COURSE_LOCKED');END IF;
  IF NOT custom_u_production.training_valid_127(payload->'data') THEN RETURN jsonb_build_object('error','INVALID_TRAINING_DATA');END IF;
  INSERT INTO custom_u_production.training_courses_127(id,data,created_by) VALUES(ident,payload->'data',u)
  ON CONFLICT(id) DO UPDATE SET data=excluded.data,version=training_courses_127.version+1;
 ELSIF op='publish' THEN
  IF c.status<>'draft' THEN RETURN jsonb_build_object('error','COURSE_LOCKED');END IF;
  IF NOT custom_u_production.training_valid_127(c.data) THEN RETURN jsonb_build_object('error','INVALID_TRAINING_DATA');END IF;
  UPDATE custom_u_production.training_courses_127 SET status='published',published_at=t,version=version+1 WHERE id=ident;
 ELSIF op='archive' THEN
  IF c.status='archived' THEN RETURN jsonb_build_object('error','COURSE_LOCKED');END IF;
  UPDATE custom_u_production.training_courses_127 SET status='archived',version=version+1 WHERE id=ident;
 ELSIF op='assign' THEN
  IF c.status<>'published' THEN RETURN jsonb_build_object('error','COURSE_NOT_PUBLISHED');END IF;
  IF jsonb_typeof(payload->'all') IS DISTINCT FROM 'boolean' OR jsonb_typeof(payload->'employees') IS DISTINCT FROM 'array' OR NOT (payload ? 'due_date') THEN RETURN jsonb_build_object('error','INVALID_TRAINING_DATA');END IF;
  IF jsonb_array_length(payload->'employees')>1000 OR payload->'all'='true'::jsonb AND jsonb_array_length(payload->'employees')<>0 THEN RETURN jsonb_build_object('error','INVALID_TRAINING_DATA');END IF;
  IF payload->'due_date'<>'null'::jsonb AND (jsonb_typeof(payload->'due_date')<>'string' OR (payload->>'due_date')!~'^[0-9]{4}-[0-9]{2}-[0-9]{2}$') THEN RETURN jsonb_build_object('error','INVALID_TRAINING_DATA');END IF;
  -- Validate the whole assignment before deleting any earlier selection.
  FOR ans IN SELECT value FROM jsonb_array_elements(payload->'employees') LOOP
   target:=(ans#>>'{}')::uuid;
   IF target IS NULL OR NOT EXISTS(SELECT 1 FROM custom_u_production.staff_members WHERE user_id=target) THEN RETURN jsonb_build_object('error','STAFF_REQUIRED');END IF;
  END LOOP;
  DELETE FROM custom_u_production.training_assignments_127 WHERE course_id=ident;
  FOR ans IN SELECT DISTINCT value FROM jsonb_array_elements(payload->'employees') LOOP
   INSERT INTO custom_u_production.training_assignments_127(course_id,employee_id,due_date,assigned_by) VALUES(ident,(ans#>>'{}')::uuid,(payload->>'due_date')::date,u);
  END LOOP;
  UPDATE custom_u_production.training_courses_127 SET assigned_all=(payload->>'all')::boolean,due_date=(payload->>'due_date')::date,version=version+1 WHERE id=ident;
 ELSE
  IF c.status<>'published' THEN RETURN jsonb_build_object('error','COURSE_NOT_PUBLISHED');END IF;
  IF op='read' THEN
   IF jsonb_typeof(payload->'lesson') IS DISTINCT FROM 'number' OR coalesce(payload->>'lesson','')!~'^[0-9]{1,2}$' OR (payload->>'lesson')::int>=jsonb_array_length(c.data->'lessons') THEN RETURN jsonb_build_object('error','INVALID_TRAINING_DATA');END IF;
   INSERT INTO custom_u_production.training_progress_127(course_id,employee_id) VALUES(ident,u) ON CONFLICT DO NOTHING;
   UPDATE custom_u_production.training_progress_127 SET read_lessons=ARRAY(SELECT DISTINCT x FROM unnest(read_lessons||ARRAY[(payload->>'lesson')::int]) x ORDER BY x) WHERE course_id=ident AND employee_id=u;
  ELSE
   SELECT * INTO p FROM custom_u_production.training_progress_127 WHERE course_id=ident AND employee_id=u;
   IF p.course_id IS NULL OR cardinality(p.read_lessons)<>jsonb_array_length(c.data->'lessons') THEN RETURN jsonb_build_object('error','READ_LESSONS_FIRST');END IF;
   IF payload->'acknowledge' IS DISTINCT FROM 'true'::jsonb OR jsonb_typeof(payload->'answers') IS DISTINCT FROM 'array' THEN RETURN jsonb_build_object('error','INVALID_TRAINING_DATA');END IF;
   total:=jsonb_array_length(c.data->'questions');
   IF jsonb_array_length(payload->'answers')<>total THEN RETURN jsonb_build_object('error','ANSWER_EVERY_QUESTION');END IF;
   FOR i IN 0..total-1 LOOP
    ans:=payload->'answers'->i;
    IF jsonb_typeof(ans) IS DISTINCT FROM 'number' OR (ans#>>'{}')!~'^[0-5]$' OR (ans#>>'{}')::int>=jsonb_array_length(c.data->'questions'->i->'options') THEN RETURN jsonb_build_object('error','ANSWER_EVERY_QUESTION');END IF;
    IF ans=c.data->'questions'->i->'correct_index' THEN correct:=correct+1;END IF;
   END LOOP;
   score:=floor(correct*100.0/total);passed:=correct*100 >= (c.data->>'pass_percent')::int*total;
   INSERT INTO custom_u_production.training_attempts_127(id,course_id,employee_id,answers,correct_count,question_count,score,passed,submitted_at) VALUES(rid,ident,u,payload->'answers',correct,total,score,passed,t);
   UPDATE custom_u_production.training_progress_127 SET best_score=greatest(coalesce(best_score,0),score),completed_at=CASE WHEN passed THEN coalesce(completed_at,t) ELSE completed_at END WHERE course_id=ident AND employee_id=u;
  END IF;
 END IF;
 IF op IN ('save','publish','archive','assign') THEN
  SELECT * INTO c FROM custom_u_production.training_courses_127 WHERE id=ident;
  INSERT INTO custom_u_production.training_audit_127(actor_id,course_id,action,details) VALUES(u,ident,op,jsonb_build_object('course',to_jsonb(c),'assignments',(SELECT coalesce(jsonb_agg(to_jsonb(x)),'[]') FROM custom_u_production.training_assignments_127 x WHERE course_id=ident)));
  result:=jsonb_build_object('id',ident,'version',c.version,'status',c.status);
 ELSE
  SELECT * INTO p FROM custom_u_production.training_progress_127 WHERE course_id=ident AND employee_id=u;
  result:=jsonb_build_object('progress',to_jsonb(p));
  IF op='submit' THEN result:=result||jsonb_build_object('attempt',(SELECT to_jsonb(x)-'answers' FROM custom_u_production.training_attempts_127 x WHERE id=rid));END IF;
 END IF;
 INSERT INTO custom_u_production.training_requests_127(actor_id,request_id,payload,result) VALUES(u,rid,payload,result);
 RETURN result;
EXCEPTION WHEN invalid_text_representation OR invalid_datetime_format OR datetime_field_overflow OR numeric_value_out_of_range OR check_violation OR not_null_violation OR unique_violation THEN RETURN jsonb_build_object('error','INVALID_TRAINING_DATA');
END $$;
CREATE OR REPLACE FUNCTION public.custom_u_training_127(payload jsonb) RETURNS jsonb LANGUAGE sql SET search_path='' AS $$ SELECT custom_u_production.training_rpc_127(payload); $$;
REVOKE ALL ON FUNCTION custom_u_production.training_valid_127(jsonb),custom_u_production.training_public_127(jsonb),custom_u_production.training_rpc_127(jsonb),public.custom_u_training_127(jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION custom_u_production.training_rpc_127(jsonb),public.custom_u_training_127(jsonb) TO authenticated;

-- Seed once; later edits and editions are created through HR.
INSERT INTO custom_u_production.training_courses_127(data,status,published_at)
SELECT $course127${
  "title": "Operating Custom U Business Manager",
  "edition": "1",
  "summary": "A practical guide to daily work, customer documents, mockups, production handover and staff responsibilities. Read all ten lessons, then complete the final knowledge test.",
  "pass_percent": 80,
  "estimated_minutes": 45,
  "lessons": [
    {
      "title": "Start safely and find your work",
      "body": "Use your own Business Manager account. Staff need both an approved computer browser and an approved office network, unless an administrator has granted a network exception. Office Wi-Fi alone does not approve a computer. A new browser, private window or cleared cookies can require approval again. Administrators manage access; do not share accounts to get around a restriction.\n\nOpen My account for your account and password options. Sign out on shared computers when you finish. Signing in does not clock you in.\n\nUse the left menu to open Customers, Quotes, Invoices, Production, Products & pricing, Client mockups, Client catalogues, HR & time clock and Team hub. Only areas your account may use are shown. New records and record links open in the same tab; use the page's Back link or main menu to return. Save before leaving a form.\n\nCheck whether a document is TEST or LIVE before saving or finalising it. Practice only with a manager-approved test exercise. Never send a practice document to a customer, record a practice payment against a live invoice, or use a real customer's information in training notes."
    },
    {
      "title": "Customers and product pricing",
      "body": "Search Customers before creating a record. Open the existing customer when one is already present. Check the customer name, contact person, email, billing details and agreed payment terms. Report duplicates or conflicting details to your manager.\n\nOnly an administrator can approve discounts or apply a discount to a customer profile. Ask for approval instead of lowering a price to imitate a discount. Do not change another customer's details just to make a document fit.\n\nUse Products & pricing to review saved products. Unpriced or inactive items need manager or administrator attention before they can be used normally. Selling prices are in BSD before VAT; the configured standard rate for these products is 10%. Review the actual document's VAT setting and total before saving.\n\nFor products with options, choose the product line and then its run quantity, finish or other available choices. Quantity breaks apply at their minimum threshold: if mugs cost BSD 12.50 at 24 and BSD 12.00 at 50, an order of 25 still uses BSD 12.50 each. Do not assume every product is priced per piece.\n\nFor area-priced products, enter width and height for one piece, select inches or feet, enter the number of pieces and calculate the price. For example, 24 by 36 inches is 6 square feet; two pieces are 12 square feet. The calculator may add the result as one Job. Keep its dimensions and piece count in the description.\n\nPrint-run pricing is for the whole run. A 500-copy brochure run priced at BSD 220 is quantity 1, unit Run, price BSD 220, with 500 copies in the description. The agreed brochure specification is double-sided, 100 lb text. Production sheet size is internal and should not appear in the customer description unless specifically needed."
    },
    {
      "title": "Create and check a quote",
      "body": "Open Quotes and choose New quote. Select the intended customer and contact, enter a clear job title and select TEST or LIVE deliberately. Add saved products using their relevant options or calculators. For each line check the description, quantity, unit, price, finish, placement, VAT and any approved discount.\n\nReview the complete price, deposit requirement, notes and terms. Save the draft and confirm that the app reports success. Open its preview or PDF and check the customer's name, specifications, totals, official Custom U logo and bank details. A saved draft can still need editing.\n\nFinalising locks the reviewed document; it does not send an email. Only finalise when the saved version is correct and you have the appropriate permission. If a finalised document needs a change, ask the authorised person to use the available correction workflow. Do not invent a new document number or edit a downloaded PDF to hide a discrepancy.\n\nFor an error or timeout, a save is not confirmed. Reopen or refresh the saved record before creating another one. Give the administrator the record number and the visible error message if you cannot establish what saved."
    },
    {
      "title": "Invoices and customer email",
      "body": "Open Invoices and choose New invoice, or use the available action from a finalised quote. Confirm the source and customer. Check the invoice date, due date, document type, billing details, items, VAT, payment terms and notes. Save the draft, review the PDF, and then finalise only when correct and permitted.\n\nTo send a quote, invoice or catalogue, use its Email / history action. Review the recipient, subject, message and exact PDF attachment. Follow the preview and confirmation steps, then send once. Finalising and sending are separate actions.\n\nRead send history after sending. Accepted by Resend means the provider accepted the request; it does not prove inbox delivery or that the customer read it. A rejected result needs review. An uncertain or unconfirmed result needs an administrator to check the provider and history before another send. Do not repeatedly click Send to resolve uncertainty.\n\nCheck for a history entry for the correct document revision and recipient. If the document changes, prepare and review a fresh PDF before sending it. The bank details should identify Scotiabank, Custom U, Checking, transit 50385 at Bay St. East Branch, account 3337316. Report a mismatch to the administrator."
    },
    {
      "title": "Payments and production handover",
      "body": "Only record a payment when you have permission and evidence of the payment. Check the customer, invoice number, amount, method, date and reference against the actual receipt or bank confirmation. Check existing payments first so the same receipt is not applied twice. A sent invoice is not a paid invoice.\n\nAfter recording a payment, confirm the saved result and remaining balance. If a payment is duplicated or entered incorrectly, ask the authorised person to use the reversal or correction workflow. Do not enter another payment or a negative amount merely to force the balance to look right.\n\nOpen Production to see job stages such as Planning / approvals, In production, Ready for collection / installation, Completed and On hold. Open the saved job and review its source, specifications, due date, artwork and handover information.\n\nUse the available stage-change controls only when the work has actually reached that stage. Enter a useful reason or handover note and confirm the change. Observe the job's approval and artwork requirements; a mockup by itself is not permission to produce. Keep a blocked job On hold and explain what is needed rather than marking it complete to remove it from the board."
    },
    {
      "title": "Build an accurate client mockup",
      "body": "Open Client mockups and choose New mockup. Select the correct customer and product. Choose an existing product photo or select a new photo file, then select the customer's logo or artwork. Use clear images of the actual surface being branded.\n\nChoose the branding finish and position. Use the manual controls to move, resize and rotate the artwork. Update preview shows the result. Selecting a new product photo and pressing Update preview also uploads that selected photo when the required fields are complete. If the preview cannot proceed, read the nearby message, supply the missing information and try again.\n\nTo size a print in inches, enter the measured reference dimensions and mark the corresponding area on the photo. Set the print width and check the resulting size and fit. The measurement is only as accurate as the reference area and photograph: a perspective view, curved surface or incorrect measurement can mislead. Verify final production dimensions against the actual item or production artwork.\n\nReview the logo, finish, placement, size and customer before saving. Saved mockups are retained copies; create and save a new version for later changes. Use the presentation PDF for the customer and the production information for the team. A preview is not saved until the save action succeeds."
    },
    {
      "title": "Combine branding options and create a catalogue",
      "body": "For alternative finishes such as UV printing and engraving, use the branding-options controls in the mockup editor. Select the finishes you want the customer to compare. For a shirt, add the required placements, such as left chest and back, centre chest and back, or sleeves.\n\nConfigure each placement with its correct product photo, artwork, position and size. Update preview and choose Use this preview for that placement. Use a back photo for the back and an appropriate sleeve view for a sleeve. A front photo does not become a back photo automatically.\n\nGenerate the selected options and inspect every generated result. Save options & create catalogue retains the mockups and opens the catalogue draft. Each finish becomes a catalogue option with its selected views together. Check all views belong to the intended product and customer.\n\nEnter and review the selling price for the complete branding combination. A left-chest-and-back option has one price for the combination; do not assume a single-placement price covers both. Review the VAT, description, finish and placement for each option, preview the catalogue PDF, then save it. Send through Email / history only after the customer details, options and attachment are correct."
    },
    {
      "title": "Time clock and time off",
      "body": "Open HR & time clock, then Time clock. Click Clock in when you start work and Clock out when you stop. Signing in to Business Manager is separate. Check that each clock action is confirmed. Tell a manager about a missed or wrong event; do not create false clock entries to compensate.\n\nThe standard weekday shift is 9:00 a.m. to 5:00 p.m. Counted work before 9:00 a.m. needs an approved early start. Clocking in at 8:30 a.m. without approval does not create extra eligible time. If an approved shift starts at 8:30 a.m., eight counted hours finish at 4:30 p.m. A 9:30 a.m. start reaches eight counted hours at 5:30 p.m., if there is no clocked-out interval. No lunch deduction is automatic; time clocked out is excluded.\n\nOvertime is recorded by the minute. One eligible weekday overtime minute earns one minute of time in lieu after manager approval. All counted Saturday and Sunday minutes are eligible for the same approval. Eligible time is not yet an approved leave balance.\n\nIn Time off, select dates and the leave type, enter the reason and submit the request. For Time in lieu, specify hours and additional minutes. A full working day is eight hours. Wait for approval; pending requests do not reserve lieu time. Check the available balance and status. A manager must approve eligible time before it is available, and approved lieu leave deducts from that balance."
    },
    {
      "title": "Team information and employee privacy",
      "body": "Use the small chat window or Team hub to message the intended colleague. Check the recipient before sending. Use clear job numbers and useful handover details. Keep sensitive employee identifiers and documents out of team chat and public bulletins.\n\nRead published bulletin-board notices and acknowledge those that require acknowledgement. In HR, read each published policy edition before acknowledging it. Acknowledgement records the edition and date; a new edition can need a new acknowledgement.\n\nIn KPIs, review the measure, period, target and whether it is an at-least or at-most target. Update your actual result and supporting notes honestly. The manager sets the target; saving a number does not automatically verify the work.\n\nAt first sign-in, employees can submit their own requested identification details. HR managers and administrators manage the private employee records and documents, including NIB, licence, passport, emergency contact and employment information. If those details need correction, contact HR privately. Never copy them into customer documents, training answers or team messages."
    },
    {
      "title": "Complete training and ask for help",
      "body": "Open HR & time clock and select Training. Open the assigned course, read each lesson and mark it read. Progress is saved to your account so you can return later. Download the guide if you want a reading copy. A PDF download alone does not record course completion.\n\nAfter reading all lessons, complete every question in the final test and confirm that you completed the training yourself. The course displays its pass mark. This first course uses 80 percent: at least 16 of 20 answers must be correct. A pass records completion against this course edition, with the score and time. A failed attempt stays in the history; review the lessons and retake the test. Later attempts do not erase an earlier pass.\n\nHR managers and administrators can review progress and results, assign a course with an optional due date, and create future training. Save a draft, review its lessons, questions and correct answers, then publish. Published content is locked so earlier completion records keep their meaning. Use a new edition for revised material and assign that edition when retraining is needed.\n\nA knowledge test records understanding of the guide; it is not proof that every practical task has been mastered. Ask your supervisor to observe a test-mode quote, a mockup and catalogue preview, and an explanation of sending and clock-in rules. Do not send a customer email or change a live payment as a practice exercise.\n\nIf something fails, record the page, record number if any, steps and visible error. Do not share passwords or employee identification numbers in the report. Check saved state before retrying a financial or sending action, and ask the administrator for help when the outcome is uncertain."
    }
  ],
  "questions": [
    {
      "prompt": "A staff member is on office Wi-Fi but sees “approved computer required”. What should happen?",
      "options": [
        "Use another employee’s account",
        "Ask an administrator to approve that computer browser",
        "Use a private window to bypass it"
      ],
      "correct_index": 1,
      "explanation": "Office network approval and computer-browser approval are separate."
    },
    {
      "prompt": "What happens when you sign in to Business Manager?",
      "options": [
        "You are automatically clocked in",
        "Eight hours are credited immediately",
        "You can use your authorised areas, but must clock in separately"
      ],
      "correct_index": 2,
      "explanation": "Use the Time clock action to record work."
    },
    {
      "prompt": "Who can approve a discount or apply one to a customer profile?",
      "options": [
        "An administrator",
        "Any person preparing a quote",
        "Any employee on office Wi-Fi"
      ],
      "correct_index": 0,
      "explanation": "Discount approval and customer-profile discounts are administrator actions."
    },
    {
      "prompt": "Mugs are BSD 12.50 each at 24 and BSD 12.00 at 50. Which rate applies to 25?",
      "options": [
        "BSD 12.00",
        "BSD 12.50",
        "An average of the two rates"
      ],
      "correct_index": 1,
      "explanation": "The lower rate starts when the quantity reaches 50."
    },
    {
      "prompt": "A 500-copy brochure run costs BSD 220 before VAT. Which line is correct?",
      "options": [
        "Quantity 500, price BSD 220 each",
        "Quantity 1 Run, price BSD 220, description says 500 copies",
        "Quantity 1, price BSD 0.44 for the whole job"
      ],
      "correct_index": 1,
      "explanation": "Run pricing represents the whole print run."
    },
    {
      "prompt": "Two pieces each measure 24 by 36 inches. What is their combined area?",
      "options": [
        "6 square feet",
        "1,728 square feet",
        "12 square feet"
      ],
      "correct_index": 2,
      "explanation": "One piece is 864 square inches, or 6 square feet. Two pieces are 12 square feet."
    },
    {
      "prompt": "Before finalising a live quote, what should you do?",
      "options": [
        "Review the saved details and PDF, including totals and customer",
        "Assume the first calculation is correct",
        "Remove the VAT so the total is lower"
      ],
      "correct_index": 0,
      "explanation": "Check the saved version before locking it."
    },
    {
      "prompt": "Does finalising an invoice automatically email it?",
      "options": [
        "Yes, always",
        "No; sending uses the separate Email / history workflow",
        "Only when a payment is due"
      ],
      "correct_index": 1,
      "explanation": "Finalising and sending are separate actions."
    },
    {
      "prompt": "Email history says “Accepted by Resend”. What does that prove?",
      "options": [
        "The customer read it",
        "The invoice is paid",
        "The email provider accepted the sending request"
      ],
      "correct_index": 2,
      "explanation": "Provider acceptance is not proof of inbox delivery or reading."
    },
    {
      "prompt": "An email result is uncertain. What is the safest next action?",
      "options": [
        "Keep clicking Send",
        "Check history and ask an administrator to verify the provider before resending",
        "Create three replacement invoices"
      ],
      "correct_index": 1,
      "explanation": "Avoid duplicate customer emails while the outcome is uncertain."
    },
    {
      "prompt": "You discover a payment was entered twice. What should you do?",
      "options": [
        "Ask the authorised person to review and reverse or correct the duplicate",
        "Enter another payment",
        "Change the invoice total to hide the balance"
      ],
      "correct_index": 0,
      "explanation": "Review the original evidence and use the authorised correction workflow."
    },
    {
      "prompt": "When should a job be marked Completed?",
      "options": [
        "As soon as a mockup exists",
        "When someone asks about its status",
        "When the work has actually reached that stage and required checks are satisfied"
      ],
      "correct_index": 2,
      "explanation": "Stages must describe real work and approval state."
    },
    {
      "prompt": "What makes an inch measurement on a mockup dependable?",
      "options": [
        "Typing any reference size",
        "Using a measured reference area and verifying the final production dimensions",
        "Enlarging the photo until it looks right"
      ],
      "correct_index": 1,
      "explanation": "Calibration depends on the measured area and the accuracy of the photograph."
    },
    {
      "prompt": "How should you prepare a left-chest-and-back mockup option?",
      "options": [
        "Reuse a front view and label it Back",
        "Capture only the cheapest placement",
        "Configure and review each placement using the correct surface photo"
      ],
      "correct_index": 2,
      "explanation": "Each surface needs the correct photo, artwork, position and size."
    },
    {
      "prompt": "A catalogue option has left-chest and back views. What price should you review?",
      "options": [
        "One selling price covering the complete combination",
        "Only the left-chest price",
        "A separate invoice total for each picture"
      ],
      "correct_index": 0,
      "explanation": "The combined option has one price for the agreed branding combination."
    },
    {
      "prompt": "An employee clocks in at 8:30 a.m. on a weekday without an approved early start. When does counted work normally begin?",
      "options": [
        "8:30 a.m.",
        "9:00 a.m.",
        "Whenever the employee signs out"
      ],
      "correct_index": 1,
      "explanation": "Unapproved time before the scheduled 9:00 a.m. start does not count."
    },
    {
      "prompt": "An employee starts at 9:30 a.m. with no clocked-out interval. When are eight counted hours reached?",
      "options": [
        "5:00 p.m.",
        "4:30 p.m.",
        "5:30 p.m."
      ],
      "correct_index": 2,
      "explanation": "Eight counted hours are needed for weekday overtime eligibility."
    },
    {
      "prompt": "How does eligible weekend work become time in lieu?",
      "options": [
        "One minute off per counted weekend minute after manager approval",
        "It is automatically available without approval",
        "Only time beyond eight hours can count"
      ],
      "correct_index": 0,
      "explanation": "All counted weekend minutes are eligible, subject to manager approval."
    },
    {
      "prompt": "Where should private NIB, passport or employee-document corrections be handled?",
      "options": [
        "In a customer quote",
        "Privately with HR or an administrator",
        "On the general bulletin board"
      ],
      "correct_index": 1,
      "explanation": "Keep sensitive employee details within the authorised HR workflow."
    },
    {
      "prompt": "What records completion of this training course?",
      "options": [
        "Opening the PDF",
        "Marking only the first lesson read",
        "Reading all lessons, confirming your own participation and passing the final test"
      ],
      "correct_index": 2,
      "explanation": "Completion is linked to the signed-in account and the published course edition."
    }
  ]
}$course127$::jsonb,'published',now()
WHERE NOT EXISTS(SELECT 1 FROM custom_u_production.training_courses_127 WHERE data->>'title'='Operating Custom U Business Manager' AND data->>'edition'='1');
