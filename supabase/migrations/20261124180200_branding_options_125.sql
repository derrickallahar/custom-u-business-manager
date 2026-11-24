-- Branding options 125: extends validation and retained view references only.
-- Existing rows, access grants, prices and invoice data are unchanged.
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='30s';
SELECT pg_advisory_xact_lock(900107);
SELECT pg_advisory_xact_lock(900108);
CREATE OR REPLACE FUNCTION custom_u_production.mockup_config_valid_107(d jsonb) RETURNS boolean LANGUAGE plpgsql IMMUTABLE SET search_path='' AS $$
DECLARE k text;n numeric;s jsonb;
BEGIN
 IF jsonb_typeof(d)='object' AND d ? 'scale' THEN
  s:=d->'scale';
  IF jsonb_typeof(s) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(s))<>8 OR s->>'unit' IS DISTINCT FROM 'in' THEN RETURN false; END IF;
  FOREACH k IN ARRAY ARRAY['reference_width','reference_height','left','top','right','bottom','print_width'] LOOP
   IF jsonb_typeof(s->k) IS DISTINCT FROM 'number' THEN RETURN false; END IF;
   n:=(s->>k)::numeric;
   IF k IN ('left','top','right','bottom') THEN
    IF n<0 OR n>100 OR n<>round(n,4) THEN RETURN false; END IF;
   ELSE
    IF n<0.001 OR n>2000 OR n<>round(n,3) THEN RETURN false; END IF;
   END IF;
  END LOOP;
  IF (s->>'right')::numeric<=(s->>'left')::numeric OR (s->>'bottom')::numeric<=(s->>'top')::numeric THEN RETURN false; END IF;
  d:=d-'scale';
 END IF;
 IF jsonb_typeof(d) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(d))<>7 THEN RETURN false; END IF;
 FOREACH k IN ARRAY ARRAY['x','y','width','rotation'] LOOP
  IF jsonb_typeof(d->k) IS DISTINCT FROM 'number' THEN RETURN false; END IF;
  n:=(d->>k)::numeric;
  IF n<>round(n,1) OR n<(CASE k WHEN 'rotation' THEN -180 WHEN 'width' THEN 1 ELSE 0 END) OR n>(CASE k WHEN 'rotation' THEN 180 ELSE 100 END) THEN RETURN false; END IF;
 END LOOP;
 IF jsonb_typeof(d->'finish') IS DISTINCT FROM 'string' OR d->>'finish' NOT IN ('colour','engraved-dark','engraved-light') OR jsonb_typeof(d->'family') IS DISTINCT FROM 'string' OR jsonb_typeof(d->'placement') IS DISTINCT FROM 'string' THEN RETURN false; END IF;
 RETURN CASE d->>'family' WHEN 'generic' THEN d->>'placement'='centre' WHEN 'shirt' THEN d->>'placement' IN ('centre','left-chest','back','left-sleeve','right-sleeve') WHEN 'journal' THEN d->>'placement' IN ('centre','bottom-right','upper-left') WHEN 'drinkware' THEN d->>'placement' IN ('centre','front') ELSE false END;
END $$;
CREATE OR REPLACE FUNCTION custom_u_production.catalogue_items_valid_108(items jsonb) RETURNS boolean LANGUAGE plpgsql IMMUTABLE SET search_path='' AS $$
DECLARE x jsonb;k text;v jsonb;view_count int:=0;seen text[];view_key text;
BEGIN
 IF jsonb_typeof(items) IS DISTINCT FROM 'array' THEN RETURN false; END IF;
 IF jsonb_array_length(items) NOT BETWEEN 1 AND 12 THEN RETURN false; END IF;
 FOR x IN SELECT value FROM jsonb_array_elements(items) LOOP
  IF jsonb_typeof(x) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(x-'views'))<>12 THEN RETURN false; END IF;
  FOREACH k IN ARRAY ARRAY['product_id','visual_id'] LOOP
   IF jsonb_typeof(x->k) IS DISTINCT FROM 'string' OR coalesce(x->>k,'') !~ '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$' THEN RETURN false; END IF;
  END LOOP;
  FOREACH k IN ARRAY ARRAY['product_code','name','description','unit','finish','placement'] LOOP
   IF custom_u_production.catalogue_text_108(x->k,CASE k WHEN 'product_code' THEN 40 WHEN 'description' THEN 400 WHEN 'unit' THEN 20 ELSE 160 END,k IN ('product_code','name','unit')) IS DISTINCT FROM true THEN RETURN false; END IF;
  END LOOP;
  IF jsonb_typeof(x->'unit_price') IS DISTINCT FROM 'string' OR coalesce(x->>'unit_price','') !~ '^(0|[1-9][0-9]{0,5})\.[0-9]{2}$'
   OR jsonb_typeof(x->'vat_rate') IS DISTINCT FROM 'string' OR coalesce(x->>'vat_rate','') !~ '^(0|[1-9][0-9]?|100)\.[0-9]{2}$'
   OR (x->>'vat_rate')::numeric>100 OR jsonb_typeof(x->'visual_kind') IS DISTINCT FROM 'string' OR x->>'visual_kind' NOT IN ('image','mockup')
   OR jsonb_typeof(x->'visual_sha256') IS DISTINCT FROM 'string' OR coalesce(x->>'visual_sha256','') !~ '^[a-f0-9]{64}$' THEN RETURN false; END IF;
  IF x ? 'views' THEN
   IF jsonb_typeof(x->'views') IS DISTINCT FROM 'array' THEN RETURN false; END IF;
   IF jsonb_array_length(x->'views') NOT BETWEEN 1 AND 4 THEN RETURN false; END IF;
   view_count:=view_count+jsonb_array_length(x->'views');seen:=ARRAY[]::text[];
   FOR v IN SELECT value FROM jsonb_array_elements(x->'views') LOOP
    IF jsonb_typeof(v) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(v))<>4
     OR custom_u_production.catalogue_text_108(v->'label',60,true) IS DISTINCT FROM true
     OR jsonb_typeof(v->'visual_kind') IS DISTINCT FROM 'string' OR v->>'visual_kind' NOT IN ('image','mockup')
     OR jsonb_typeof(v->'visual_id') IS DISTINCT FROM 'string' OR coalesce(v->>'visual_id','') !~ '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
     OR jsonb_typeof(v->'visual_sha256') IS DISTINCT FROM 'string' OR coalesce(v->>'visual_sha256','') !~ '^[a-f0-9]{64}$' THEN RETURN false; END IF;
    view_key:=(v->>'visual_kind')||':'||(v->>'visual_id');
    IF view_key=ANY(seen) THEN RETURN false; END IF;seen:=array_append(seen,view_key);
   END LOOP;
   FOREACH k IN ARRAY ARRAY['visual_kind','visual_id','visual_sha256'] LOOP
    IF x->'views'->0->k IS DISTINCT FROM x->k THEN RETURN false; END IF;
   END LOOP;
  ELSE view_count:=view_count+1;
  END IF;
 END LOOP;RETURN view_count<=12;
END $$;
CREATE OR REPLACE FUNCTION custom_u_production.catalogue_assets_108(items jsonb,cid uuid,need_active boolean) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE x jsonb;d jsonb;assets jsonb:='{}';img custom_u_production.product_images_106;m custom_u_production.mockups_107;p custom_u_production.products_105;
BEGIN
 IF NOT custom_u_production.catalogue_items_valid_108(items) THEN RETURN jsonb_build_object('error','INVALID_CATALOGUE'); END IF;
 FOR x IN SELECT i.value||v.value FROM jsonb_array_elements(items) i CROSS JOIN LATERAL jsonb_array_elements(coalesce(i.value->'views',jsonb_build_array(i.value))) v LOOP
  SELECT * INTO p FROM custom_u_production.products_105 WHERE id=(x->>'product_id')::uuid FOR SHARE;
  IF NOT FOUND OR (need_active AND (NOT p.active OR p.data->>'code'<>x->>'product_code')) THEN RETURN jsonb_build_object('error','CATALOGUE_SOURCE_UNAVAILABLE'); END IF;
  IF x->>'visual_kind'='image' THEN
   SELECT * INTO img FROM custom_u_production.product_images_106 WHERE id=(x->>'visual_id')::uuid AND product_id=p.id FOR SHARE;
   IF NOT FOUND OR (need_active AND NOT img.active) OR img.sha256<>x->>'visual_sha256' THEN RETURN jsonb_build_object('error','CATALOGUE_SOURCE_UNAVAILABLE'); END IF;
   d:=jsonb_build_object('width',img.width,'height',img.height,'size_bytes',img.size_bytes,'sha256',img.sha256,'content_base64',img.content_base64);
  ELSE
   SELECT * INTO m FROM custom_u_production.mockups_107 WHERE id=(x->>'visual_id')::uuid AND product_id=p.id AND customer_id=cid FOR SHARE;
   IF NOT FOUND OR (need_active AND NOT m.active) OR m.preview->>'sha256'<>x->>'visual_sha256' THEN RETURN jsonb_build_object('error','CATALOGUE_SOURCE_UNAVAILABLE'); END IF;
   d:=m.preview;
  END IF;
  assets:=assets||jsonb_build_object((x->>'visual_kind')||':'||(x->>'visual_id'),d);
 END LOOP;RETURN assets;
END $$;
REVOKE ALL ON FUNCTION custom_u_production.mockup_config_valid_107(jsonb),custom_u_production.catalogue_items_valid_108(jsonb),custom_u_production.catalogue_assets_108(jsonb,uuid,boolean) FROM PUBLIC,anon,authenticated;
