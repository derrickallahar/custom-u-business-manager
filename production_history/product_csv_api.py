"""Administrator-only CSV previews; explicit commit creates new products atomically."""
import hashlib
import json
import secrets
import threading
import time
from flask import jsonify, request
from product_csv import parse_csv, preview, money


def install(app, provider, session, enabled, root, failure):
    plans = {}
    lock = threading.Lock()
    path = '/api/products/csv-import'

    def gate():
        rec, me = session()
        if not enabled:
            raise failure('CUSTOMERS_NOT_ENABLED', 409)
        if me.get('role') != 'admin':
            raise failure('ACCESS_DENIED', 403)
        return rec, hashlib.sha256(rec['token'].encode()).hexdigest()

    def rpc(rec, payload):
        raw = provider.call('/rest/v1/rpc/custom_u_product_csv_1141', rec['token'],
                            {'payload': payload}, limit=8*1024*1024)
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in result:
            code = result['error']
            raise failure(code, 403 if code == 'ACCESS_DENIED' else 409)
        gate()
        return result

    @app.get('/products/csv-import')
    def product_csv_page():
        return app.response_class((root/'static/product-csv.html').read_bytes(), mimetype='text/html')

    @app.get('/product-csv.js')
    def product_csv_script():
        return app.response_class((root/'static/product-csv.js').read_bytes(), mimetype='text/javascript')

    @app.post(path+'/preview')
    def product_csv_preview():
        rec, owner = gate()
        request.max_content_length = 3*1024*1024
        body = request.get_json()
        if not isinstance(body, dict) or set(body) != {'csv'}:
            raise failure('INVALID_REQUEST', 400)
        try:
            parsed = parse_csv(body['csv'])
        except (ValueError, UnicodeError) as e:
            raise failure(str(e) if isinstance(e, ValueError) else 'CSV_FORMAT_INVALID', 400) from None
        state = rpc(rec, {'op': 'inspect'})
        if not isinstance(state.get('records'), list) or not isinstance(state.get('stamp'), str):
            raise failure('INVALID_PROVIDER_RESPONSE')
        report = preview(parsed, state['records'])
        token = secrets.token_urlsafe(32)
        with lock:
            for k in list(plans):
                p = plans[k]
                if not p['running'] and (p['until'] <= time.time() or p['owner'] == owner):
                    plans.pop(k)
            if len(plans) >= 8:
                raise failure('IMPORT_BUSY', 429)
            plans[token] = {'owner': owner, 'until': time.time()+1800, 'report': report,
                            'stamp': state['stamp'], 'result': None, 'running': False,
                            'selection': None}
        return jsonify(preview_id=token, expires_in=1800, report=report)

    @app.post(path+'/commit')
    def product_csv_commit():
        rec, owner = gate()
        request.max_content_length = 128*1024
        body = request.get_json()
        if (not isinstance(body, dict) or set(body) != {'preview_id', 'selections', 'confirm', 'prices_bsd_before_vat'}
                or body['confirm'] is not True or body['prices_bsd_before_vat'] is not True
                or not isinstance(body['preview_id'], str) or not isinstance(body['selections'], list)
                or not 1 <= len(body['selections']) <= 250):
            raise failure('CONFIRM_PREVIEW_REQUIRED', 400)
        with lock:
            plan = plans.get(body['preview_id'])
            if not plan or plan['owner'] != owner or plan['until'] <= time.time():
                raise failure('PREVIEW_EXPIRED', 409)
            candidates = {r['row']: r for r in plan['report']['rows'] if r['status'] == 'candidate'}
            selected = set()
            items = []
            for chosen in body['selections']:
                if (not isinstance(chosen, dict) or set(chosen) != {'row', 'vat_rate'}
                        or type(chosen['row']) is not int or chosen['row'] not in candidates
                        or chosen['row'] in selected):
                    raise failure('INVALID_SELECTION', 400)
                selected.add(chosen['row'])
                try:
                    vat = money(chosen['vat_rate'], 100)
                except ValueError:
                    raise failure('VAT_REVIEW_REQUIRED', 400) from None
                candidate = candidates[chosen['row']]
                items.append({'id': candidate['id'], 'data': {**candidate['data'], 'vat_rate': vat}})
            items.sort(key=lambda x: x['id'])
            if plan['result'] is not None:
                if plan['selection'] != items:
                    raise failure('PREVIEW_ALREADY_USED', 409)
                return jsonify(plan['result'])
            if plan['running']:
                raise failure('IMPORT_BUSY', 429)
            plan['running'] = True
        try:
            result = rpc(rec, {'op': 'commit', 'confirm': True, 'stamp': plan['stamp'], 'items': items})
            if result.get('products_added') != len(items):
                raise failure('IMPORT_RESULT_UNCONFIRMED')
            result['source_sha256'] = plan['report']['source_sha256']
            result['source_rows'] = sorted(selected)
            with lock:
                plan['result'] = result
                plan['selection'] = items
            return jsonify(result)
        finally:
            with lock:
                plan['running'] = False
