# Custom U Business Manager v0.7.7 — DigitalOcean HTTPS cloud staging

**Purpose:** Deploy the fictional-only v0.7.6 multi-user application with individual quote and invoice permissions to DigitalOcean App Platform, while keeping your working Windows application unchanged.

**NO REAL CUSTOMERS, NO REAL STAFF EMAILS, NO REAL INVOICES OR PAYMENTS.** This is still a cloud *test* application, not a production ShopVox replacement. Its internet address is public, but its business screens require pilot login. This does not count as a private network or a comprehensive security review.

## What changes from v0.7.6

- Runs as a Python web service in DigitalOcean App Platform at a provided HTTPS address, rather than on localhost.
- Uses **the existing** Supabase PostgreSQL *fictional* schema `custom_u_permissions_pilot_076`; no migration or new setup is required.
- Uses the **existing fictional v0.7.6 administrator and staff accounts** and their tested per-user quote, invoice, payment and production permissions.
- Secure `HttpOnly`, `SameSite=Strict` HTTPS session cookies; host/origin enforcement; CSRF checks; no real-data import or customer emails.
- Reads the database connection string and CA certificate only from DigitalOcean **encrypted runtime environment variables**; does not write them to repository files.
- `/healthz` endpoint for DigitalOcean health checks; one low-cost web service instance only.

## 1. Prepare the GitHub repository

1. Extract this ZIP to a new folder on your Windows computer.
2. Open your **PRIVATE** GitHub repository: `derrickallahar/custom-u-business-manager`.
3. Use **Add file → Upload files** on GitHub; upload the *contents* of this extracted folder **including the `static` folder**, so `requirements.txt`, `cloud_main.py`, and `cloud_server.py` appear at the **repository root**. Do not upload the ZIP itself as your only repository file.
4. Choose **Commit directly to the `main` branch**, then confirm that the GitHub Code tab shows `requirements.txt` at the top level.
5. IMPORTANT: Never upload your PostgreSQL URI, database password, CA certificate, private .env, existing database backups, real artwork, customer CSVs, or production SQLite files. `.gitignore` provides an extra safeguard, but review files yourself before uploading.

If GitHub browser upload does not let you preserve folders, use GitHub Desktop to copy the extracted folder contents into a local checkout, then commit and push them. `static/index.html`, `static/app.js`, and `static/style.css` must retain their `static/` folder path.

## 2. DigitalOcean App Platform configuration

Open https://cloud.digitalocean.com/apps → **Create App**.

- Provider: GitHub
- Repository: `derrickallahar/custom-u-business-manager`
- Branch: `main`
- Source directory: **leave empty**
- Autodeploy: **OFF** for initial testing
- Component: **Web Service**, Python (not a static site, Spaces, or Droplet)
- Run command: `python cloud_main.py`
- HTTP port: `8080`
- Health check path: `/healthz` (if configurable; otherwise the default TCP health check is acceptable)
- Size: the smallest available **Basic shared** instance (typically 512 MB), count **1**. Verify the billing preview before creating the app.
- Region: a region convenient for Nassau and close to your Supabase project if possible.

DigitalOcean should detect the repository because `requirements.txt` is at the **root**. If it still says *No components detected*, check that `requirements.txt` actually appears in GitHub's `main` branch (not inside a wrapper folder).

## 3. Add FIVE runtime environment variables

Add these in DigitalOcean **App Platform → Environment Variables** before deploying. **Set the two confidential/credential values to Encrypt and RUN TIME**. The two confirmation values and origin are nonsecret; set them to RUN TIME as well.

| Key | Value | Encryption |
| --- | --- | --- |
| `CUSTOMU_STAGING_ONLY` | `YES_FICTIONAL_ONLY` | optional |
| `CUSTOMU_ENABLE_CLOUD` | `RUN_FICTIONAL_PILOT` | optional |
| `CUSTOMU_PUBLIC_ORIGIN` | `${APP_URL}` | optional (DigitalOcean bindable variable) |
| `CUSTOMU_STAGING_DATABASE_URL` | Your previously verified **Supabase STAGING Session pooler URI** | **Encrypt** |
| `CUSTOMU_PG_CA_B64` | Base64 of your verified Supabase CA certificate | **Encrypt** |

**How to make the CA Base64:** Double-click `ENCODE_CA_CERT_WINDOWS.bat` in the extracted folder. Paste the full path to the certificate that worked in v0.7.6 (for example `C:\Users\derri\Downloads\prod-ca-2021.crt`). It copies Base64 text to your Windows clipboard. Paste that into DigitalOcean as `CUSTOMU_PG_CA_B64`; **never** paste it into GitHub. This is a *CA certificate*, not a client private key.

**Crucial:** Do **NOT** enter the actual Supabase connection URI or password into this README, `.env.example`, GitHub issues, or chat. DigitalOcean environment variables are decrypted in the runtime container, so grant App Platform Console/code-editing access only to trusted people.

DigitalOcean supports `${APP_URL}` as an app-level bindable variable. If it does not resolve correctly, edit `CUSTOMU_PUBLIC_ORIGIN` to the **exact** `https://...ondigitalocean.app` URL DigitalOcean assigns you, with no trailing slash; then redeploy.

## 4. Deploy and verify

1. Check the final monthly cost preview. **DigitalOcean starts charging when you create/activate the web service.**
2. Click **Create App / Deploy** only after you've added all runtime variables.
3. Wait for deployment to become healthy; open the provided HTTPS URL.
4. The login should appear. Sign in using your **existing fictional v0.7.6** credentials, e.g. `admin@example.invalid` and its password. **Never share your password or session cookie in chat**.
5. Check Customers, Catalogs, Quotes, Invoices and Production. Your v0.7.6 fictional transactions should appear.
6. Log in as a separate fictional Production staff user in an InPrivate window; verify the individual invoice permission override still applies.
7. Change a fictional production stage, refresh the other window, and verify persistence.
8. Check that the existing localhost v0.7.6 still opens on `http://127.0.0.1:8776` and remains unaffected.

## Troubleshooting

- **“No components detected”**: `requirements.txt` missing from the repository root; branch is wrong; repository permissions missing.
- **App build success but service fails to start**: Check DigitalOcean app logs for error codes. `FICTIONAL_STAGING_CONFIRMATION_REQUIRED`, `PUBLIC_HTTPS_ORIGIN_REQUIRED`, `CA_CERTIFICATE_B64_REQUIRED`, `SUPABASE_STAGING_SESSION_POOLER_URI_REQUIRED`, etc. mean a required environment variable is missing or wrong. Do **not** send screenshots containing the variable values.
- **Health check failing**: Confirm run command `python cloud_main.py` and port `8080`.
- **`INVALID_HOST`**: `CUSTOMU_PUBLIC_ORIGIN` is not the exact assigned HTTPS app URL.
- **`NON_FICTIONAL_*_RECORD_DETECTED`**: The public pilot intentionally stops if nonfictional records are present. Do not bypass the check; first investigate the **staging** database offline.
- **Login fails**: Use **v0.7.6** fictional staff credentials; this release does not create new user accounts.
- **Database connection error**: Confirm you're using Session pooler, not a URL with a password placeholder, and the matching CA certificate. Never paste credentials in chat.
- **`CUSTOMU_PUBLIC_ORIGIN` stays literally `${APP_URL}`**: In DigitalOcean edit the environment variable to its actual issued HTTPS URL and redeploy.

## Important boundaries

- This release does not provide production-grade authentication, MFA, encrypted artwork/asset storage, malware scanning, independent backups, email delivery, password reset, external audit or an isolated private network.
- Do not turn on customer email reminders or add production customer data.
- For the actual business rollout, perform a security review, set up MFA / identity provider, private file storage, backups, monitoring, credential rotation, and a deliberate real-data migration.
- This deployment reuses the v0.7.6 synthetic schema; it will NOT alter your v0.7.1 daily-use SQLite app, v0.7.4 pilot, v0.7.5 pilot, or v0.7.3 synthetic verification schema.
