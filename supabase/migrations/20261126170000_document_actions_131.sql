-- Release 131: downloads, saved-quote conversion, audited finalised revisions.

CREATE OR REPLACE FUNCTION custom_u_production.permission_keys_102()
 RETURNS text[]
 LANGUAGE sql
 IMMUTABLE
 SET search_path TO ''
AS $function$
 SELECT ARRAY['customers.view','customers.create','customers.edit','quotes.view','quotes.create','quotes.edit','quotes.amend','quotes.approve','quotes.send','invoices.view','invoices.create','invoices.edit','invoices.amend','invoices.issue','invoices.send','payments.view','payments.record','payments.reverse','jobs.view','jobs.create','jobs.edit','jobs.progress','artwork.view','artwork.upload','artwork.approve','products.view','products.create','products.edit','products.send']::text[];
$function$;

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
  IF op='amend' THEN RETURN custom_u_production.can_102('quotes.amend');END IF;
  RETURN op='save' AND custom_u_production.can_102('customers.view') AND (custom_u_production.can_102('quotes.create') OR custom_u_production.can_102('quotes.edit'));
 ELSIF area='invoices' THEN
  IF op IN ('list','get') THEN RETURN true;END IF;
  cap:=CASE op WHEN 'convert' THEN 'invoices.create' WHEN 'amend' THEN 'invoices.amend' WHEN 'create' THEN 'invoices.create' WHEN 'save' THEN 'invoices.edit' WHEN 'issue' THEN 'invoices.issue' ELSE NULL END;
  RETURN custom_u_production.can_102(cap) AND (op NOT IN ('create','convert') OR custom_u_production.can_102('quotes.view'));
 ELSIF area='payments' THEN
  IF NOT custom_u_production.can_102('invoices.view') THEN RETURN false;END IF;
  IF op IN ('list','invoice','receipt') THEN RETURN true;END IF;
  RETURN custom_u_production.can_102(CASE op WHEN 'record' THEN 'payments.record' WHEN 'reverse' THEN 'payments.reverse' ELSE NULL END);
 END IF;
 RETURN false;
END $function$;

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
  IF q.status NOT IN ('draft','issued') THEN RETURN jsonb_build_object('error','QUOTE_NOT_FOUND'); END IF;
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
  IF TG_OP='INSERT' AND NEW.quote_id IS NOT NULL AND EXISTS(SELECT 1 FROM custom_u_production.quotes_097 q WHERE q.id=NEW.quote_id AND q.status IN ('draft','issued') AND to_jsonb(q)=NEW.quote_snapshot) THEN RETURN NEW;END IF;
 END IF;
 IF cid=oldcid AND (SELECT jsonb_agg(l-ARRAY['description','finish','placement'] ORDER BY n) FROM jsonb_array_elements(lines) WITH ORDINALITY x(l,n)) IS NOT DISTINCT FROM (SELECT jsonb_agg(l-ARRAY['description','finish','placement'] ORDER BY n) FROM jsonb_array_elements(oldlines) WITH ORDINALITY x(l,n)) THEN RETURN NEW;END IF;
 SELECT coalesce((data->>'percent')::numeric,0) INTO rate FROM custom_u_production.controls_118 WHERE key='discount:'||cid::text FOR SHARE;
 rate:=coalesce(rate,0);
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(lines) l WHERE (l->>'discount_percent')::numeric<>0 AND (l->>'discount_percent')::numeric<>rate) THEN RAISE EXCEPTION 'ADMIN_DISCOUNT_REQUIRED' USING ERRCODE='23514';END IF;
 RETURN NEW;
END $function$;

-- Revision saves leave issued documents issued. Prior versions remain in the audit tables.
CREATE OR REPLACE FUNCTION custom_u_production.quotes_rpc_131(payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' SET lock_timeout='5s' AS $$
DECLARE oldq custom_u_production.quotes_097%ROWTYPE;saved custom_u_production.quotes_097%ROWTYPE;d jsonb;expected integer;
BEGIN
 IF payload->>'op' IS DISTINCT FROM 'amend' THEN RETURN custom_u_production.quotes_rpc_097(payload);END IF;
 IF NOT custom_u_production.operation_access_102('quotes',payload) THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 IF jsonb_typeof(payload) IS DISTINCT FROM 'object' OR octet_length(payload::text)>262144 OR
 (SELECT count(*) FROM jsonb_object_keys(payload))<>6 OR EXISTS(SELECT 1 FROM jsonb_object_keys(payload) k WHERE k NOT IN ('op','id','version','customer_id','contact_id','data')) OR
 coalesce(payload->>'id','') !~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$' OR coalesce(payload->>'version','') !~ '^[1-9][0-9]{0,8}$' THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
 d:=custom_u_production.quote_data_097(payload->'data');IF d ? 'error' THEN RETURN d;END IF;expected:=(payload->>'version')::integer;
 PERFORM pg_advisory_xact_lock(hashtextextended(payload->>'id',97));
 SELECT * INTO oldq FROM custom_u_production.quotes_097 WHERE id=(payload->>'id')::uuid FOR UPDATE;
 IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;
 IF oldq.status<>'issued' THEN RETURN jsonb_build_object('error','FINALISED_DOCUMENT_REQUIRED');END IF;
 IF (payload->>'customer_id') IS DISTINCT FROM oldq.customer_id::text OR (payload->>'contact_id') IS DISTINCT FROM oldq.contact_id::text THEN RETURN jsonb_build_object('error','SAVED_PARTIES_LOCKED');END IF;
 IF oldq.data=d AND oldq.version IN (expected,expected+1) THEN RETURN jsonb_build_object('data',to_jsonb(oldq),'existing',true);END IF;
 IF oldq.version<>expected THEN RETURN jsonb_build_object('error','VERSION_CONFLICT');END IF;
 IF (d->>'tax_cents')::bigint>0 AND btrim(coalesce(oldq.seller_snapshot->>'tax_id',''))='' THEN RETURN jsonb_build_object('error','TAX_ID_REQUIRED');END IF;
 UPDATE custom_u_production.quotes_097 SET data=d,version=version+1,updated_at=now() WHERE id=oldq.id RETURNING * INTO saved;
 INSERT INTO custom_u_production.quote_audit_097(entity,entity_id,actor_id,before_record,after_record) VALUES('quote',oldq.id::text,auth.uid(),to_jsonb(oldq),to_jsonb(saved));
 RETURN jsonb_build_object('data',to_jsonb(saved));
END $$;

-- The financial signature retains line order and all quantities/rates/totals.
CREATE OR REPLACE FUNCTION custom_u_production.invoice_financial_131(d jsonb) RETURNS jsonb LANGUAGE sql IMMUTABLE SET search_path='' AS $$
 SELECT coalesce(jsonb_agg(l-ARRAY['description','finish','placement'] ORDER BY n),'[]'::jsonb) FROM jsonb_array_elements(d->'lines') WITH ORDINALITY AS x(l,n);
$$;

CREATE OR REPLACE FUNCTION custom_u_production.invoices_rpc_131(payload jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' SET lock_timeout='5s' AS $$
DECLARE op text:=payload->>'op';oldi custom_u_production.invoices_098%ROWTYPE;saved custom_u_production.invoices_098%ROWTYPE;
 q custom_u_production.quotes_097%ROWTYPE;d jsonb;fields jsonb;snapshot jsonb;expected integer;days integer;today date;codes jsonb;
BEGIN
 IF op NOT IN ('amend','convert') OR op IS NULL THEN RETURN custom_u_production.invoices_rpc_114(payload);END IF;
 IF NOT custom_u_production.operation_access_102('invoices',payload) THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 IF jsonb_typeof(payload) IS DISTINCT FROM 'object' OR octet_length(payload::text)>262144 THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
 IF op='convert' THEN
  IF (SELECT count(*) FROM jsonb_object_keys(payload))<>5 OR EXISTS(SELECT 1 FROM jsonb_object_keys(payload) k WHERE k NOT IN ('op','quote_id','quote_version','invoice_date','terms')) OR
   coalesce(payload->>'quote_id','') !~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$' OR coalesce(payload->>'quote_version','') !~ '^[1-9][0-9]{0,8}$' OR coalesce(payload->>'invoice_date','') !~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$' THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
  SELECT * INTO q FROM custom_u_production.quotes_097 WHERE id=(payload->>'quote_id')::uuid FOR SHARE;
  IF NOT FOUND THEN RETURN jsonb_build_object('error','QUOTE_NOT_FOUND');END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(q.id::text||'false',98));
  SELECT * INTO oldi FROM custom_u_production.invoices_098 WHERE quote_id=q.id AND NOT is_test FOR UPDATE;
  IF FOUND THEN RETURN jsonb_build_object('data',to_jsonb(oldi),'existing',true);END IF;
  IF q.version<>(payload->>'quote_version')::integer THEN RETURN jsonb_build_object('error','VERSION_CONFLICT');END IF;
  BEGIN today:=(payload->>'invoice_date')::date;EXCEPTION WHEN OTHERS THEN RETURN jsonb_build_object('error','INVALID_DATES');END;
  SELECT coalesce((data->>'payment_terms_days')::integer,0) INTO days FROM custom_u_production.crm_records_093 WHERE id=q.customer_id;
  SELECT jsonb_agg(CASE WHEN (l->>'vat_rate')::numeric>0 THEN 'T' ELSE '' END ORDER BY n) INTO codes FROM jsonb_array_elements(q.data->'lines') WITH ORDINALITY x(l,n);
  fields:=jsonb_build_object('invoice_date',today::text,'due_date',(today+coalesce(days,0))::text,'supply_date','','document_type',CASE WHEN coalesce(q.customer_snapshot->>'tax_id','')<>'' AND coalesce(q.customer_snapshot->>'address','')<>'' THEN 'vat_invoice' ELSE 'vat_sales_receipt' END,
   'billing_address',coalesce(q.customer_snapshot->>'address',''),'billing_tax_id',coalesce(q.customer_snapshot->>'tax_id',''),'notes',q.data->>'notes','terms',payload->>'terms','tax_codes',codes);
  RETURN custom_u_production.invoices_rpc_098(jsonb_build_object('op','create','id',gen_random_uuid(),'quote_id',q.id,'quote_version',q.version,'is_test',false,'details',fields));
 END IF;
 IF (SELECT count(*) FROM jsonb_object_keys(payload))<>5 OR EXISTS(SELECT 1 FROM jsonb_object_keys(payload) k WHERE k NOT IN ('op','id','version','data','details')) OR
 coalesce(payload->>'id','') !~ '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$' OR coalesce(payload->>'version','') !~ '^[1-9][0-9]{0,8}$' OR jsonb_typeof(payload->'data') IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(payload->'data'))<>2 OR NOT (payload->'data' ?& ARRAY['title','lines']) THEN RETURN jsonb_build_object('error','INVALID_REQUEST');END IF;
 expected:=(payload->>'version')::integer;
 SELECT * INTO oldi FROM custom_u_production.invoices_098 WHERE id=(payload->>'id')::uuid FOR UPDATE;
 IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;
 IF oldi.status<>'issued' THEN RETURN jsonb_build_object('error','FINALISED_DOCUMENT_REQUIRED');END IF;
 d:=custom_u_production.quote_data_097(jsonb_build_object('title',payload->'data'->'title','lines',payload->'data'->'lines','currency','BSD',
 'quote_date',CASE WHEN oldi.quote_id IS NULL THEN payload->'details'->>'invoice_date' ELSE oldi.quote_snapshot->'data'->>'quote_date' END,
 'valid_until',CASE WHEN oldi.quote_id IS NULL THEN payload->'details'->>'due_date' ELSE oldi.quote_snapshot->'data'->>'valid_until' END,
 'deposit_percent',CASE WHEN oldi.quote_id IS NULL THEN '0' ELSE oldi.quote_snapshot->'data'->>'deposit_percent' END,
 'notes',CASE WHEN oldi.quote_id IS NULL THEN payload->'details'->>'notes' ELSE oldi.quote_snapshot->'data'->>'notes' END,
 'terms',CASE WHEN oldi.quote_id IS NULL THEN payload->'details'->>'terms' ELSE oldi.quote_snapshot->'data'->>'terms' END));
 IF d ? 'error' THEN RETURN d;END IF;
 fields:=custom_u_production.invoice_details_098(payload->'details',d);IF fields ? 'error' THEN RETURN fields;END IF;
 IF btrim(coalesce(oldi.quote_snapshot->'seller_snapshot'->>'tax_id',''))='' THEN RETURN jsonb_build_object('error','SUPPLIER_TAX_ID_REQUIRED');END IF;
 IF fields->'tax_codes' @> '[""]'::jsonb THEN RETURN jsonb_build_object('error','TAX_CLASSIFICATION_REQUIRED');END IF;
 IF fields->>'document_type'='vat_invoice' AND (fields->>'billing_address'='' OR fields->>'billing_tax_id'='') THEN RETURN jsonb_build_object('error','RECIPIENT_TAX_DETAILS_REQUIRED');END IF;
 IF oldi.quote_snapshot->'data'=d AND oldi.details=fields AND oldi.version IN (expected,expected+1) THEN RETURN jsonb_build_object('data',to_jsonb(oldi),'existing',true);END IF;
 IF oldi.version<>expected THEN RETURN jsonb_build_object('error','VERSION_CONFLICT');END IF;
 -- Once a financial transaction exists, use credit/refund corrections for amounts.
 -- Text, billing details and dates can still be revised without rewriting the ledger.
 IF (custom_u_production.invoice_financial_131(d) IS DISTINCT FROM custom_u_production.invoice_financial_131(oldi.quote_snapshot->'data') OR fields->'tax_codes' IS DISTINCT FROM oldi.details->'tax_codes' OR fields->'invoice_date' IS DISTINCT FROM oldi.details->'invoice_date') AND
 (EXISTS(SELECT 1 FROM custom_u_production.payments_099 WHERE invoice_id=oldi.id) OR EXISTS(SELECT 1 FROM custom_u_production.credit_notes_100 WHERE invoice_id=oldi.id) OR EXISTS(SELECT 1 FROM custom_u_production.refunds_100 WHERE invoice_id=oldi.id)) THEN RETURN jsonb_build_object('error','INVOICE_FINANCIAL_HISTORY');END IF;
 snapshot:=oldi.quote_snapshot;
 IF oldi.quote_id IS NOT NULL AND NOT snapshot ? 'original_quote_data' THEN snapshot:=snapshot||jsonb_build_object('original_quote_data',snapshot->'data');END IF;
 snapshot:=jsonb_set(snapshot,'{data}',d);
 UPDATE custom_u_production.invoices_098 SET quote_snapshot=snapshot,details=fields,version=version+1,updated_at=now() WHERE id=oldi.id RETURNING * INTO saved;
 INSERT INTO custom_u_production.invoice_audit_098(invoice_id,actor_id,before_record,after_record) VALUES(oldi.id,auth.uid(),to_jsonb(oldi),to_jsonb(saved));
 RETURN jsonb_build_object('data',to_jsonb(saved));
END $$;

CREATE OR REPLACE FUNCTION custom_u_production.invoice_revision_131(iid uuid,revision integer) RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT after_record FROM custom_u_production.invoice_audit_098 WHERE invoice_id=iid AND (after_record->>'version')::integer=revision ORDER BY id DESC LIMIT 1;
$$;

REVOKE ALL ON FUNCTION custom_u_production.quotes_rpc_131(jsonb),custom_u_production.invoices_rpc_131(jsonb),custom_u_production.invoice_revision_131(uuid,integer),custom_u_production.invoice_financial_131(jsonb) FROM PUBLIC,anon,authenticated;


CREATE OR REPLACE FUNCTION public.custom_u_quotes_097(payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$BEGIN RETURN custom_u_production.quotes_rpc_131(payload);EXCEPTION WHEN check_violation THEN IF SQLERRM IN ('ADMIN_DISCOUNT_REQUIRED','DOCUMENT_NUMBER_LOCKED','NUMBERING_EXHAUSTED','ACCESS_DENIED') THEN RETURN jsonb_build_object('error',SQLERRM);ELSE RAISE;END IF;END $function$;

CREATE OR REPLACE FUNCTION public.custom_u_invoices_114(payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$BEGIN RETURN custom_u_production.invoices_rpc_131(payload);EXCEPTION WHEN check_violation THEN IF SQLERRM IN ('ADMIN_DISCOUNT_REQUIRED','DOCUMENT_NUMBER_LOCKED','NUMBERING_EXHAUSTED','ACCESS_DENIED') THEN RETURN jsonb_build_object('error',SQLERRM);ELSE RAISE;END IF;END $function$;

CREATE OR REPLACE FUNCTION public.custom_u_invoice_terms_113(quote_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE c custom_u_production.crm_records_093%ROWTYPE;BEGIN
 IF NOT custom_u_production.can_102('invoices.create') OR NOT custom_u_production.can_102('invoices.view') THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 SELECT x.* INTO c FROM custom_u_production.crm_records_093 x JOIN custom_u_production.quotes_097 q ON q.customer_id=x.id WHERE q.id=quote_id AND x.kind='customer';
 IF NOT FOUND THEN RETURN jsonb_build_object('error','QUOTE_NOT_FOUND');END IF;
 RETURN jsonb_build_object('payment_terms_days',c.data->'payment_terms_days','customer_version',c.version);
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
 IF op='receipt' THEN RETURN jsonb_build_object('invoice',custom_u_production.invoice_revision_131(inv.id,oldrow.invoice_version),'payment',to_jsonb(oldrow));END IF;
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
 IF op='credit' THEN RETURN jsonb_build_object('invoice',custom_u_production.invoice_revision_131(inv.id,c.invoice_version),'credit',to_jsonb(c));END IF;
 IF op='refund' THEN RETURN jsonb_build_object('invoice',custom_u_production.invoice_revision_131(inv.id,r.invoice_version),'refund',to_jsonb(r));END IF;
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
-- Existing job release checks retain the quote revision used to create the job.
CREATE OR REPLACE FUNCTION custom_u_production.job_gate_103(j custom_u_production.jobs_103)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE
 SET search_path TO ''
AS $function$
DECLARE q custom_u_production.quotes_097;inv custom_u_production.invoices_098;s jsonb;code text;ah custom_u_production.artwork_heads_104;af custom_u_production.artwork_files_104;
BEGIN
 SELECT (jsonb_populate_record(NULL::custom_u_production.quotes_097,a.after_record)).* INTO q
 FROM custom_u_production.quote_audit_097 a WHERE a.entity='quote' AND a.entity_id=j.quote_id::text AND (a.after_record->>'version')::integer=(j.source->>'quote_version')::integer ORDER BY a.id DESC LIMIT 1;
 SELECT * INTO inv FROM custom_u_production.invoices_098 WHERE quote_id=j.quote_id AND is_test=j.is_test;
 SELECT * INTO ah FROM custom_u_production.artwork_heads_104 WHERE job_id=j.id;
 SELECT * INTO af FROM custom_u_production.artwork_files_104 WHERE id=ah.approved_id;
 IF q.status IS DISTINCT FROM 'issued' THEN code:='FINALISED_QUOTE_REQUIRED';
 ELSIF j.details->'customer_approved' IS DISTINCT FROM 'true'::jsonb THEN code:='CUSTOMER_APPROVAL_REQUIRED';
 ELSIF j.details->'artwork_approved' IS DISTINCT FROM 'true'::jsonb THEN code:='ARTWORK_APPROVAL_REQUIRED';
 ELSIF EXISTS(SELECT 1 FROM custom_u_production.artwork_files_104 WHERE job_id=j.id AND status='stored') AND NOT EXISTS(SELECT 1 FROM storage.buckets WHERE id='custom-u-artwork-104' AND public=false) THEN code:='ARTWORK_STORAGE_PRIVATE_REQUIRED';
 ELSIF EXISTS(SELECT 1 FROM custom_u_production.artwork_files_104 WHERE job_id=j.id AND status='stored') AND (ah.approved_id IS NULL OR NOT EXISTS(SELECT 1 FROM storage.objects WHERE bucket_id='custom-u-artwork-104' AND name=af.object_path AND (metadata->>'size')::bigint=af.size_bytes)) THEN code:='ARTWORK_VERSION_APPROVAL_REQUIRED';
 ELSE
  IF inv.id IS NOT NULL THEN s:=custom_u_production.settlement_100(inv.id);END IF;
  IF coalesce((s->>'credit_cents')::bigint,0)>0 THEN code:='CREDIT_REVIEW_REQUIRED';
  ELSIF (q.data->>'deposit_cents')::bigint>0 AND (inv.id IS NULL OR inv.status<>'issued') THEN code:='FINALISED_INVOICE_REQUIRED';
  ELSIF (q.data->>'deposit_cents')::bigint>coalesce((s->>'paid_cents')::bigint,0) THEN code:='DEPOSIT_REQUIRED';
  ELSE code:='READY';END IF;
 END IF;
 RETURN jsonb_build_object('ready',code='READY','code',code,'invoice_id',inv.id)||CASE WHEN ah.approved_id IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('artwork_file_id',ah.approved_id,'artwork_revision',ah.revision) END;
END $function$
;
