CREATE OR REPLACE FUNCTION public.custom_u_invoice_terms_113(quote_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE c custom_u_production.crm_records_093%ROWTYPE;BEGIN
 IF NOT custom_u_production.can_102('invoices.create') OR NOT custom_u_production.can_102('invoices.view') THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 SELECT x.* INTO c FROM custom_u_production.crm_records_093 x JOIN custom_u_production.quotes_097 q ON q.customer_id=x.id WHERE q.id=quote_id AND q.status='issued' AND x.kind='customer';
 IF NOT FOUND THEN RETURN jsonb_build_object('error','QUOTE_NOT_FOUND');END IF;
 RETURN jsonb_build_object('payment_terms_days',c.data->'payment_terms_days','customer_version',c.version);
END $function$;

CREATE OR REPLACE FUNCTION public.custom_u_invoices_114(payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$BEGIN RETURN custom_u_production.invoices_rpc_114(payload);EXCEPTION WHEN check_violation THEN IF SQLERRM IN ('ADMIN_DISCOUNT_REQUIRED','DOCUMENT_NUMBER_LOCKED','NUMBERING_EXHAUSTED','ACCESS_DENIED') THEN RETURN jsonb_build_object('error',SQLERRM);ELSE RAISE;END IF;END $function$;

CREATE OR REPLACE FUNCTION custom_u_production.can_102(cap text)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
 SELECT coalesce((custom_u_production.session_access_102()->>'role'='admin') OR (custom_u_production.session_access_102()->'permissions'->cap='true'::jsonb),false);
$function$;

CREATE OR REPLACE FUNCTION custom_u_production.invoices_rpc_098(payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
 SET lock_timeout TO '5s'
AS $function$
DECLARE op text;rid uuid;qid uuid;expected integer;mode boolean;fields jsonb;term text;p integer;n bigint;rows jsonb;
 oldrow custom_u_production.invoices_098%ROWTYPE;saved custom_u_production.invoices_098%ROWTYPE;q custom_u_production.quotes_097%ROWTYPE;
BEGIN
 IF NOT custom_u_production.operation_access_102('invoices',payload) THEN RETURN jsonb_build_object('error','ACCESS_DENIED'); END IF;
 IF jsonb_typeof(payload) IS DISTINCT FROM 'object' OR octet_length(payload::text)>32768 THEN RETURN jsonb_build_object('error','INVALID_REQUEST'); END IF;
 op:=payload->>'op';
 IF op='list' THEN
  term:=coalesce(payload->>'q','');
  IF length(term)>200 OR coalesce(payload->>'page','1') !~ '^[1-9][0-9]{0,5}$' THEN RETURN jsonb_build_object('error','INVALID_REQUEST'); END IF;
  p:=coalesce(payload->>'page','1')::integer;
  SELECT count(*) INTO n FROM custom_u_production.invoices_098 r WHERE strpos(lower(r.number||' '||(r.quote_snapshot->'customer_snapshot'->>'name')||' '||(r.quote_snapshot->'data'->>'title')),lower(term))>0;
  SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]') INTO rows FROM (SELECT r.id,r.number,r.status,r.is_test,r.version,r.quote_snapshot->'customer_snapshot'->>'name' AS customer,r.quote_snapshot->'data'->>'title' AS title,(r.quote_snapshot->'data'->>'total_cents')::bigint AS total_cents,r.details->>'due_date' AS due_date
   FROM custom_u_production.invoices_098 r WHERE strpos(lower(r.number||' '||(r.quote_snapshot->'customer_snapshot'->>'name')||' '||(r.quote_snapshot->'data'->>'title')),lower(term))>0 ORDER BY r.serial DESC LIMIT 50 OFFSET (p-1)*50) t;
  RETURN jsonb_build_object('data',rows,'total',n,'page',p);
 END IF;
 IF coalesce(payload->>'id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN RETURN jsonb_build_object('error','INVALID_ID'); END IF;
 rid:=(payload->>'id')::uuid;
 IF op='get' THEN
  SELECT * INTO oldrow FROM custom_u_production.invoices_098 WHERE id=rid;
  IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND'); END IF;
  RETURN jsonb_build_object('data',to_jsonb(oldrow));
 END IF;
 IF op='create' THEN
  IF (SELECT count(*) FROM jsonb_object_keys(payload))<>6 OR EXISTS(SELECT 1 FROM jsonb_object_keys(payload) x WHERE x NOT IN ('op','id','quote_id','quote_version','is_test','details'))
   OR coalesce(payload->>'quote_id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
   OR jsonb_typeof(payload->'is_test') IS DISTINCT FROM 'boolean' OR jsonb_typeof(payload->'quote_version') IS DISTINCT FROM 'number' OR coalesce(payload->>'quote_version','') !~ '^[1-9][0-9]{0,8}$' THEN RETURN jsonb_build_object('error','INVALID_REQUEST'); END IF;
  qid:=(payload->>'quote_id')::uuid;mode:=(payload->>'is_test')::boolean;
  SELECT * INTO q FROM custom_u_production.quotes_097 WHERE id=qid FOR SHARE;
  IF NOT FOUND THEN RETURN jsonb_build_object('error','QUOTE_NOT_FOUND'); END IF;
  IF q.status<>'issued' THEN RETURN jsonb_build_object('error','FINALISED_QUOTE_REQUIRED'); END IF;
  IF q.version<>(payload->>'quote_version')::integer THEN RETURN jsonb_build_object('error','VERSION_CONFLICT'); END IF;
  fields:=custom_u_production.invoice_details_098(payload->'details',q.data);IF fields ? 'error' THEN RETURN fields; END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(qid::text||mode::text,98));
  SELECT * INTO oldrow FROM custom_u_production.invoices_098 WHERE quote_id=qid AND is_test=mode FOR UPDATE;
  IF FOUND THEN RETURN jsonb_build_object('data',to_jsonb(oldrow),'existing',true); END IF;
  IF EXISTS(SELECT 1 FROM custom_u_production.invoices_098 WHERE id=rid) THEN RETURN jsonb_build_object('error','ID_CONFLICT'); END IF;
  PERFORM pg_advisory_xact_lock(90009802);
  IF (SELECT count(*) FROM custom_u_production.invoices_098)>=5000 THEN RETURN jsonb_build_object('error','INVOICE_LIMIT_REACHED'); END IF;
  INSERT INTO custom_u_production.invoices_098(id,is_test,quote_id,quote_version,quote_snapshot,details,status,version)
   VALUES(rid,mode,qid,q.version,to_jsonb(q),fields,'draft',1) RETURNING * INTO saved;
 ELSE
  IF coalesce(op,'') NOT IN ('save','issue') OR jsonb_typeof(payload->'version') IS DISTINCT FROM 'number' OR coalesce(payload->>'version','') !~ '^[1-9][0-9]{0,8}$'
   OR EXISTS(SELECT 1 FROM jsonb_object_keys(payload) x WHERE x NOT IN ('op','id','version',CASE WHEN op='save' THEN 'details' ELSE 'confirm' END)) THEN RETURN jsonb_build_object('error','INVALID_REQUEST'); END IF;
  expected:=(payload->>'version')::integer;
  SELECT * INTO oldrow FROM custom_u_production.invoices_098 WHERE id=rid FOR UPDATE;
  IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND'); END IF;
  IF op='save' AND oldrow.quote_id IS NULL THEN RETURN jsonb_build_object('error','DIRECT_INVOICE_EDITOR_REQUIRED');END IF;
  IF op='issue' THEN
   IF payload->'confirm' IS DISTINCT FROM 'true'::jsonb THEN RETURN jsonb_build_object('error','CONFIRM_REQUIRED'); END IF;
   IF oldrow.status='issued' AND oldrow.version IN (expected,expected+1) THEN RETURN jsonb_build_object('data',to_jsonb(oldrow)); END IF;
   IF oldrow.status<>'draft' THEN RETURN jsonb_build_object('error','INVOICE_LOCKED'); END IF;
   IF oldrow.version<>expected THEN RETURN jsonb_build_object('error','VERSION_CONFLICT'); END IF;
   IF btrim(coalesce(oldrow.quote_snapshot->'seller_snapshot'->>'tax_id',''))='' THEN RETURN jsonb_build_object('error','SUPPLIER_TAX_ID_REQUIRED'); END IF;
   IF oldrow.details->>'document_type'='vat_invoice' AND (oldrow.details->>'billing_address'='' OR oldrow.details->>'billing_tax_id'='') THEN RETURN jsonb_build_object('error','RECIPIENT_TAX_DETAILS_REQUIRED'); END IF;
   IF EXISTS(SELECT 1 FROM jsonb_array_elements_text(oldrow.details->'tax_codes') x WHERE x='') THEN RETURN jsonb_build_object('error','TAX_CLASSIFICATION_REQUIRED'); END IF;
   UPDATE custom_u_production.invoices_098 SET status='issued',version=version+1,updated_at=now() WHERE id=rid RETURNING * INTO saved;
  ELSE
   IF oldrow.status<>'draft' THEN RETURN jsonb_build_object('error','INVOICE_LOCKED'); END IF;
   fields:=custom_u_production.invoice_details_098(payload->'details',oldrow.quote_snapshot->'data');IF fields ? 'error' THEN RETURN fields; END IF;
   IF oldrow.details=fields AND oldrow.version IN (expected,expected+1) THEN RETURN jsonb_build_object('data',to_jsonb(oldrow)); END IF;
   IF oldrow.version<>expected THEN RETURN jsonb_build_object('error','VERSION_CONFLICT'); END IF;
   UPDATE custom_u_production.invoices_098 SET details=fields,version=version+1,updated_at=now() WHERE id=rid RETURNING * INTO saved;
  END IF;
 END IF;
 INSERT INTO custom_u_production.invoice_audit_098(invoice_id,actor_id,before_record,after_record)
 VALUES(saved.id,auth.uid(),CASE WHEN oldrow.id IS NULL THEN NULL ELSE to_jsonb(oldrow) END,to_jsonb(saved));
 RETURN jsonb_build_object('data',to_jsonb(saved),'existing',false);
END $function$;

CREATE OR REPLACE FUNCTION custom_u_production.invoices_rpc_114(payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
 SET lock_timeout TO '5s'
AS $function$
DECLARE op text:=payload->>'op';rid uuid;cid uuid;pid uuid;mode boolean;expected int;data jsonb;fields jsonb;snapshot jsonb;
 oldrow custom_u_production.invoices_098%ROWTYPE;saved custom_u_production.invoices_098%ROWTYPE;
 customer custom_u_production.crm_records_093%ROWTYPE;contact custom_u_production.crm_records_093%ROWTYPE;profile custom_u_production.quote_profile_097%ROWTYPE;
BEGIN
 IF op NOT IN ('create_direct','save_direct') OR op IS NULL THEN RETURN custom_u_production.invoices_rpc_098(payload);END IF;
 IF NOT custom_u_production.operation_access_102('invoices',jsonb_build_object('op','get')) OR NOT custom_u_production.can_102(CASE WHEN op='create_direct' THEN 'invoices.create' ELSE 'invoices.edit' END) THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 IF jsonb_typeof(payload) IS DISTINCT FROM 'object' OR octet_length(payload::text)>262144 OR (SELECT count(*) FROM jsonb_object_keys(payload))<>7
 OR EXISTS(SELECT 1 FROM jsonb_object_keys(payload) k WHERE k NOT IN ('op','id','customer_id','contact_id','data','details',CASE WHEN op='create_direct' THEN 'is_test' ELSE 'version' END))
 OR coalesce(payload->>'id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
 OR coalesce(payload->>'customer_id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
 OR NOT (payload ? 'contact_id') OR (payload->'contact_id'<>'null'::jsonb AND coalesce(payload->>'contact_id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$') THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
 IF op='create_direct' AND jsonb_typeof(payload->'is_test') IS DISTINCT FROM 'boolean' OR op='save_direct' AND (jsonb_typeof(payload->'version') IS DISTINCT FROM 'number' OR coalesce(payload->>'version','') !~ '^[1-9][0-9]{0,8}$') THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
 IF jsonb_typeof(payload->'data') IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(payload->'data'))<>2 OR NOT (payload->'data' ?& ARRAY['title','lines']) THEN RETURN jsonb_build_object('error','INVALID_INVOICE_ITEMS');END IF;
 rid:=(payload->>'id')::uuid;cid:=(payload->>'customer_id')::uuid;pid:=(payload->>'contact_id')::uuid;
 data:=custom_u_production.quote_data_097((payload->'data')||jsonb_build_object('currency','BSD','quote_date',payload->'details'->'invoice_date','valid_until',payload->'details'->'due_date','deposit_percent','0','terms',payload->'details'->'terms','notes',payload->'details'->'notes'));
 IF data ? 'error' THEN RETURN data;END IF;
 fields:=custom_u_production.invoice_details_098(payload->'details',data);IF fields ? 'error' THEN RETURN fields;END IF;
 SELECT * INTO customer FROM custom_u_production.crm_records_093 WHERE id=cid AND kind='customer' AND active FOR SHARE;
 IF NOT FOUND THEN RETURN jsonb_build_object('error','CUSTOMER_INACTIVE');END IF;
 IF pid IS NOT NULL THEN
  SELECT * INTO contact FROM custom_u_production.crm_records_093 WHERE id=pid AND kind='contact' AND customer_id=cid AND active FOR SHARE;
  IF NOT FOUND THEN RETURN jsonb_build_object('error','CONTACT_INVALID');END IF;
 END IF;
 SELECT * INTO profile FROM custom_u_production.quote_profile_097 WHERE id='business' FOR SHARE;
 IF NOT FOUND THEN RETURN jsonb_build_object('error','BUSINESS_PROFILE_REQUIRED');END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(rid::text,114));
 SELECT * INTO oldrow FROM custom_u_production.invoices_098 WHERE id=rid FOR UPDATE;
 IF oldrow.id IS NOT NULL AND oldrow.quote_id IS NOT NULL THEN RETURN jsonb_build_object('error','INVOICE_SOURCE_CONFLICT');END IF;
 snapshot:=jsonb_build_object('source','direct','customer_id',cid,'contact_id',pid,'customer_snapshot',customer.data,'customer_version',customer.version,'contact_snapshot',contact.data,'contact_version',contact.version,'seller_snapshot',profile.data,'seller_version',profile.version,'data',data);
 IF oldrow.id IS NOT NULL THEN
  snapshot:=snapshot||jsonb_build_object('seller_snapshot',oldrow.quote_snapshot->'seller_snapshot','seller_version',oldrow.quote_snapshot->'seller_version');
  IF oldrow.quote_snapshot->>'customer_id'=cid::text THEN snapshot:=snapshot||jsonb_build_object('customer_snapshot',oldrow.quote_snapshot->'customer_snapshot','customer_version',oldrow.quote_snapshot->'customer_version');END IF;
  IF oldrow.quote_snapshot->>'customer_id'=cid::text AND oldrow.quote_snapshot->>'contact_id' IS NOT DISTINCT FROM pid::text THEN snapshot:=snapshot||jsonb_build_object('contact_snapshot',oldrow.quote_snapshot->'contact_snapshot','contact_version',oldrow.quote_snapshot->'contact_version');END IF;
 END IF;
 IF op='create_direct' THEN
  mode:=(payload->>'is_test')::boolean;
  IF oldrow.id IS NOT NULL THEN
   IF oldrow.is_test=mode AND oldrow.quote_snapshot=snapshot AND oldrow.details=fields THEN RETURN jsonb_build_object('data',to_jsonb(oldrow),'existing',true);END IF;
   RETURN jsonb_build_object('error','ID_CONFLICT');
  END IF;
  PERFORM pg_advisory_xact_lock(90009802);
  IF (SELECT count(*) FROM custom_u_production.invoices_098)>=5000 THEN RETURN jsonb_build_object('error','INVOICE_LIMIT_REACHED');END IF;
  INSERT INTO custom_u_production.invoices_098(id,is_test,quote_id,quote_version,quote_snapshot,details,status,version) VALUES(rid,mode,NULL,NULL,snapshot,fields,'draft',1) RETURNING * INTO saved;
 ELSE
  IF oldrow.id IS NULL THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;
  IF oldrow.status<>'draft' THEN RETURN jsonb_build_object('error','INVOICE_LOCKED');END IF;
  expected:=(payload->>'version')::int;
  IF oldrow.quote_snapshot=snapshot AND oldrow.details=fields AND oldrow.version IN (expected,expected+1) THEN RETURN jsonb_build_object('data',to_jsonb(oldrow),'existing',true);END IF;
  IF oldrow.version<>expected THEN RETURN jsonb_build_object('error','VERSION_CONFLICT');END IF;
  UPDATE custom_u_production.invoices_098 SET quote_snapshot=snapshot,details=fields,version=version+1,updated_at=now() WHERE id=rid RETURNING * INTO saved;
 END IF;
 INSERT INTO custom_u_production.invoice_audit_098(invoice_id,actor_id,before_record,after_record) VALUES(saved.id,auth.uid(),CASE WHEN oldrow.id IS NULL THEN NULL ELSE to_jsonb(oldrow) END,to_jsonb(saved));
 RETURN jsonb_build_object('data',to_jsonb(saved),'existing',false);
END $function$;

CREATE OR REPLACE FUNCTION custom_u_production.quotes_rpc_097(payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
 SET lock_timeout TO '5s'
AS $function$
<<quote_vars>>
DECLARE op text; expected integer; rid uuid; cid uuid; pid uuid; oldjson jsonb; data jsonb; k text; v text; p integer; term text; rows jsonb; n bigint;
 oldq custom_u_production.quotes_097%ROWTYPE; savedq custom_u_production.quotes_097%ROWTYPE;
 oldp custom_u_production.quote_profile_097%ROWTYPE; savedp custom_u_production.quote_profile_097%ROWTYPE;
 customer custom_u_production.crm_records_093%ROWTYPE; contact custom_u_production.crm_records_093%ROWTYPE;
 cs jsonb; ps jsonb; ss jsonb;
BEGIN
 IF NOT custom_u_production.operation_access_102('quotes',payload) THEN RETURN jsonb_build_object('error','ACCESS_DENIED'); END IF;
 IF jsonb_typeof(payload) IS DISTINCT FROM 'object' OR octet_length(payload::text)>262144 THEN RETURN jsonb_build_object('error','INVALID_REQUEST'); END IF;
 op:=payload->>'op';
 IF op='profile' THEN RETURN jsonb_build_object('data',(SELECT to_jsonb(r) FROM custom_u_production.quote_profile_097 r WHERE id='business')); END IF;
 IF op='save_profile' THEN
  IF EXISTS(SELECT 1 FROM jsonb_object_keys(payload) x WHERE x NOT IN ('op','version','data')) OR jsonb_typeof(payload->'version') IS DISTINCT FROM 'number' OR coalesce(payload->>'version','') !~ '^[0-9]{1,9}$' THEN RETURN jsonb_build_object('error','INVALID_REQUEST'); END IF;
  data:=payload->'data';expected:=(payload->>'version')::integer;
  IF jsonb_typeof(data) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('error','INVALID_PROFILE'); END IF;
  IF (SELECT count(*) FROM jsonb_object_keys(data))<>11 OR EXISTS(SELECT 1 FROM jsonb_object_keys(data) x WHERE x NOT IN ('name','address','email','phone','tax_id','website','quote_terms','default_vat_rate','default_deposit_percent','validity_days','currency')) THEN RETURN jsonb_build_object('error','INVALID_PROFILE'); END IF;
  FOREACH k IN ARRAY ARRAY['name','address','email','phone','tax_id','website','quote_terms','currency'] LOOP
   IF NOT custom_u_production.quote_text_097(data->k,CASE WHEN k='quote_terms' THEN 2000 WHEN k='address' THEN 500 ELSE 254 END,k IN ('address','quote_terms')) THEN RETURN jsonb_build_object('error','INVALID_PROFILE'); END IF;
   data:=jsonb_set(data,ARRAY[k],to_jsonb(btrim(data->>k)));
  END LOOP;
  IF coalesce(length(data->>'name'),0) NOT BETWEEN 1 AND 160 OR length(data->>'address')=0 OR data->>'currency'<>'BSD'
  OR (data->>'email') !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' THEN RETURN jsonb_build_object('error','INVALID_PROFILE'); END IF;
  FOREACH k IN ARRAY ARRAY['default_vat_rate','default_deposit_percent'] LOOP
   IF jsonb_typeof(data->k) IS DISTINCT FROM 'string' OR (data->>k) !~ '^[0-9]{1,3}(\.[0-9]{1,2})?$' THEN RETURN jsonb_build_object('error','INVALID_PROFILE'); END IF;
   IF (data->>k)::numeric>100 THEN RETURN jsonb_build_object('error','INVALID_PROFILE'); END IF;
   data:=jsonb_set(data,ARRAY[k],to_jsonb(to_char((data->>k)::numeric,'FM990.00')));
  END LOOP;
  IF jsonb_typeof(data->'validity_days') IS DISTINCT FROM 'number' OR coalesce(data->>'validity_days','') !~ '^[0-9]{1,3}$' THEN RETURN jsonb_build_object('error','INVALID_PROFILE'); END IF;
  IF (data->>'validity_days')::integer>366 THEN RETURN jsonb_build_object('error','INVALID_PROFILE'); END IF;
  PERFORM pg_advisory_xact_lock(90009701);
  SELECT * INTO oldp FROM custom_u_production.quote_profile_097 WHERE id='business' FOR UPDATE;
  IF FOUND THEN
   IF oldp.data=data AND oldp.version IN (expected,expected+1) THEN RETURN jsonb_build_object('data',to_jsonb(oldp)); END IF;
   IF oldp.version<>expected THEN RETURN jsonb_build_object('error','VERSION_CONFLICT'); END IF;
   oldjson:=to_jsonb(oldp);
   UPDATE custom_u_production.quote_profile_097 SET data=quote_vars.data,version=version+1,updated_at=now() WHERE id='business' RETURNING * INTO savedp;
  ELSE
   IF expected<>0 THEN RETURN jsonb_build_object('error','VERSION_CONFLICT'); END IF;
   INSERT INTO custom_u_production.quote_profile_097(id,data,version) VALUES('business',data,1) RETURNING * INTO savedp;
  END IF;
  INSERT INTO custom_u_production.quote_audit_097(entity,entity_id,actor_id,before_record,after_record) VALUES('profile','business',auth.uid(),oldjson,to_jsonb(savedp));
  RETURN jsonb_build_object('data',to_jsonb(savedp));
 END IF;
 IF op='list' THEN
  term:=coalesce(payload->>'q','');
  IF length(term)>200 OR coalesce(payload->>'page','1') !~ '^[1-9][0-9]{0,5}$' THEN RETURN jsonb_build_object('error','INVALID_REQUEST'); END IF;
  p:=coalesce(payload->>'page','1')::integer;
  SELECT count(*) INTO n FROM custom_u_production.quotes_097 r WHERE strpos(lower(r.number||' '||(r.customer_snapshot->>'name')||' '||(r.data->>'title')),lower(term))>0;
  SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]') INTO rows FROM (SELECT r.id,r.number,r.status,r.version,r.customer_snapshot->>'name' AS customer,r.data->>'title' AS title,(r.data->>'total_cents')::bigint AS total_cents,r.data->>'valid_until' AS valid_until
   FROM custom_u_production.quotes_097 r WHERE strpos(lower(r.number||' '||(r.customer_snapshot->>'name')||' '||(r.data->>'title')),lower(term))>0 ORDER BY r.serial DESC LIMIT 50 OFFSET (p-1)*50) t;
  RETURN jsonb_build_object('data',rows,'total',n,'page',p);
 END IF;
 IF coalesce(payload->>'id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN RETURN jsonb_build_object('error','INVALID_ID'); END IF;
 rid:=(payload->>'id')::uuid;
 IF op='get' THEN
  SELECT * INTO oldq FROM custom_u_production.quotes_097 WHERE id=rid;
  IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND'); END IF;
  RETURN jsonb_build_object('data',to_jsonb(oldq));
 END IF;
 IF coalesce(op,'') NOT IN ('save','issue') OR jsonb_typeof(payload->'version') IS DISTINCT FROM 'number' OR coalesce(payload->>'version','') !~ '^[0-9]{1,9}$' THEN RETURN jsonb_build_object('error','INVALID_REQUEST'); END IF;
 expected:=(payload->>'version')::integer;
 IF op='issue' THEN
  IF EXISTS(SELECT 1 FROM jsonb_object_keys(payload) x WHERE x NOT IN ('op','id','version')) THEN RETURN jsonb_build_object('error','INVALID_REQUEST'); END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(rid::text,97));
  SELECT * INTO oldq FROM custom_u_production.quotes_097 WHERE id=rid FOR UPDATE;
  IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND'); END IF;
  IF oldq.status='issued' AND oldq.version IN (expected,expected+1) THEN RETURN jsonb_build_object('data',to_jsonb(oldq)); END IF;
  IF oldq.version<>expected THEN RETURN jsonb_build_object('error','VERSION_CONFLICT'); END IF;
  IF oldq.status<>'draft' THEN RETURN jsonb_build_object('error','QUOTE_LOCKED'); END IF;
  IF (oldq.data->>'tax_cents')::bigint>0 AND btrim(coalesce(oldq.seller_snapshot->>'tax_id',''))='' THEN RETURN jsonb_build_object('error','TAX_ID_REQUIRED'); END IF;
  UPDATE custom_u_production.quotes_097 SET status='issued',version=version+1,updated_at=now() WHERE id=rid RETURNING * INTO savedq;
 ELSE
  IF EXISTS(SELECT 1 FROM jsonb_object_keys(payload) x WHERE x NOT IN ('op','id','version','customer_id','contact_id','data')) THEN RETURN jsonb_build_object('error','INVALID_REQUEST'); END IF;
  IF coalesce(payload->>'customer_id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
   OR (payload->>'contact_id' IS NOT NULL AND (payload->>'contact_id') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$') THEN RETURN jsonb_build_object('error','INVALID_CUSTOMER'); END IF;
  cid:=(payload->>'customer_id')::uuid;pid:=(payload->>'contact_id')::uuid;
  data:=custom_u_production.quote_data_097(payload->'data');IF data ? 'error' THEN RETURN data; END IF;
  -- Match CRM's parent-before-contact lock order. A selected active parent is required.
  SELECT * INTO customer FROM custom_u_production.crm_records_093 WHERE id=cid AND kind='customer' AND active FOR SHARE;
  IF NOT FOUND THEN RETURN jsonb_build_object('error','CUSTOMER_INACTIVE'); END IF;
  IF pid IS NOT NULL THEN
   SELECT * INTO contact FROM custom_u_production.crm_records_093 WHERE id=pid AND kind='contact' AND customer_id=cid AND active FOR SHARE;
   IF NOT FOUND THEN RETURN jsonb_build_object('error','CONTACT_INVALID'); END IF;
  END IF;
  SELECT r.data INTO ss FROM custom_u_production.quote_profile_097 r WHERE id='business' FOR SHARE;
  IF NOT FOUND THEN RETURN jsonb_build_object('error','BUSINESS_PROFILE_REQUIRED'); END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(rid::text,97));
  SELECT * INTO oldq FROM custom_u_production.quotes_097 WHERE id=rid FOR UPDATE;
  IF FOUND THEN
   IF oldq.status<>'draft' THEN RETURN jsonb_build_object('error','QUOTE_LOCKED'); END IF;
   IF oldq.data=data AND oldq.customer_id=cid AND oldq.contact_id IS NOT DISTINCT FROM pid AND oldq.version IN (expected,expected+1) THEN RETURN jsonb_build_object('data',to_jsonb(oldq)); END IF;
   IF NOT custom_u_production.can_102('quotes.edit') THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
   IF oldq.version<>expected THEN RETURN jsonb_build_object('error','VERSION_CONFLICT'); END IF;
   cs:=CASE WHEN oldq.customer_id=cid THEN oldq.customer_snapshot ELSE customer.data END;
   ps:=CASE WHEN oldq.contact_id IS NOT DISTINCT FROM pid THEN oldq.contact_snapshot ELSE contact.data END;
   UPDATE custom_u_production.quotes_097 SET data=quote_vars.data,customer_id=cid,contact_id=pid,customer_snapshot=cs,contact_snapshot=ps,version=version+1,updated_at=now() WHERE id=rid RETURNING * INTO savedq;
  ELSE
   IF expected<>0 THEN RETURN jsonb_build_object('error','NOT_FOUND'); END IF;
   PERFORM pg_advisory_xact_lock(90009702);
   IF (SELECT count(*) FROM custom_u_production.quotes_097)>=5000 THEN RETURN jsonb_build_object('error','QUOTE_LIMIT_REACHED'); END IF;
   IF NOT custom_u_production.can_102('quotes.create') THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
   INSERT INTO custom_u_production.quotes_097(id,status,version,customer_id,contact_id,customer_snapshot,contact_snapshot,seller_snapshot,data)
    VALUES(rid,'draft',1,cid,pid,customer.data,contact.data,ss,data) RETURNING * INTO savedq;
  END IF;
 END IF;
 INSERT INTO custom_u_production.quote_audit_097(entity,entity_id,actor_id,before_record,after_record) VALUES('quote',rid::text,auth.uid(),CASE WHEN oldq.id IS NULL THEN NULL ELSE to_jsonb(oldq) END,to_jsonb(savedq));
 RETURN jsonb_build_object('data',to_jsonb(savedq));
END $function$;



CREATE OR REPLACE FUNCTION public.custom_u_quotes_097(payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$BEGIN RETURN custom_u_production.quotes_rpc_097(payload);EXCEPTION WHEN check_violation THEN IF SQLERRM IN ('ADMIN_DISCOUNT_REQUIRED','DOCUMENT_NUMBER_LOCKED','NUMBERING_EXHAUSTED','ACCESS_DENIED') THEN RETURN jsonb_build_object('error',SQLERRM);ELSE RAISE;END IF;END $function$;

CREATE OR REPLACE FUNCTION custom_u_production.discount_guard_118()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE me jsonb;lines jsonb;oldlines jsonb;cid uuid;oldcid uuid;rate numeric:=0;BEGIN
 me:=custom_u_production.session_access_102();
 IF me IS NULL THEN RAISE EXCEPTION 'ACCESS_DENIED' USING ERRCODE='23514';END IF;
 IF me->>'role'='admin' THEN RETURN NEW;END IF;
 IF TG_TABLE_NAME='quotes_097' THEN
  lines:=NEW.data->'lines';cid:=NEW.customer_id;
  IF TG_OP='UPDATE' THEN oldlines:=OLD.data->'lines';oldcid:=OLD.customer_id;END IF;
 ELSE
  lines:=NEW.quote_snapshot->'data'->'lines';cid:=(NEW.quote_snapshot->>'customer_id')::uuid;
  IF TG_OP='UPDATE' THEN oldlines:=OLD.quote_snapshot->'data'->'lines';oldcid:=(OLD.quote_snapshot->>'customer_id')::uuid;END IF;
  IF TG_OP='INSERT' AND NEW.quote_id IS NOT NULL AND EXISTS(SELECT 1 FROM custom_u_production.quotes_097 q WHERE q.id=NEW.quote_id AND q.status='issued' AND to_jsonb(q)=NEW.quote_snapshot) THEN RETURN NEW;END IF;
 END IF;
 IF lines=oldlines AND cid=oldcid THEN RETURN NEW;END IF;
 SELECT coalesce((data->>'percent')::numeric,0) INTO rate FROM custom_u_production.controls_118 WHERE key='discount:'||cid::text FOR SHARE;
 rate:=coalesce(rate,0);
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(lines) l WHERE (l->>'discount_percent')::numeric<>0 AND (l->>'discount_percent')::numeric<>rate) THEN RAISE EXCEPTION 'ADMIN_DISCOUNT_REQUIRED' USING ERRCODE='23514';END IF;
 RETURN NEW;
END $function$;

CREATE OR REPLACE FUNCTION custom_u_production.document_number_118()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE cfg jsonb;field text;n bigint;BEGIN
 IF TG_OP='UPDATE' THEN
  IF NEW.number IS DISTINCT FROM OLD.number OR NEW.serial IS DISTINCT FROM OLD.serial THEN RAISE EXCEPTION 'DOCUMENT_NUMBER_LOCKED' USING ERRCODE='23514';END IF;
  RETURN NEW;
 END IF;
 IF TG_TABLE_NAME='invoices_098' THEN
  IF NEW.is_test THEN NEW.number:='CU-TEST-I-'||lpad(NEW.serial::text,8,'0');RETURN NEW;END IF;
 END IF;
 field:=CASE TG_TABLE_NAME WHEN 'quotes_097' THEN 'quote_next' ELSE 'invoice_next' END;
 SELECT data INTO cfg FROM custom_u_production.controls_118 WHERE key='numbering' FOR UPDATE;
 n:=(cfg->>field)::bigint;
 IF n NOT BETWEEN 1 AND 99999999 THEN RAISE EXCEPTION 'NUMBERING_EXHAUSTED' USING ERRCODE='23514';END IF;
 NEW.number:=n::text;
 PERFORM custom_u_production.control_put_118('numbering','numbering',jsonb_set(cfg,ARRAY[field],to_jsonb(n+1)));
 RETURN NEW;
END $function$;

CREATE OR REPLACE FUNCTION custom_u_production.invoice_details_098(d jsonb, q jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 IMMUTABLE
 SET search_path TO ''
AS $function$
DECLARE starts date;due date;supply date;k text;code text;i integer;
BEGIN
 IF jsonb_typeof(d) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('error','INVALID_INVOICE'); END IF;
 IF (SELECT count(*) FROM jsonb_object_keys(d))<>9 OR EXISTS(SELECT 1 FROM jsonb_object_keys(d) x WHERE x NOT IN ('invoice_date','due_date','supply_date','document_type','billing_address','billing_tax_id','notes','terms','tax_codes')) THEN RETURN jsonb_build_object('error','INVALID_INVOICE'); END IF;
 IF coalesce(d->>'document_type','') NOT IN ('vat_invoice','vat_sales_receipt') THEN RETURN jsonb_build_object('error','DOCUMENT_TYPE_REQUIRED'); END IF;
 FOREACH k IN ARRAY ARRAY['invoice_date','due_date'] LOOP
  IF jsonb_typeof(d->k) IS DISTINCT FROM 'string' OR (d->>k) !~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$' THEN RETURN jsonb_build_object('error','INVALID_DATES'); END IF;
 END LOOP;
 IF jsonb_typeof(d->'supply_date') IS DISTINCT FROM 'string' OR ((d->>'supply_date')<>'' AND (d->>'supply_date') !~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$') THEN RETURN jsonb_build_object('error','INVALID_DATES'); END IF;
 BEGIN
  starts:=(d->>'invoice_date')::date;due:=(d->>'due_date')::date;supply:=nullif(d->>'supply_date','')::date;
 EXCEPTION WHEN OTHERS THEN RETURN jsonb_build_object('error','INVALID_DATES'); END;
 IF due<starts OR due>starts+366 OR supply>starts THEN RETURN jsonb_build_object('error','INVALID_DATES'); END IF;
 FOREACH k IN ARRAY ARRAY['billing_address','billing_tax_id','notes','terms'] LOOP
  IF NOT custom_u_production.quote_text_097(d->k,CASE WHEN k='billing_address' THEN 500 WHEN k='billing_tax_id' THEN 100 ELSE 2000 END,k<>'billing_tax_id') THEN RETURN jsonb_build_object('error','INVALID_INVOICE'); END IF;
  d:=jsonb_set(d,ARRAY[k],to_jsonb(btrim(d->>k)));
 END LOOP;
 IF jsonb_typeof(d->'tax_codes') IS DISTINCT FROM 'array' THEN RETURN jsonb_build_object('error','INVALID_TAX_CODES'); END IF;
 IF jsonb_array_length(d->'tax_codes')<>jsonb_array_length(q->'lines') THEN RETURN jsonb_build_object('error','INVALID_TAX_CODES'); END IF;
 FOR i IN 0..jsonb_array_length(q->'lines')-1 LOOP
  code:=d->'tax_codes'->>i;
  IF jsonb_typeof(d->'tax_codes'->i) IS DISTINCT FROM 'string' OR code NOT IN ('','T','Z','E') THEN RETURN jsonb_build_object('error','INVALID_TAX_CODES'); END IF;
  IF (((q->'lines'->i->>'vat_rate')::numeric>0) IS DISTINCT FROM (code='T')) THEN RETURN jsonb_build_object('error','INVALID_TAX_CODES'); END IF;
 END LOOP;
 RETURN d;
END $function$;



CREATE OR REPLACE FUNCTION custom_u_production.operation_access_102(area text, p jsonb)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE op text:=p->>'op';cap text;
BEGIN
 PERFORM 1 FROM custom_u_production.staff_members WHERE user_id=auth.uid() FOR SHARE;
 PERFORM 1 FROM custom_u_production.staff_access_102 WHERE user_id=auth.uid() FOR SHARE;
 IF custom_u_production.session_access_102() IS NULL THEN RETURN false;END IF;
 IF custom_u_production.history_access_091() IS NOT NULL THEN RETURN true;END IF;
 IF NOT custom_u_production.can_102(area||'.view') THEN RETURN false;END IF;
 IF area='customers' THEN
  IF op IN ('list','get') THEN RETURN true;END IF;
  RETURN op IN ('save_customer','save_contact') AND (custom_u_production.can_102('customers.create') OR custom_u_production.can_102('customers.edit'));
 ELSIF area='quotes' THEN
  IF op IN ('list','get','profile') THEN RETURN true;END IF;
  IF op='issue' THEN RETURN custom_u_production.can_102('quotes.approve');END IF;
  RETURN op='save' AND custom_u_production.can_102('customers.view') AND (custom_u_production.can_102('quotes.create') OR custom_u_production.can_102('quotes.edit'));
 ELSIF area='invoices' THEN
  IF op IN ('list','get') THEN RETURN true;END IF;
  cap:=CASE op WHEN 'create' THEN 'invoices.create' WHEN 'save' THEN 'invoices.edit' WHEN 'issue' THEN 'invoices.issue' ELSE NULL END;
  RETURN custom_u_production.can_102(cap) AND (op<>'create' OR custom_u_production.can_102('quotes.view'));
 ELSIF area='payments' THEN
  IF NOT custom_u_production.can_102('invoices.view') THEN RETURN false;END IF;
  IF op IN ('list','invoice','receipt') THEN RETURN true;END IF;
  RETURN custom_u_production.can_102(CASE op WHEN 'record' THEN 'payments.record' WHEN 'reverse' THEN 'payments.reverse' ELSE NULL END);
 END IF;
 RETURN false;
END $function$;

CREATE OR REPLACE FUNCTION custom_u_production.permission_keys_102()
 RETURNS text[]
 LANGUAGE sql
 IMMUTABLE
 SET search_path TO ''
AS $function$
 SELECT ARRAY['customers.view','customers.create','customers.edit','quotes.view','quotes.create','quotes.edit','quotes.approve','quotes.send','invoices.view','invoices.create','invoices.edit','invoices.issue','invoices.send','payments.view','payments.record','payments.reverse','jobs.view','jobs.create','jobs.edit','jobs.progress','artwork.view','artwork.upload','artwork.approve','products.view','products.create','products.edit','products.send']::text[];
$function$;

CREATE OR REPLACE FUNCTION custom_u_production.quote_data_097(d jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 IMMUTABLE
 SET search_path TO ''
AS $function$
DECLARE l jsonb; rows jsonb:='[]'; q numeric; price numeric; discount numeric; vat numeric;
 gross bigint; disc bigint; net bigint; tax bigint; subtotal bigint:=0; discounts bigint:=0; taxes bigint:=0; total bigint;
 dep numeric; starts date; expires date; k text;
BEGIN
 IF jsonb_typeof(d) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('error','INVALID_QUOTE'); END IF;
 IF (SELECT count(*) FROM jsonb_object_keys(d))<>8 OR EXISTS(SELECT 1 FROM jsonb_object_keys(d) x WHERE x NOT IN ('title','quote_date','valid_until','lines','terms','notes','deposit_percent','currency')) OR (d->>'currency') IS DISTINCT FROM 'BSD' THEN RETURN jsonb_build_object('error','INVALID_QUOTE'); END IF;
 IF NOT custom_u_production.quote_text_097(d->'title',160) OR length(btrim(d->>'title'))=0
 OR NOT custom_u_production.quote_text_097(d->'terms',2000,true) OR NOT custom_u_production.quote_text_097(d->'notes',2000,true)
 OR coalesce(d->>'quote_date','') !~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$' OR coalesce(d->>'valid_until','') !~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$'
 OR jsonb_typeof(d->'deposit_percent') IS DISTINCT FROM 'string' OR (d->>'deposit_percent') !~ '^[0-9]{1,3}(\.[0-9]{1,2})?$' THEN RETURN jsonb_build_object('error','INVALID_QUOTE'); END IF;
 BEGIN starts:=(d->>'quote_date')::date;expires:=(d->>'valid_until')::date;EXCEPTION WHEN OTHERS THEN RETURN jsonb_build_object('error','INVALID_DATES'); END;
 dep:=(d->>'deposit_percent')::numeric;
 IF expires<starts OR expires>starts+366 OR dep>100 THEN RETURN jsonb_build_object('error','INVALID_QUOTE'); END IF;
 IF jsonb_typeof(d->'lines') IS DISTINCT FROM 'array' THEN RETURN jsonb_build_object('error','INVALID_LINES'); END IF;
 IF jsonb_array_length(d->'lines') NOT BETWEEN 1 AND 100 THEN RETURN jsonb_build_object('error','INVALID_LINES'); END IF;
 FOR l IN SELECT value FROM jsonb_array_elements(d->'lines') LOOP
  IF jsonb_typeof(l) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('error','INVALID_LINES'); END IF;
  IF (SELECT count(*) FROM jsonb_object_keys(l))<>8 OR EXISTS(SELECT 1 FROM jsonb_object_keys(l) x WHERE x NOT IN ('description','finish','placement','unit','quantity','unit_price','discount_percent','vat_rate')) THEN RETURN jsonb_build_object('error','INVALID_LINES'); END IF;
  IF NOT custom_u_production.quote_text_097(l->'description',1000,true) OR length(btrim(l->>'description'))=0
  OR NOT custom_u_production.quote_text_097(l->'finish',160) OR NOT custom_u_production.quote_text_097(l->'placement',160)
  OR NOT custom_u_production.quote_text_097(l->'unit',20) OR length(btrim(l->>'unit'))=0 THEN RETURN jsonb_build_object('error','INVALID_LINES'); END IF;
  FOREACH k IN ARRAY ARRAY['quantity','unit_price','discount_percent','vat_rate'] LOOP
   IF jsonb_typeof(l->k) IS DISTINCT FROM 'string' OR (l->>k) !~ (CASE WHEN k='quantity' THEN '^[0-9]{1,7}(\.[0-9]{1,3})?$' ELSE '^[0-9]{1,7}(\.[0-9]{1,2})?$' END) THEN RETURN jsonb_build_object('error','INVALID_LINES'); END IF;
  END LOOP;
  q:=(l->>'quantity')::numeric;price:=(l->>'unit_price')::numeric;discount:=(l->>'discount_percent')::numeric;vat:=(l->>'vat_rate')::numeric;
  IF q<=0 OR q>1000000 OR price>1000000 OR discount>100 OR vat>100 THEN RETURN jsonb_build_object('error','INVALID_LINES'); END IF;
  gross:=round(q*price*100);disc:=round(gross*discount/100);net:=gross-disc;tax:=round(net*vat/100);
  subtotal:=subtotal+gross;discounts:=discounts+disc;taxes:=taxes+tax;
  IF subtotal+taxes>100000000000 THEN RETURN jsonb_build_object('error','QUOTE_TOO_LARGE'); END IF;
  rows:=rows||jsonb_build_array(jsonb_build_object('description',btrim(l->>'description'),'finish',btrim(l->>'finish'),'placement',btrim(l->>'placement'),'unit',btrim(l->>'unit'),
   'quantity',to_char(q,'FM9999990.000'),'unit_price',to_char(price,'FM9999990.00'),'discount_percent',to_char(discount,'FM990.00'),'vat_rate',to_char(vat,'FM990.00'),
   'gross_cents',gross,'discount_cents',disc,'net_cents',net,'tax_cents',tax,'total_cents',net+tax));
 END LOOP;
 total:=subtotal-discounts+taxes;
 RETURN jsonb_build_object('title',btrim(d->>'title'),'quote_date',starts::text,'valid_until',expires::text,'currency','BSD','lines',rows,'terms',btrim(d->>'terms'),'notes',btrim(d->>'notes'),
  'deposit_percent',to_char(dep,'FM990.00'),'subtotal_cents',subtotal,'discount_cents',discounts,'tax_cents',taxes,'total_cents',total,'deposit_cents',round(total*dep/100));
END $function$;

CREATE OR REPLACE FUNCTION custom_u_production.staff_rpc_102(payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
<<staff_vars>>
DECLARE op text;u uuid;email text;keys text[];key text;perms jsonb;oldrow custom_u_production.staff_access_102%ROWTYPE;saved custom_u_production.staff_access_102%ROWTYPE;oldjson jsonb;rows jsonb;
BEGIN
 IF custom_u_production.history_access_091() IS NULL THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 IF jsonb_typeof(payload) IS DISTINCT FROM 'object' OR octet_length(payload::text)>6000 THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
 op:=payload->>'op';keys:=custom_u_production.permission_keys_102();
 IF op='list' THEN
  SELECT coalesce(jsonb_agg(jsonb_build_object('user_id',m.user_id,'email',u.email,'role',m.role,'member_active',m.active,'access',to_jsonb(a)) ORDER BY lower(u.email)),'[]') INTO rows FROM custom_u_production.staff_members m JOIN auth.users u ON u.id=m.user_id LEFT JOIN custom_u_production.staff_access_102 a ON a.user_id=m.user_id;
  RETURN jsonb_build_object('data',rows,'permission_keys',keys,'enabled',(SELECT enabled FROM custom_u_production.staff_switch_102 WHERE id),'scope','all_company_records');
 END IF;
 IF op='add' THEN
  IF (SELECT count(*) FROM jsonb_object_keys(payload))<>2 OR jsonb_typeof(payload->'email') IS DISTINCT FROM 'string' THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
  email:=lower(btrim(payload->>'email'));
  IF length(email) NOT BETWEEN 3 AND 254 THEN RETURN jsonb_build_object('error','INVALID_EMAIL');END IF;
  IF (SELECT count(*) FROM auth.users WHERE lower(auth.users.email)=staff_vars.email AND email_confirmed_at IS NOT NULL)<>1 THEN RETURN jsonb_build_object('error','CONFIRMED_ACCOUNT_REQUIRED');END IF;
  SELECT id INTO u FROM auth.users WHERE lower(auth.users.email)=staff_vars.email AND email_confirmed_at IS NOT NULL;
  PERFORM pg_advisory_xact_lock(900102);
  IF EXISTS(SELECT 1 FROM custom_u_production.staff_members WHERE user_id=u AND role='admin') THEN RETURN jsonb_build_object('error','ADMIN_PROTECTED');END IF;
  IF EXISTS(SELECT 1 FROM custom_u_production.staff_access_102 WHERE user_id=u) THEN RETURN jsonb_build_object('error','ALREADY_ADDED');END IF;
  IF (SELECT count(*) FROM custom_u_production.staff_access_102)>=100 THEN RETURN jsonb_build_object('error','STAFF_LIMIT');END IF;
  INSERT INTO custom_u_production.staff_members(user_id,role,active) VALUES(u,'office',true) ON CONFLICT(user_id) DO NOTHING;
  INSERT INTO custom_u_production.staff_access_102(user_id,registered_email) VALUES(u,email) RETURNING * INTO saved;
 ELSIF op='save' THEN
  IF (SELECT count(*) FROM jsonb_object_keys(payload))<>5 OR EXISTS(SELECT 1 FROM jsonb_object_keys(payload) k WHERE k NOT IN ('op','user_id','version','active','permissions')) OR jsonb_typeof(payload->'active') IS DISTINCT FROM 'boolean' OR jsonb_typeof(payload->'version') IS DISTINCT FROM 'number' OR coalesce(payload->>'version','') !~ '^[1-9][0-9]{0,8}$' OR coalesce(payload->>'user_id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' OR jsonb_typeof(payload->'permissions') IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
  u:=(payload->>'user_id')::uuid;perms:=payload->'permissions';
  -- Same lock order as document operations; administrators cannot be edited here.
  PERFORM 1 FROM custom_u_production.staff_members WHERE user_id=u FOR UPDATE;
  IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;
  IF EXISTS(SELECT 1 FROM custom_u_production.staff_members WHERE user_id=u AND role='admin') THEN RETURN jsonb_build_object('error','ADMIN_PROTECTED');END IF;
  SELECT * INTO oldrow FROM custom_u_production.staff_access_102 WHERE user_id=u FOR UPDATE;
  IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;
  FOR key IN SELECT jsonb_object_keys(perms) LOOP
   IF NOT key=ANY(keys) OR jsonb_typeof(perms->key) IS DISTINCT FROM 'boolean' THEN RETURN jsonb_build_object('error','INVALID_PERMISSIONS');END IF;
  END LOOP;
  FOR key IN SELECT e.key FROM jsonb_each(perms) e WHERE e.value='true'::jsonb LOOP
   IF perms->(split_part(key,'.',1)||'.view') IS DISTINCT FROM 'true'::jsonb THEN RETURN jsonb_build_object('error','VIEW_PERMISSION_REQUIRED');END IF;
  END LOOP;
  IF (perms->'quotes.create'='true'::jsonb OR perms->'quotes.edit'='true'::jsonb) AND perms->'customers.view' IS DISTINCT FROM 'true'::jsonb OR perms->'payments.view'='true'::jsonb AND perms->'invoices.view' IS DISTINCT FROM 'true'::jsonb THEN RETURN jsonb_build_object('error','RELATED_VIEW_REQUIRED');END IF;
  IF perms->'artwork.view'='true'::jsonb AND perms->'jobs.view' IS DISTINCT FROM 'true'::jsonb THEN RETURN jsonb_build_object('error','RELATED_VIEW_REQUIRED');END IF;
  IF perms->'jobs.create'='true'::jsonb AND perms->'quotes.view' IS DISTINCT FROM 'true'::jsonb THEN RETURN jsonb_build_object('error','RELATED_VIEW_REQUIRED');END IF;
  IF oldrow.version<>(payload->>'version')::integer THEN RETURN jsonb_build_object('error','VERSION_CONFLICT');END IF;
  IF oldrow.active=(payload->>'active')::boolean AND oldrow.permissions=perms THEN RETURN jsonb_build_object('data',to_jsonb(oldrow));END IF;
  oldjson:=to_jsonb(oldrow);
  UPDATE custom_u_production.staff_access_102 SET active=(payload->>'active')::boolean,permissions=perms,version=version+1,updated_at=now() WHERE user_id=u RETURNING * INTO saved;
 ELSE RETURN jsonb_build_object('error','INVALID_OPERATION');END IF;
 INSERT INTO custom_u_production.staff_audit_102(user_id,actor_id,before_record,after_record) VALUES(u,auth.uid(),oldjson,to_jsonb(saved));
 RETURN jsonb_build_object('data',to_jsonb(saved));
END $function$;

CREATE OR REPLACE FUNCTION public.custom_u_adjustments_100(payload jsonb)
 RETURNS jsonb
 LANGUAGE sql
 SET search_path TO ''
AS $function$ SELECT custom_u_production.adjustments_rpc_100(payload); $function$;

CREATE OR REPLACE FUNCTION public.custom_u_payments_099(payload jsonb)
 RETURNS jsonb
 LANGUAGE sql
 SET search_path TO ''
AS $function$ SELECT custom_u_production.payments_rpc_100(payload); $function$;

CREATE OR REPLACE FUNCTION custom_u_production.adjustments_rpc_100(payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
 SET lock_timeout TO '5s'
AS $function$
DECLARE op text;iid uuid;rid uuid;inv custom_u_production.invoices_098%ROWTYPE;c custom_u_production.credit_notes_100%ROWTYPE;r custom_u_production.refunds_100%ROWTYPE;
 d jsonb;before_row jsonb;after_row jsonb;s jsonb;entity text;operation text;reason text;result jsonb;pv integer;
BEGIN
 IF custom_u_production.history_access_091() IS NULL THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 IF jsonb_typeof(payload) IS DISTINCT FROM 'object' OR octet_length(payload::text)>32768 THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
 op:=payload->>'op';IF coalesce(op,'') NOT IN ('invoice','credit','refund','save_credit','issue_credit','record_refund','reverse_refund') THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
 IF op='invoice' OR op IN ('save_credit','record_refund') THEN
  IF coalesce(payload->>'invoice_id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN RETURN jsonb_build_object('error','INVALID_ID');END IF;iid:=(payload->>'invoice_id')::uuid;
 END IF;
 IF op<>'invoice' THEN
  IF coalesce(payload->>'id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN RETURN jsonb_build_object('error','INVALID_ID');END IF;rid:=(payload->>'id')::uuid;
  IF op IN ('credit','issue_credit') THEN SELECT * INTO c FROM custom_u_production.credit_notes_100 WHERE id=rid;IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;iid:=c.invoice_id;END IF;
  IF op IN ('refund','reverse_refund') THEN SELECT * INTO r FROM custom_u_production.refunds_100 WHERE id=rid;IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;iid:=r.invoice_id;END IF;
 END IF;
 IF op IN ('invoice','credit','refund') THEN SELECT * INTO inv FROM custom_u_production.invoices_098 WHERE id=iid;
 ELSE SELECT * INTO inv FROM custom_u_production.invoices_098 WHERE id=iid FOR UPDATE;END IF;
 IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;
 IF inv.status<>'issued' THEN RETURN jsonb_build_object('error','FINALISED_INVOICE_REQUIRED');END IF;
 IF op='invoice' THEN
  SELECT jsonb_build_object('invoice',to_jsonb(inv),'summary',custom_u_production.settlement_100(iid),'credits',coalesce((SELECT jsonb_agg(to_jsonb(x) ORDER BY x.serial) FROM custom_u_production.credit_notes_100 x WHERE x.invoice_id=iid),'[]'),'refunds',coalesce((SELECT jsonb_agg(to_jsonb(x) ORDER BY x.serial) FROM custom_u_production.refunds_100 x WHERE x.invoice_id=iid),'[]')) INTO result;RETURN result;
 END IF;
 IF op='credit' THEN RETURN jsonb_build_object('invoice',to_jsonb(inv),'credit',to_jsonb(c));END IF;
 IF op='refund' THEN RETURN jsonb_build_object('invoice',to_jsonb(inv),'refund',to_jsonb(r));END IF;
 PERFORM pg_advisory_xact_lock(90010003);
 IF (SELECT count(*) FROM custom_u_production.adjustment_audit_100)>=100000 THEN RETURN jsonb_build_object('error','ADJUSTMENT_LIMIT_REACHED');END IF;
 s:=custom_u_production.settlement_100(iid);pv:=(s->>'legacy_payment_version')::integer;
 IF jsonb_typeof(payload->'payment_version') IS DISTINCT FROM 'number' OR coalesce(payload->>'payment_version','') !~ '^[0-9]{1,7}$' THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
 IF op='save_credit' THEN
  IF (SELECT count(*) FROM jsonb_object_keys(payload))<>6 OR EXISTS(SELECT 1 FROM jsonb_object_keys(payload) x WHERE x NOT IN ('op','id','invoice_id','version','payment_version','details')) OR jsonb_typeof(payload->'version') IS DISTINCT FROM 'number' OR coalesce(payload->>'version','') !~ '^[0-9]{1,6}$' THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
  SELECT * INTO c FROM custom_u_production.credit_notes_100 WHERE id=rid FOR UPDATE;
  IF FOUND AND c.invoice_id<>iid THEN RETURN jsonb_build_object('error','ID_CONFLICT');END IF;
  IF c.status='issued' THEN RETURN jsonb_build_object('error','CREDIT_LOCKED');END IF;
  d:=custom_u_production.credit_details_100(payload->'details',inv);IF d ? 'error' THEN RETURN d;END IF;
  IF c.id IS NOT NULL AND c.details=d AND (payload->>'version')::integer IN (c.version,c.version-1) THEN RETURN jsonb_build_object('credit',to_jsonb(c),'summary',s,'existing',true);END IF;
  IF (payload->>'payment_version')::integer<>(s->>'payment_version')::integer THEN RETURN jsonb_build_object('error','BALANCE_CHANGED');END IF;
  IF (payload->>'version')::integer<>coalesce(c.version,0) THEN RETURN jsonb_build_object('error','VERSION_CONFLICT');END IF;
  IF c.id IS NULL THEN
   PERFORM pg_advisory_xact_lock(90010001);
   IF (SELECT count(*) FROM custom_u_production.credit_notes_100)>=5000 OR (SELECT count(*) FROM custom_u_production.credit_notes_100 WHERE invoice_id=iid)>=200 THEN RETURN jsonb_build_object('error','CREDIT_LIMIT_REACHED');END IF;
   INSERT INTO custom_u_production.credit_notes_100(id,invoice_id,invoice_version,is_test,details,status,version,created_by,updated_by) VALUES(rid,iid,inv.version,inv.is_test,d,'draft',1,auth.uid(),auth.uid()) RETURNING * INTO c;operation:='create';before_row:=NULL;
  ELSE
   before_row:=to_jsonb(c);UPDATE custom_u_production.credit_notes_100 SET details=d,version=version+1,updated_at=now(),updated_by=auth.uid() WHERE id=rid RETURNING * INTO c;operation:='save';
  END IF;entity:='credit';after_row:=to_jsonb(c);
 ELSIF op='issue_credit' THEN
  IF (SELECT count(*) FROM jsonb_object_keys(payload))<>5 OR EXISTS(SELECT 1 FROM jsonb_object_keys(payload) x WHERE x NOT IN ('op','id','version','payment_version','confirm')) OR payload->'confirm' IS DISTINCT FROM 'true'::jsonb OR jsonb_typeof(payload->'version') IS DISTINCT FROM 'number' OR coalesce(payload->>'version','') !~ '^[1-9][0-9]{0,5}$' THEN RETURN jsonb_build_object('error','CONFIRM_REQUIRED');END IF;
  SELECT * INTO c FROM custom_u_production.credit_notes_100 WHERE id=rid FOR UPDATE;
  IF c.status='issued' AND (payload->>'version')::integer IN (c.version,c.version-1) THEN RETURN jsonb_build_object('credit',to_jsonb(c),'summary',s,'existing',true);END IF;
  IF c.status='issued' THEN RETURN jsonb_build_object('error','CREDIT_LOCKED');END IF;
  IF (payload->>'version')::integer<>c.version THEN RETURN jsonb_build_object('error','VERSION_CONFLICT');END IF;
  IF (payload->>'payment_version')::integer<>(s->>'payment_version')::integer THEN RETURN jsonb_build_object('error','BALANCE_CHANGED');END IF;
  SELECT jsonb_build_object('credit_date',c.details->>'credit_date','reason',c.details->>'reason','lines',jsonb_agg(jsonb_build_object('line_index',x->'line_index','net_amount',((x->>'net_cents')::numeric/100)::numeric(14,2)::text))) INTO d FROM jsonb_array_elements(c.details->'lines') x;
  d:=custom_u_production.credit_details_100(d,inv);IF d ? 'error' OR d<>c.details THEN RETURN jsonb_build_object('error','CREDIT_CHANGED');END IF;
  before_row:=to_jsonb(c);UPDATE custom_u_production.credit_notes_100 SET status='issued',version=credit_notes_100.version+1,updated_at=now(),updated_by=auth.uid() WHERE id=rid RETURNING * INTO c;entity:='credit';operation:='issue';after_row:=to_jsonb(c);
 ELSIF op='record_refund' THEN
  IF (SELECT count(*) FROM jsonb_object_keys(payload))<>6 OR EXISTS(SELECT 1 FROM jsonb_object_keys(payload) x WHERE x NOT IN ('op','id','invoice_id','details','payment_version','confirm')) OR payload->'confirm' IS DISTINCT FROM 'true'::jsonb THEN RETURN jsonb_build_object('error','CONFIRM_REQUIRED');END IF;
  d:=payload->'details';IF jsonb_typeof(d) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(d))<>5 OR EXISTS(SELECT 1 FROM jsonb_object_keys(d) x WHERE x NOT IN ('refund_date','amount','method','reference','reason')) THEN RETURN jsonb_build_object('error','INVALID_REFUND');END IF;
  d:=custom_u_production.payment_details_099(jsonb_build_object('payment_date',d->'refund_date','amount',d->'amount','method',d->'method','reference',d->'reference','note',d->'reason'));IF d ? 'error' THEN RETURN d;END IF;
  IF d->>'note'='' THEN RETURN jsonb_build_object('error','REFUND_REASON_REQUIRED');END IF;
  d:=(d-'payment_date'-'note')||jsonb_build_object('refund_date',d->'payment_date','reason',d->'note');
  SELECT * INTO r FROM custom_u_production.refunds_100 WHERE id=rid FOR UPDATE;
  IF FOUND THEN
   IF r.invoice_id<>iid OR r.details<>d THEN RETURN jsonb_build_object('error','ID_CONFLICT');END IF;RETURN jsonb_build_object('refund',to_jsonb(r),'summary',s,'existing',true);
  END IF;
  IF (payload->>'payment_version')::integer<>(s->>'payment_version')::integer THEN RETURN jsonb_build_object('error','BALANCE_CHANGED');END IF;
  IF (d->>'amount_cents')::bigint>(s->>'refund_due_cents')::bigint THEN RETURN jsonb_build_object('error','REFUND_EXCEEDS_DUE');END IF;
  PERFORM pg_advisory_xact_lock(90010002);
  IF (SELECT count(*) FROM custom_u_production.refunds_100)>=10000 OR (SELECT count(*) FROM custom_u_production.refunds_100 WHERE invoice_id=iid)>=500 THEN RETURN jsonb_build_object('error','REFUND_LIMIT_REACHED');END IF;
  INSERT INTO custom_u_production.refunds_100(id,invoice_id,invoice_version,is_test,details,status,version,created_by) VALUES(rid,iid,inv.version,inv.is_test,d,'recorded',1,auth.uid()) RETURNING * INTO r;entity:='refund';operation:='record';before_row:=NULL;after_row:=to_jsonb(r);
 ELSE
  IF (SELECT count(*) FROM jsonb_object_keys(payload))<>5 OR EXISTS(SELECT 1 FROM jsonb_object_keys(payload) x WHERE x NOT IN ('op','id','reason','payment_version','confirm')) OR payload->'confirm' IS DISTINCT FROM 'true'::jsonb OR NOT custom_u_production.quote_text_097(payload->'reason',500,true) OR btrim(payload->>'reason')='' THEN RETURN jsonb_build_object('error','REVERSAL_REASON_REQUIRED');END IF;
  reason:=btrim(payload->>'reason');SELECT * INTO r FROM custom_u_production.refunds_100 WHERE id=rid FOR UPDATE;
  IF r.status='reversed' THEN
   IF r.reversal_reason<>reason THEN RETURN jsonb_build_object('error','ALREADY_REVERSED');END IF;RETURN jsonb_build_object('refund',to_jsonb(r),'summary',s,'existing',true);
  END IF;
  IF (payload->>'payment_version')::integer<>(s->>'payment_version')::integer THEN RETURN jsonb_build_object('error','BALANCE_CHANGED');END IF;
  before_row:=to_jsonb(r);UPDATE custom_u_production.refunds_100 SET status='reversed',version=2,reversed_by=auth.uid(),reversed_at=now(),reversal_reason=reason WHERE id=rid RETURNING * INTO r;entity:='refund';operation:='reverse';after_row:=to_jsonb(r);
 END IF;
 INSERT INTO custom_u_production.adjustment_audit_100(invoice_id,entity,entity_id,operation,payment_version,actor_id,before_record,after_record) VALUES(iid,entity,rid,operation,pv,auth.uid(),before_row,after_row);
 RETURN jsonb_build_object(entity,after_row,'summary',custom_u_production.settlement_100(iid),'existing',false);
END $function$;

CREATE OR REPLACE FUNCTION custom_u_production.payments_rpc_099(payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
 SET lock_timeout TO '5s'
AS $function$
DECLARE op text;iid uuid;rid uuid;inv custom_u_production.invoices_098%ROWTYPE;oldrow custom_u_production.payments_099%ROWTYPE;saved custom_u_production.payments_099%ROWTYPE;
 d jsonb;s jsonb;rows jsonb;reason text;balance bigint;after_balance bigint;ver integer;term text;page_no integer;n bigint;
BEGIN
 IF NOT custom_u_production.operation_access_102('payments',payload) THEN RETURN jsonb_build_object('error','ACCESS_DENIED'); END IF;
 IF jsonb_typeof(payload) IS DISTINCT FROM 'object' OR octet_length(payload::text)>16384 THEN RETURN jsonb_build_object('error','INVALID_REQUEST'); END IF;
 op:=payload->>'op';
 IF op='list' THEN
  term:=coalesce(payload->>'q','');IF length(term)>200 OR coalesce(payload->>'page','1') !~ '^[1-9][0-9]{0,5}$' THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;page_no:=coalesce(payload->>'page','1')::integer;
  SELECT count(*) INTO n FROM custom_u_production.invoices_098 i WHERE i.status='issued' AND strpos(lower(i.number||' '||(i.quote_snapshot->'customer_snapshot'->>'name')||' '||(i.quote_snapshot->'data'->>'title')),lower(term))>0;
  SELECT coalesce(jsonb_agg(to_jsonb(t)),'[]') INTO rows FROM (SELECT i.id,i.number,i.is_test,i.quote_snapshot->'customer_snapshot'->>'name' AS customer,i.quote_snapshot->'data'->>'title' AS title,i.details->>'due_date' AS due_date,custom_u_production.payment_summary_099(i.id) AS summary FROM custom_u_production.invoices_098 i
   WHERE i.status='issued' AND strpos(lower(i.number||' '||(i.quote_snapshot->'customer_snapshot'->>'name')||' '||(i.quote_snapshot->'data'->>'title')),lower(term))>0 ORDER BY i.serial DESC LIMIT 50 OFFSET (page_no-1)*50) t;
  RETURN jsonb_build_object('data',rows,'total',n,'page',page_no);
 END IF;
 IF coalesce(op,'') NOT IN ('invoice','receipt','record','reverse') THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
 IF op IN ('receipt','reverse') THEN
  IF coalesce(payload->>'id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN RETURN jsonb_build_object('error','INVALID_ID');END IF;
  rid:=(payload->>'id')::uuid;SELECT * INTO oldrow FROM custom_u_production.payments_099 WHERE id=rid;
  IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;iid:=oldrow.invoice_id;
 ELSE
  IF coalesce(payload->>'invoice_id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN RETURN jsonb_build_object('error','INVALID_ID');END IF;iid:=(payload->>'invoice_id')::uuid;
 END IF;
 -- Mutations take the invoice lock FIRST, including reversal. Summaries are then
 -- read afresh under READ COMMITTED, serialising all entries for this invoice.
 IF op IN ('record','reverse') THEN SELECT * INTO inv FROM custom_u_production.invoices_098 WHERE id=iid FOR UPDATE;
 ELSE SELECT * INTO inv FROM custom_u_production.invoices_098 WHERE id=iid;END IF;
 IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;
 IF inv.status<>'issued' THEN RETURN jsonb_build_object('error','FINALISED_INVOICE_REQUIRED');END IF;
 IF op='invoice' THEN
  SELECT jsonb_build_object('invoice',to_jsonb(inv),'summary',custom_u_production.payment_summary_099(iid),'payments',coalesce((SELECT jsonb_agg(to_jsonb(p) ORDER BY p.serial) FROM custom_u_production.payments_099 p WHERE p.invoice_id=iid),'[]')) INTO rows;
  RETURN rows;
 END IF;
 IF op='receipt' THEN RETURN jsonb_build_object('invoice',to_jsonb(inv),'payment',to_jsonb(oldrow));END IF;
 IF payload->'confirm' IS DISTINCT FROM 'true'::jsonb THEN RETURN jsonb_build_object('error','CONFIRM_REQUIRED');END IF;
 IF jsonb_typeof(payload->'payment_version') IS DISTINCT FROM 'number' OR coalesce(payload->>'payment_version','') !~ '^[0-9]{1,6}$'
 OR jsonb_typeof(payload->'balance_cents') IS DISTINCT FROM 'number' OR coalesce(payload->>'balance_cents','') !~ '^[0-9]{1,12}$' THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
 s:=custom_u_production.payment_summary_099(iid);balance:=(s->>'balance_cents')::bigint;ver:=(s->>'payment_version')::integer;
 IF op='record' THEN
  IF (SELECT count(*) FROM jsonb_object_keys(payload))<>7 OR EXISTS(SELECT 1 FROM jsonb_object_keys(payload) x WHERE x NOT IN ('op','id','invoice_id','details','payment_version','balance_cents','confirm')) OR coalesce(payload->>'id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
  rid:=(payload->>'id')::uuid;d:=custom_u_production.payment_details_099(payload->'details');IF d ? 'error' THEN RETURN d;END IF;
  SELECT * INTO oldrow FROM custom_u_production.payments_099 WHERE id=rid FOR UPDATE;
  IF FOUND THEN
   IF oldrow.invoice_id<>iid OR oldrow.details<>d THEN RETURN jsonb_build_object('error','ID_CONFLICT');END IF;
   RETURN jsonb_build_object('payment',to_jsonb(oldrow),'summary',s,'existing',true);
  END IF;
  IF ver<>(payload->>'payment_version')::integer OR balance<>(payload->>'balance_cents')::bigint THEN RETURN jsonb_build_object('error','BALANCE_CHANGED');END IF;
  IF (d->>'amount_cents')::bigint>balance THEN RETURN jsonb_build_object('error','OVERPAYMENT');END IF;
  IF (SELECT count(*) FROM custom_u_production.payments_099 WHERE invoice_id=iid)>=500 THEN RETURN jsonb_build_object('error','PAYMENT_LIMIT_REACHED');END IF;
  PERFORM pg_advisory_xact_lock(90009902);
  IF (SELECT count(*) FROM custom_u_production.payments_099)>=20000 THEN RETURN jsonb_build_object('error','PAYMENT_LIMIT_REACHED');END IF;
  after_balance:=balance-(d->>'amount_cents')::bigint;
  INSERT INTO custom_u_production.payments_099(id,invoice_id,invoice_version,is_test,details,balance_before_cents,balance_after_cents,status,version,created_by)
   VALUES(rid,iid,inv.version,inv.is_test,d,balance,after_balance,'recorded',1,auth.uid()) RETURNING * INTO saved;
 ELSE
  IF (SELECT count(*) FROM jsonb_object_keys(payload))<>6 OR EXISTS(SELECT 1 FROM jsonb_object_keys(payload) x WHERE x NOT IN ('op','id','reason','payment_version','balance_cents','confirm'))
   OR NOT custom_u_production.quote_text_097(payload->'reason',500,true) THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
  reason:=btrim(payload->>'reason');IF reason='' THEN RETURN jsonb_build_object('error','REVERSAL_REASON_REQUIRED');END IF;
  SELECT * INTO oldrow FROM custom_u_production.payments_099 WHERE id=rid FOR UPDATE;
  IF oldrow.status='reversed' THEN
   IF oldrow.reversal_reason<>reason THEN RETURN jsonb_build_object('error','ALREADY_REVERSED');END IF;
   RETURN jsonb_build_object('payment',to_jsonb(oldrow),'summary',s,'existing',true);
  END IF;
  IF ver<>(payload->>'payment_version')::integer OR balance<>(payload->>'balance_cents')::bigint THEN RETURN jsonb_build_object('error','BALANCE_CHANGED');END IF;
  after_balance:=balance+(oldrow.details->>'amount_cents')::bigint;
  UPDATE custom_u_production.payments_099 SET status='reversed',version=2,reversal_reason=reason,reversed_by=auth.uid(),reversed_at=now() WHERE id=rid RETURNING * INTO saved;
 END IF;
 INSERT INTO custom_u_production.payment_audit_099(payment_id,invoice_id,ledger_version,operation,actor_id,before_record,after_record,balance_before_cents,balance_after_cents)
 VALUES(saved.id,iid,ver+1,op,auth.uid(),CASE WHEN op='record' THEN NULL ELSE to_jsonb(oldrow) END,to_jsonb(saved),balance,after_balance);
 RETURN jsonb_build_object('payment',to_jsonb(saved),'summary',custom_u_production.payment_summary_099(iid),'existing',false);
END $function$;

CREATE OR REPLACE FUNCTION custom_u_production.payments_rpc_100(payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
 SET lock_timeout TO '5s'
AS $function$
DECLARE op text;iid uuid;inv custom_u_production.invoices_098%ROWTYPE;p custom_u_production.payments_099%ROWTYPE;s jsonb;legacy jsonb;result jsonb;entry jsonb;rows jsonb:='[]';
BEGIN
 IF NOT custom_u_production.operation_access_102('payments',payload) THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 IF jsonb_typeof(payload) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;op:=payload->>'op';
 IF op IN ('list','invoice','receipt') THEN
  IF op='list' THEN
   result:=custom_u_production.payments_rpc_099(payload);IF result ? 'error' THEN RETURN result;END IF;
   FOR entry IN SELECT value FROM jsonb_array_elements(result->'data') LOOP rows:=rows||jsonb_build_array(entry||jsonb_build_object('summary',custom_u_production.settlement_100((entry->>'id')::uuid)));END LOOP;
   RETURN result||jsonb_build_object('data',rows);
  END IF;
  result:=custom_u_production.payments_rpc_099(payload);IF result ? 'error' OR op='receipt' THEN RETURN result;END IF;
  iid:=(result->'invoice'->>'id')::uuid;
  SELECT jsonb_build_object('invoice',result->'invoice','summary',custom_u_production.settlement_100(iid),'payments',coalesce((SELECT jsonb_agg(to_jsonb(x) ORDER BY x.serial) FROM custom_u_production.payments_099 x WHERE x.invoice_id=iid),'[]')) INTO result;RETURN result;
 END IF;
 IF op NOT IN ('record','reverse') OR op IS NULL THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
 IF op='record' THEN
  IF coalesce(payload->>'invoice_id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN RETURN jsonb_build_object('error','INVALID_ID');END IF;iid:=(payload->>'invoice_id')::uuid;
 ELSE
  IF coalesce(payload->>'id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN RETURN jsonb_build_object('error','INVALID_ID');END IF;
  SELECT * INTO p FROM custom_u_production.payments_099 WHERE id=(payload->>'id')::uuid;IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;iid:=p.invoice_id;
 END IF;
 SELECT * INTO inv FROM custom_u_production.invoices_098 WHERE id=iid FOR UPDATE;IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;
 s:=custom_u_production.settlement_100(iid);legacy:=custom_u_production.payment_summary_099(iid);
 IF op='record' THEN
  IF coalesce(payload->>'id','') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' THEN RETURN jsonb_build_object('error','INVALID_ID');END IF;
  SELECT * INTO p FROM custom_u_production.payments_099 WHERE id=(payload->>'id')::uuid;
 ELSE SELECT * INTO p FROM custom_u_production.payments_099 WHERE id=(payload->>'id')::uuid;END IF;
 -- An exact retry is delegated unchanged except for the version/balance mapping.
 IF NOT ((op='record' AND p.id IS NOT NULL) OR (op='reverse' AND p.status='reversed')) THEN
  IF payload->'payment_version' IS DISTINCT FROM s->'payment_version' OR payload->'balance_cents' IS DISTINCT FROM s->'balance_cents' THEN RETURN jsonb_build_object('error','BALANCE_CHANGED');END IF;
  IF op='record' THEN
   entry:=custom_u_production.payment_details_099(payload->'details');IF entry ? 'error' THEN RETURN entry;END IF;
   IF (entry->>'amount_cents')::bigint>(s->>'balance_cents')::bigint THEN RETURN jsonb_build_object('error','OVERPAYMENT');END IF;
  ELSE
   IF (p.details->>'amount_cents')::bigint>(s->>'gross_paid_cents')::bigint-(s->>'refund_cents')::bigint THEN RETURN jsonb_build_object('error','REFUND_DEPENDENCY');END IF;
  END IF;
 END IF;
 result:=custom_u_production.payments_rpc_099(payload||jsonb_build_object('payment_version',legacy->'payment_version','balance_cents',legacy->'balance_cents'));
 IF result ? 'error' THEN RETURN result;END IF;
 RETURN result||jsonb_build_object('summary',custom_u_production.settlement_100(iid));
END $function$;

CREATE OR REPLACE FUNCTION custom_u_production.credit_details_100(d jsonb, inv custom_u_production.invoices_098)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE
 SET search_path TO ''
AS $function$
DECLARE item jsonb;line jsonb;outlines jsonb:='[]';idx integer;seen integer[]:='{}';net bigint;tax bigint;prior_net bigint;prior_tax bigint;total_net bigint:=0;total_tax bigint:=0;prior_total bigint;day date;
BEGIN
 IF jsonb_typeof(d) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(d))<>3 OR EXISTS(SELECT 1 FROM jsonb_object_keys(d) x WHERE x NOT IN ('credit_date','reason','lines')) THEN RETURN jsonb_build_object('error','INVALID_CREDIT');END IF;
 IF NOT custom_u_production.quote_text_097(d->'reason',1000,true) OR btrim(d->>'reason')='' OR jsonb_typeof(d->'credit_date') IS DISTINCT FROM 'string' OR coalesce(d->>'credit_date','') !~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$' THEN RETURN jsonb_build_object('error','INVALID_CREDIT');END IF;
 BEGIN day:=(d->>'credit_date')::date;EXCEPTION WHEN OTHERS THEN RETURN jsonb_build_object('error','INVALID_CREDIT_DATE');END;
 IF day<(inv.details->>'invoice_date')::date OR day>(now() AT TIME ZONE 'America/Nassau')::date THEN RETURN jsonb_build_object('error','INVALID_CREDIT_DATE');END IF;
 IF jsonb_typeof(d->'lines') IS DISTINCT FROM 'array' THEN RETURN jsonb_build_object('error','INVALID_CREDIT_LINES');END IF;
 IF jsonb_array_length(d->'lines') NOT BETWEEN 1 AND 100 THEN RETURN jsonb_build_object('error','INVALID_CREDIT_LINES');END IF;
 FOR item IN SELECT value FROM jsonb_array_elements(d->'lines') LOOP
  IF jsonb_typeof(item) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(item))<>2 OR NOT(item ? 'line_index' AND item ? 'net_amount') OR jsonb_typeof(item->'line_index') IS DISTINCT FROM 'number' OR coalesce(item->>'line_index','') !~ '^[0-9]{1,2}$' OR jsonb_typeof(item->'net_amount') IS DISTINCT FROM 'string' OR coalesce(item->>'net_amount','') !~ '^[0-9]{1,10}(\.[0-9]{1,2})?$' THEN RETURN jsonb_build_object('error','INVALID_CREDIT_LINES');END IF;
  idx:=(item->>'line_index')::integer;line:=inv.quote_snapshot->'data'->'lines'->idx;
  IF line IS NULL OR idx=ANY(seen) THEN RETURN jsonb_build_object('error','INVALID_CREDIT_LINES');END IF;seen:=array_append(seen,idx);
  net:=((item->>'net_amount')::numeric*100)::bigint;
  SELECT coalesce(sum((x->>'net_cents')::bigint),0),coalesce(sum((x->>'tax_cents')::bigint),0) INTO prior_net,prior_tax
  FROM custom_u_production.credit_notes_100 c CROSS JOIN LATERAL jsonb_array_elements(c.details->'lines') x WHERE c.invoice_id=inv.id AND c.status='issued' AND (x->>'line_index')::integer=idx;
  IF net<1 OR net+prior_net>(line->>'net_cents')::bigint THEN RETURN jsonb_build_object('error','CREDIT_EXCEEDS_LINE');END IF;
  -- Cumulative allocation returns the exact original VAT when a line is fully credited.
  tax:=round((line->>'tax_cents')::numeric*(net+prior_net)/(line->>'net_cents')::numeric)::bigint-prior_tax;
  outlines:=outlines||jsonb_build_array(jsonb_build_object('line_index',idx,'net_cents',net,'tax_cents',tax,'total_cents',net+tax,'prior_net_cents',prior_net,'prior_tax_cents',prior_tax));total_net:=total_net+net;total_tax:=total_tax+tax;
 END LOOP;
 SELECT coalesce(jsonb_agg(value ORDER BY (value->>'line_index')::integer),'[]') INTO outlines FROM jsonb_array_elements(outlines);
 SELECT coalesce(sum((c.details->>'total_cents')::bigint),0) INTO prior_total FROM custom_u_production.credit_notes_100 c WHERE c.invoice_id=inv.id AND c.status='issued';
 RETURN jsonb_build_object('credit_date',d->>'credit_date','reason',btrim(d->>'reason'),'lines',outlines,'net_cents',total_net,'tax_cents',total_tax,'total_cents',total_net+total_tax,'prior_credit_cents',prior_total);
END $function$;



CREATE OR REPLACE FUNCTION custom_u_production.invoice_sources_114(payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE term text;page_no int;total bigint;rows jsonb;c custom_u_production.crm_records_093%ROWTYPE;BEGIN
 IF NOT custom_u_production.operation_access_102('invoices',jsonb_build_object('op','get')) OR NOT (custom_u_production.can_102('invoices.create') OR custom_u_production.can_102('invoices.edit')) THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 IF jsonb_typeof(payload) IS DISTINCT FROM 'object' OR octet_length(payload::text)>2000 THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
 IF payload->>'op'='setup' AND (SELECT count(*) FROM jsonb_object_keys(payload))=1 THEN
  RETURN jsonb_build_object('profile',(SELECT to_jsonb(p) FROM custom_u_production.quote_profile_097 p WHERE p.id='business'));
 ELSIF payload->>'op'='customers' AND (SELECT count(*) FROM jsonb_object_keys(payload))=3 THEN
  term:=coalesce(payload->>'q','');IF length(term)>200 OR coalesce(payload->>'page','') !~ '^[1-9][0-9]{0,5}$' THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;page_no:=(payload->>'page')::int;
  SELECT count(*) INTO total FROM custom_u_production.crm_records_093 WHERE kind='customer' AND active AND strpos(lower(data->>'name'),lower(term))>0;
  SELECT coalesce(jsonb_agg(x),'[]') INTO rows FROM (SELECT id,data->>'name' name FROM custom_u_production.crm_records_093 WHERE kind='customer' AND active AND strpos(lower(data->>'name'),lower(term))>0 ORDER BY lower(data->>'name'),id LIMIT 50 OFFSET (page_no-1)*50) x;
  RETURN jsonb_build_object('data',rows,'total',total,'page',page_no);
 ELSIF payload->>'op'='customer' AND (SELECT count(*) FROM jsonb_object_keys(payload))=2 THEN
  SELECT * INTO c FROM custom_u_production.crm_records_093 WHERE id::text=payload->>'id' AND kind='customer' AND active;
  IF NOT FOUND THEN RETURN jsonb_build_object('error','CUSTOMER_INACTIVE');END IF;
  SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY lower(x.data->>'name'),x.id),'[]') INTO rows FROM custom_u_production.crm_records_093 x WHERE customer_id=c.id AND kind='contact' AND active;
  RETURN jsonb_build_object('data',to_jsonb(c),'contacts',rows);
 END IF;RETURN jsonb_build_object('error','INVALID_REQUEST');
END $function$;

CREATE OR REPLACE FUNCTION custom_u_production.payment_details_099(d jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE
 SET search_path TO ''
AS $function$
DECLARE k text;day date;amount bigint;
BEGIN
 IF jsonb_typeof(d) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('error','INVALID_PAYMENT'); END IF;
 IF (SELECT count(*) FROM jsonb_object_keys(d))<>5 OR EXISTS(SELECT 1 FROM jsonb_object_keys(d) x WHERE x NOT IN ('payment_date','amount','method','reference','note')) THEN RETURN jsonb_build_object('error','INVALID_PAYMENT'); END IF;
 IF jsonb_typeof(d->'amount') IS DISTINCT FROM 'string' OR coalesce(d->>'amount','') !~ '^[0-9]{1,10}(\.[0-9]{1,2})?$' THEN RETURN jsonb_build_object('error','INVALID_AMOUNT'); END IF;
 amount:=((d->>'amount')::numeric*100)::bigint;
 IF amount<1 OR amount>100000000000 THEN RETURN jsonb_build_object('error','INVALID_AMOUNT'); END IF;
 IF jsonb_typeof(d->'payment_date') IS DISTINCT FROM 'string' OR coalesce(d->>'payment_date','') !~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$' THEN RETURN jsonb_build_object('error','INVALID_PAYMENT_DATE'); END IF;
 BEGIN day:=(d->>'payment_date')::date;EXCEPTION WHEN OTHERS THEN RETURN jsonb_build_object('error','INVALID_PAYMENT_DATE');END;
 IF day>(now() AT TIME ZONE 'America/Nassau')::date THEN RETURN jsonb_build_object('error','FUTURE_PAYMENT_DATE'); END IF;
 IF coalesce(d->>'method','') NOT IN ('cash','bank_transfer','card','cheque','other') THEN RETURN jsonb_build_object('error','PAYMENT_METHOD_REQUIRED'); END IF;
 FOREACH k IN ARRAY ARRAY['reference','note'] LOOP
  IF NOT custom_u_production.quote_text_097(d->k,CASE WHEN k='reference' THEN 120 ELSE 1000 END,k='note') THEN RETURN jsonb_build_object('error','INVALID_PAYMENT'); END IF;
  d:=jsonb_set(d,ARRAY[k],to_jsonb(btrim(d->>k)));
 END LOOP;
 RETURN (d-'amount')||jsonb_build_object('amount_cents',amount);
END $function$;

CREATE OR REPLACE FUNCTION custom_u_production.payment_summary_099(iid uuid)
 RETURNS jsonb
 LANGUAGE sql
 STABLE
 SET search_path TO ''
AS $function$
 SELECT jsonb_build_object('invoice_total_cents',total,'paid_cents',paid,'balance_cents',total-paid,'payment_version',ver,
 'payment_state',CASE WHEN total=0 THEN 'nothing_due' WHEN paid=total THEN 'paid' WHEN paid=0 THEN 'unpaid' ELSE 'part_paid' END)
 FROM (SELECT (i.quote_snapshot->'data'->>'total_cents')::bigint AS total,
 coalesce((SELECT sum((p.details->>'amount_cents')::bigint) FROM custom_u_production.payments_099 p WHERE p.invoice_id=i.id AND p.status='recorded'),0)::bigint AS paid,
 (SELECT count(*)::integer FROM custom_u_production.payment_audit_099 a WHERE a.invoice_id=i.id) AS ver
 FROM custom_u_production.invoices_098 i WHERE i.id=iid) t;
$function$;

CREATE OR REPLACE FUNCTION custom_u_production.quote_text_097(v jsonb, lim integer, multi boolean DEFAULT false)
 RETURNS boolean
 LANGUAGE sql
 IMMUTABLE
 SET search_path TO ''
AS $function$
 SELECT coalesce(jsonb_typeof(v)='string' AND length(v#>>'{}')<=lim AND
 CASE WHEN multi THEN replace(v#>>'{}',chr(10),'') !~ '[[:cntrl:]]' ELSE (v#>>'{}') !~ '[[:cntrl:]]' END,false);
$function$;

CREATE OR REPLACE FUNCTION custom_u_production.settlement_100(iid uuid)
 RETURNS jsonb
 LANGUAGE sql
 STABLE
 SET search_path TO ''
AS $function$
 SELECT jsonb_build_object('invoice_total_cents',total,'credit_cents',credits,'adjusted_total_cents',total-credits,'gross_paid_cents',paid,'refund_cents',refunded,'paid_cents',paid-refunded,
 'balance_cents',greatest(total-credits-paid+refunded,0),'refund_due_cents',greatest(paid-refunded-total+credits,0),'payment_version',pv+av,'legacy_payment_version',pv,
 'payment_state',CASE WHEN paid-refunded>total-credits THEN 'refund_due' WHEN total>0 AND credits=total THEN 'credited' WHEN total=0 THEN 'nothing_due' WHEN paid-refunded=total-credits THEN 'paid' WHEN paid-refunded=0 THEN 'unpaid' ELSE 'part_paid' END)
 FROM (SELECT (i.quote_snapshot->'data'->>'total_cents')::bigint total,
 coalesce((SELECT sum((c.details->>'total_cents')::bigint) FROM custom_u_production.credit_notes_100 c WHERE c.invoice_id=i.id AND c.status='issued'),0)::bigint credits,
 coalesce((SELECT sum((p.details->>'amount_cents')::bigint) FROM custom_u_production.payments_099 p WHERE p.invoice_id=i.id AND p.status='recorded'),0)::bigint paid,
 coalesce((SELECT sum((r.details->>'amount_cents')::bigint) FROM custom_u_production.refunds_100 r WHERE r.invoice_id=i.id AND r.status='recorded'),0)::bigint refunded,
 (SELECT count(*) FROM custom_u_production.payment_audit_099 a WHERE a.invoice_id=i.id)::integer pv,
 (SELECT count(*) FROM custom_u_production.adjustment_audit_100 a WHERE a.invoice_id=i.id)::integer av
 FROM custom_u_production.invoices_098 i WHERE i.id=iid) totals;
$function$;
