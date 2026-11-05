"""Session-bound, expiring previews; only explicit confirmation can create rows."""
import hashlib
import json
import secrets
import threading
import time
from flask import request, jsonify
from customer_import import parse_csv, preview
from reviewed_import import make_plan, canonical, reviewed_preview, mark_completed_resolutions


def install(app, provider, session, enabled, root, failure, reviewed=False):
    plans = {}
    lock = threading.Lock()
    suffix = 'reviewed' if reviewed else 'standard'
    page_path = '/customers/reviewed-import' if reviewed else '/customers/import'
    api_path = '/api/customers/reviewed-import' if reviewed else '/api/customers/import'
    rpc_path = '/rest/v1/rpc/custom_u_crm_reviewed_096' if reviewed else '/rest/v1/rpc/custom_u_crm_import_095'

    def gate():
        rec, me = session()
        if not enabled:
            raise failure('CUSTOMERS_NOT_ENABLED', 409)
        if me.get('role') != 'admin':
            raise failure('ACCESS_DENIED', 403)
        owner = hashlib.sha256(rec['token'].encode()).hexdigest()
        return rec, owner

    def rpc(rec, payload):
        raw = provider.call(rpc_path, rec['token'],
                            {'payload': payload}, limit=8*1024*1024)
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise failure('INVALID_PROVIDER_RESPONSE')
        if 'error' in result:
            code = result['error']
            raise failure(code, 403 if code == 'ACCESS_DENIED' else 409)
        if provider.access(rec['token']).get('role')!='admin':raise failure('ACCESS_DENIED',403)
        return result

    @app.get(page_path, endpoint='import_page_'+suffix)
    def import_page():
        return app.response_class((root/('static/reviewed-import.html' if reviewed else 'static/import.html')).read_bytes(), mimetype='text/html')

    def import_script():
        return app.response_class((root/'static/import.js').read_bytes(), mimetype='text/javascript')
    if not reviewed:
        app.add_url_rule('/customer-import.js', 'customer_import_script', import_script)

    @app.post(api_path+'/preview', endpoint='import_preview_'+suffix)
    def import_preview():
        rec, owner = gate()
        # Larger body allowance applies ONLY here, after authentication.
        request.max_content_length = 1024*1024
        body = request.get_json()
        if not isinstance(body, dict) or set(body) != {'csv'}:
            raise failure('INVALID_REQUEST', 400)
        try:
            parsed = parse_csv(body['csv'])
            plan = make_plan(parsed) if reviewed else None
        except (ValueError, UnicodeError) as e:
            code = str(e) if isinstance(e, ValueError) and str(e).isupper() else 'CSV_FORMAT_INVALID'
            raise failure(code, 400) from None
        inspect_body = {'op': 'inspect'}
        if reviewed:
            inspect_body['plan_json'] = canonical(plan)
        state = rpc(rec, inspect_body)
        if not isinstance(state.get('records'), list) or not isinstance(state.get('stamp'), str):
            raise failure('INVALID_PROVIDER_RESPONSE')
        if reviewed:
            if state.get('resolution_status') not in ('pending', 'complete'):
                raise failure('INVALID_PROVIDER_RESPONSE')
            report, items = reviewed_preview(parsed, plan, state)
        else:
            report, items = preview(parsed, state['records'])
            mark_completed_resolutions(report, parsed, state['records'])
        session()  # Re-check live permission before returning private records.
        token = secrets.token_urlsafe(32)
        with lock:
            for k in [k for k, v in plans.items() if v['until'] <= time.time() or v['owner'] == owner]:
                plans.pop(k)
            if len(plans) >= 8:
                raise failure('IMPORT_BUSY', 429)
            plans[token] = {'owner': owner, 'until': time.time()+600, 'stamp': state['stamp'],
                            'items': items, 'report': report, 'running': False, 'result': None,
                            'plan_json': canonical(plan) if reviewed else None}
        return jsonify(preview_id=token, expires_in=600, report=report)

    @app.post(api_path+'/commit', endpoint='import_commit_'+suffix)
    def import_commit():
        rec, owner = gate()
        body = request.get_json()
        if not isinstance(body, dict) or set(body) != {'preview_id', 'confirm'} or body['confirm'] is not True or not isinstance(body['preview_id'], str):
            raise failure('CONFIRM_PREVIEW_REQUIRED', 400)
        with lock:
            plan = plans.get(body['preview_id'])
            if not plan or plan['owner'] != owner or plan['until'] <= time.time():
                raise failure('PREVIEW_EXPIRED', 409)
            if plan['result'] is not None:
                return jsonify(plan['result'])
            if plan['running']:
                raise failure('IMPORT_BUSY', 429)
            if not plan['items']:
                raise failure('NOTHING_READY_TO_IMPORT', 409)
            plan['running'] = True
        try:
            payload = {'op': 'commit', 'stamp': plan['stamp']}
            payload['plan_json' if reviewed else 'items'] = plan['plan_json'] if reviewed else plan['items']
            outcome = rpc(rec, payload)
            expected_c = plan['report']['counts']['ready']
            expected_p = plan['report']['counts']['contacts_to_add']
            already = reviewed and outcome.get('already_completed') is True and outcome.get('customers_added') == 0 and outcome.get('contacts_added') == 0
            if not already and (outcome.get('customers_added') != expected_c or outcome.get('contacts_added') != expected_p):
                raise failure('IMPORT_RESULT_UNCONFIRMED')
            outcome['source_sha256'] = plan['report']['source_sha256']
            outcome['held_for_review'] = plan['report']['counts']['review']
            with lock:
                plan['result'] = outcome
            return jsonify(outcome)
        finally:
            with lock:
                plan['running'] = False
