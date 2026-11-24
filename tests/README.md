Run from the repository root:

```sh
python -m pip install -r production_history/requirements.txt pypdf
PYTHONPATH=production_history python -m unittest discover -s tests -p 'test_branding_options_125.py'
npm ci --prefix tests
node tests/test_branding_options_125.mjs
node tests/test_branding_sql_125.mjs
```

The JavaScript checks use JSDOM and an isolated PGlite database. They never connect to the hosted workspace. The Python tests generate synthetic product images and check combined PDF output and retained references.
