Run from the repository root:

```sh
python -m pip install -r production_history/requirements.txt pypdf
PYTHONPATH=production_history python -m unittest discover -s tests -p 'test_branding_options_125.py'
npm ci --prefix tests
node tests/test_branding_options_125.mjs
node tests/test_branding_sql_125.mjs
node tests/test_mockup_preview_126.mjs
```

The JavaScript checks use JSDOM and an isolated PGlite database. They never connect to the hosted workspace. The Python tests generate synthetic product images and check combined PDF output and retained references.


## Training 127

Run from the repository root, with the application Python requirements available:

```sh
node tests/test_training_sql_127.mjs
node tests/test_training_ui_127.mjs
PYTHONPATH=production_history python -m unittest discover -s tests -p 'test_training_127.py'
```

The SQL test replays the migration in isolated PGlite, exercises real permission and scoring boundaries, and writes a temporary backup fixture for the Python validation test. The UI test loads the real training page and script in JSDOM with simulated network outcomes. Python verifies served routes, authentication, origin checks, answer-key privacy, PDF branding, CSV escaping and backup integrity. These tests create no live staff training results.
