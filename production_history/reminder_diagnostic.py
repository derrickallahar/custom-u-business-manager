"""Temporary read-only TEST worker check. Never claims or sends a reminder.

Use python -u reminder_diagnostic.py as the job command while troubleshooting.
The default three-minute hold gives the runtime log viewer time to attach.
Use --once for a local check without the hold. No secret values, customer data,
raw exceptions, provider response bodies, or environment dumps are printed.
"""
import argparse
import importlib
import os
import re
import time


def emit(label, result):
    print(label + ': ' + result, flush=True)


def check_environment():
    good = True
    patterns = (
        ('CUSTOMU_PRODUCTION_PUBLISHABLE_KEY', r'sb_publishable_[A-Za-z0-9_-]+'),
        ('RESEND_API_KEY', r're_[A-Za-z0-9_-]{10,200}'),
        ('CUSTOMU_EMAIL_SIGNING_SECRET', r'[a-f0-9]{64}'),
    )
    for name, pattern in patterns:
        value = os.getenv(name, '')
        if not value:
            result = 'MISSING'
        elif not re.fullmatch(pattern, value):
            result = 'INVALID_FORMAT'
        else:
            result = 'FORMAT_OK'
        emit(name, result)
        good = good and result == 'FORMAT_OK'
    # This diagnostic deliberately requires the explicit TEST configuration.
    for name, expected in (
        ('CUSTOMU_REMINDER_WORKER_ENABLED', '1'),
        ('CUSTOMU_REMINDER_MODE', 'test'),
        ('CUSTOMU_EMAIL_TEST_MODE', '1'),
        ('CUSTOMU_REMINDER_LIVE_ENABLED', '0'),
    ):
        result = 'OK' if os.getenv(name) == expected else 'CHECK_TEST_SETTING'
        emit(name, result)
        good = good and result == 'OK'
    return good


SAFE_ERRORS = {
    'REMINDER_SERVER_AUTH_REQUIRED': 'SIGNING_KEY_OR_CLOCK_REJECTED',
    'REMINDER_LIVE_DISABLED': 'TEST_CONFIGURATION_REQUIRED',
    'REMINDER_RESPONSE_INVALID': 'INVALID_DATABASE_RESPONSE',
    'SIGN_IN_OR_ACCESS_REJECTED': 'DATABASE_ACCESS_REJECTED',
    'PROVIDER_REQUEST_FAILED': 'DATABASE_REQUEST_FAILED',
    'PROVIDER_UNAVAILABLE': 'DATABASE_UNAVAILABLE',
    'PLEASE_WAIT_AND_TRY_AGAIN': 'DATABASE_RATE_LIMITED',
    'RESPONSE_TOO_LARGE': 'DATABASE_RESPONSE_TOO_LARGE',
}


def diagnose():
    emit('CUSTOM_U_REMINDER_DIAGNOSTIC', 'READ_ONLY_TEST_NO_EMAIL')
    if not check_environment():
        emit('RESULT', 'ENVIRONMENT_CHECK_FAILED')
        return 1
    modules = {}
    for name in ('email_delivery', 'production_app', 'reminder_worker', 'reminder_rules'):
        try:
            modules[name] = importlib.import_module(name)
        except Exception:
            emit('IMPORT_' + name.upper(), 'FAILED_CHECK_DEPENDENCIES_AND_SOURCE')
            return 1
        emit('IMPORT_' + name.upper(), 'OK')
    try:
        config = modules['email_delivery'].Settings()
    except Exception:
        emit('EMAIL_ADDRESS_SETTINGS', 'INVALID_CHECK_FROM_REPLY_TO_TEST_RECIPIENT')
        return 1
    if not config.ready:
        emit('EMAIL_SETTINGS', 'NOT_READY')
        return 1
    emit('EMAIL_ADDRESS_SETTINGS', 'OK')
    try:
        provider = modules['production_app'].Supabase(os.environ['CUSTOMU_PRODUCTION_PUBLISHABLE_KEY'])
        runner = modules['reminder_worker'].Runner(provider, config=config)
        # Only this read-only operation is permitted. Do not call Runner.run().
        state = runner.call({'op': 'state', 'mode': 'test'})
    except Exception as exc:
        # Match only fixed internal codes. Never print arbitrary exception text.
        code = getattr(exc, 'code', None)
        if not isinstance(code, str):
            code = exc.args[0] if len(exc.args) == 1 and isinstance(exc.args[0], str) else ''
        emit('DATABASE_STATE', SAFE_ERRORS.get(code, 'WORKER_STATE_CHECK_FAILED'))
        return 1
    emit('DATABASE_AUTH_AND_TEST_STATE', 'OK')
    try:
        cfg = modules['reminder_rules'].settings(state['settings'])
    except Exception:
        emit('SAVED_TEST_SCHEDULE', 'INVALID_SAVED_SETTINGS')
        return 1
    if state.get('needs_review'):
        emit('SAVED_TEST_SCHEDULE', 'REVIEW_AND_SAVE_IN_APP_REQUIRED')
    else:
        emit('SAVED_TEST_SCHEDULE', 'ENABLED' if cfg['enabled'] else 'PAUSED')
    emit('RESULT', 'READ_ONLY_CHECK_PASSED')
    emit('RESEND_DELIVERY', 'NOT_TESTED_NO_EMAIL_SENT')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Exit immediately after checking.')
    args = parser.parse_args(argv)
    try:
        result = diagnose()
    except Exception:
        emit('RESULT', 'DIAGNOSTIC_INTERNAL_ERROR_NO_DETAILS_LOGGED')
        result = 1
    if not args.once:
        emit('LOG_WINDOW', 'OPEN_FOR_THREE_MINUTES_NO_FURTHER_REQUESTS')
        for _ in range(12):
            time.sleep(15)
            emit('LOG_WINDOW', 'CHECK_PASSED' if result == 0 else 'CHECK_FAILED_SEE_ABOVE')
    emit('DIAGNOSTIC_FINISHED', 'PASS' if result == 0 else 'FAIL')
    return result


if __name__ == '__main__':
    raise SystemExit(main())
