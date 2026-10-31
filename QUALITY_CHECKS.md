# v0.7.7 local verification

Implemented using the actual verified v0.7.6 source code, not a mock UI.

- 14 isolated local HTTP/config/permission unit tests: **PASS**
- Python syntax compilation: **PASS**
- JavaScript syntax (`node --check`): **PASS** where Node is installed
- Tested host/origin mismatch 403, unauthenticated financial API 401, POST content-type 415, HTTPS-only origin validation, secure session cookie, fictional-only permission defaults
- DigitalOcean Python buildpack detection file `requirements.txt` included at repo root
- `runtime.txt` chooses Python 3.13.17; single service instance; `PORT` supported
- Public cloud will not start without explicit fictional-data consent, HTTPS origin, Supabase Session pooler URI, CA certificate, and existing v0.7.6 fictional schema
- Supabase connection uses `sslmode=verify-full` and the supplied CA chain
- Database credentials and password are NOT in the release

**NOT YET TESTED:** live App Platform deployment, actual GitHub repository upload, real browser behavior behind DigitalOcean's HTTPS proxy, cloud-to-Supabase connectivity, or operational performance. These checks must be done after you deploy. The local tests do not certify production security.
