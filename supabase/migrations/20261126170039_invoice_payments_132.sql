-- Release 132: a consistent, read-only payment view alongside the saved invoice.
CREATE OR REPLACE FUNCTION custom_u_production.invoice_document_132(iid uuid)
 RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' SET lock_timeout='5s'
AS $function$
DECLARE inv custom_u_production.invoices_098%ROWTYPE;s jsonb;payments jsonb;
BEGIN
 -- Check and lock staff access before the invoice, matching the write paths.
 IF NOT custom_u_production.operation_access_102('invoices','{"op":"get"}'::jsonb)
 THEN RETURN jsonb_build_object('error','ACCESS_DENIED');END IF;
 SELECT * INTO inv FROM custom_u_production.invoices_098 WHERE id=iid FOR SHARE;
 IF NOT FOUND THEN RETURN jsonb_build_object('error','NOT_FOUND');END IF;
 -- Payment, reversal, credit and refund writes take this same invoice FOR UPDATE.
 s:=custom_u_production.settlement_100(iid);
 SELECT coalesce(jsonb_agg(jsonb_build_object('number',p.number,'date',p.details->>'payment_date',
  'amount_cents',(p.details->>'amount_cents')::bigint) ORDER BY p.details->>'payment_date',p.number),'[]'::jsonb)
 INTO payments FROM custom_u_production.payments_099 p WHERE p.invoice_id=iid AND p.status='recorded';
 RETURN jsonb_build_object('data',to_jsonb(inv),'payment_summary',jsonb_build_object(
  'invoice_id',inv.id,'invoice_version',inv.version,'ledger_version',s->'payment_version',
  'total_cents',s->'invoice_total_cents','paid_cents',s->'gross_paid_cents',
  'credit_cents',s->'credit_cents','refund_cents',s->'refund_cents',
  'balance_cents',s->'balance_cents','refund_due_cents',s->'refund_due_cents','payments',payments));
END $function$;
REVOKE ALL ON FUNCTION custom_u_production.invoice_document_132(uuid) FROM PUBLIC,anon,authenticated;

CREATE OR REPLACE FUNCTION public.custom_u_invoices_114(payload jsonb)
 RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=''
AS $function$
BEGIN
 IF jsonb_typeof(payload)='object' AND octet_length(payload::text)<=32768 AND payload->>'op'='get'
 AND coalesce(payload->>'id','') ~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
 THEN RETURN custom_u_production.invoice_document_132((payload->>'id')::uuid);END IF;
 RETURN custom_u_production.invoices_rpc_131(payload);
EXCEPTION WHEN check_violation THEN
 IF SQLERRM IN ('ADMIN_DISCOUNT_REQUIRED','DOCUMENT_NUMBER_LOCKED','NUMBERING_EXHAUSTED','ACCESS_DENIED')
 THEN RETURN jsonb_build_object('error',SQLERRM);ELSE RAISE;END IF;
END $function$;
