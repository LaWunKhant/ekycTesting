# MoonKYC (Django) - Developer Runbook

This README is the single source of truth for setup, runtime, troubleshooting, and recent architecture decisions.

Need a faster team handoff doc? See `DEVELOPER_OPERATIONS_GUIDE.md`.
Japanese-style design document is available at `SYSTEM_DESIGN_JP.md`.

## 1) Project Overview
MoonKYC is a Django-based eKYC backend with:
- Platform admin workspace (`/admin/dashboard/`)
- Customer verification flow (document capture, liveness, selfie, submit)
- Manual review queue for final approval/rejection
- AI assist (face similarity + optional Mistral OCR) with strict human-in-the-loop final decision
- Tenant-backed customer/session isolation for verification routing

Core apps:
- `accounts`: super admin authentication, login/logout/password change
- `kyc`: tenants/customers/sessions, verification APIs, review workflows, OCR queue integration

## 2) Stack
- Python 3.10+
- Django
- MySQL or Postgres
- OpenCV + NumPy
- DeepFace (face extraction/verification)
- Mistral OCR API (asynchronous queue-based extraction)
- Tailwind (template-level CDN use)

## 3) Important Files
- `manage.py`
- `myproject/settings.py`
- `myproject/urls.py`
- `accounts/models.py`
- `accounts/views.py`
- `accounts/templates/registration/password_change.html`
- `kyc/models.py`
- `kyc/views.py`
- `kyc/api_views.py`
- `kyc/services/card_physical_check.py`
- `kyc/services/mistral_ai.py`
- `kyc/templates/kyc/admin_session_detail.html`
- `kyc/static/js/main.js`

## 4) Local Setup
### 4.1 Create virtualenv
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4.2 Install dependencies
```bash
pip install -r requirements.txt
```

### 4.3 Configure `.env`
```bash
cp .env.example .env
```

Note: `.env` values for `PUBLIC_BASE_URL` and `EMAIL_*` are loaded with priority over stale shell exports to keep links/SMTP behavior deterministic.

Required database fields:
```env
DB_ENGINE=mysql
DB_NAME=ekyc
DB_USER=root
DB_PASSWORD=
DB_HOST=127.0.0.1
DB_PORT=3306
```

For Render Postgres you can instead set:
```env
DB_ENGINE=postgres
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
```

### 4.4 Migrate and run
```bash
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### 4.5 Optional ngrok for mobile testing
```bash
ngrok http 8000
```
Set latest URL in `.env`:
```env
PUBLIC_BASE_URL=https://<your-ngrok>.ngrok-free.app
```

## 5) Environment Variables
### 5.1 Database
- `DB_ENGINE` (`mysql` or `postgres`)
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `DATABASE_URL`
- `DB_SSL_MODE`

### 5.2 Core app
- `SECRET_KEY`
- `DEBUG`
- `PUBLIC_BASE_URL`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `SECURE_SSL_REDIRECT`
- `SESSION_COOKIE_SECURE`
- `CSRF_COOKIE_SECURE`
- `SERVE_MEDIA_FILES`
- `MEDIA_ROOT`
- `EMAIL_HOST`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_PORT`
- `EMAIL_USE_TLS`
- `DEFAULT_FROM_EMAIL`

### 5.3 Mistral OCR / AI assist
- `MISTRAL_API_KEY`
- `MISTRAL_BASE_URL` (default `https://api.mistral.ai/v1`)
- `MISTRAL_OCR_MODEL` (default `mistral-ocr-latest`)
- `MISTRAL_REQUEST_TIMEOUT` (default `25`)
- `MISTRAL_SSL_VERIFY` (default `true`)
- `MISTRAL_CA_BUNDLE` (optional cert bundle path)
- `MISTRAL_ENABLE_OCR` (default `true`)
- `MISTRAL_ENABLE_BACK_OCR` (default `false`)
- `MISTRAL_MAX_RETRIES` (default `2`, immediate request-level retries)
- `MISTRAL_RETRY_BASE_SECONDS` (default `1.0`)
- `MISTRAL_MIN_INTERVAL_SECONDS` (default `1.0`, throttle between API calls)
- `MISTRAL_QUEUE_MAX_ATTEMPTS` (default `6`, queue-level retries on 429)
- `MISTRAL_QUEUE_RETRY_BASE_SECONDS` (default `30.0`, exponential backoff base)

### 5.4 Gunicorn / Render runtime
- `WEB_CONCURRENCY` (default `1`)
- `GUNICORN_TIMEOUT` (default `120`)

## 6) Authentication and Account Flows
- Login: `/accounts/login/`
- Logout: `/accounts/logout/`
- Password change: `/accounts/password/change/`

Only super admin users can sign in to this Django app. Tenant-facing dashboard flows were removed from this repo and are handled externally.
Password changes use Django `PasswordChangeForm` and keep session active via `update_session_auth_hash`.

## 7) Route Map
### 7.1 Platform Admin
- `/admin/dashboard/`
- `/admin/users/`
- `/admin/tenants/<uuid>/...`
- `/review/`

### 7.2 Customer Verification
- `/customer/start/`
- `/verify/?tenant_slug=<slug>&customer_id=<id>`
- `/verify/start/<token>/`
- `/liveness?session_id=<uuid>`

### 7.3 API
- `/session/start`
- `/capture/`
- `/session/submit`
- `/verify/submit/`
- `/liveness-result`
- `/start-liveness/`
- `/check-liveness/`
- `/cancel-liveness/`

## 8) Verification Flow (Current)
Frontend (`kyc/static/js/main.js`):
1. Start session (`/session/start`)
2. Capture document front/back
3. Capture tilt/thickness frames
4. Run liveness
5. Capture selfie
6. Submit (`/session/submit`)
7. Verify (`/verify/submit/`)

Backend (`verify_kyc`):
1. Resolve session/tenant
2. Extract face from front ID image
3. Compare with selfie using DeepFace models
4. Compute identity assist (initial fallback mode without OCR)
5. Run physical card checks
6. Persist session verification metrics
7. Queue OCR job if enabled
8. Return response immediately (customer does not wait for OCR)

Important:
- Customer completion step intentionally does not expose internal AI metrics.
- Final `review_status` is manual only (`pending/approved/rejected/needs_info`).

## 9) Async OCR Queue Behavior
Implemented in `kyc/services/mistral_ai.py`.

- Uses a background worker thread with a priority queue.
- Queue supports delayed retries.
- 429 responses trigger queue re-try with exponential backoff.
- `document_data.ai_document_extraction.status` transitions:
  - `queued`
  - `rate_limited_retry`
  - `completed`
- `document_data.ai_document_extraction.address_summary` now stores merged address output:
  - `selected_address`
  - `selected_source` (`front` or `back`)
  - `has_conflict` (true when front/back addresses differ)
  - `candidates` (deduplicated list with source and confidence)
- OCR `front/back.extracted` also includes structured address fields:
  - `address` (full address candidate; never postal-code-only)
  - `postal_code`
  - `prefecture`
  - `city`
  - `street_address`
  - `address_raw`
  - `residence_status`
- OCR `front/back` metadata now includes:
  - `raw_confidence` (provider reported score)
  - `confidence` (post-validation adjusted score)
  - `quality_flags` (`missing_core_fields`, `address_missing`, `address_only_postal`, `address_low_detail`, `confidence_penalty`)

When OCR completes, worker updates:
- `document_data.ai_document_extraction`
- `document_data.identity_assist` (recomputed in `with_ocr` mode)
- `identity_assist.recommendation` can be elevated to `needs_info_manual_review` when OCR quality issues indicate missing critical data

## 10) Reviewer UX
`kyc/templates/kyc/admin_session_detail.html` includes:
- Click-to-preview large images in a modal
- `Open in new tab` fallback for full-size image
- `Esc` and outside-click modal close

## 11) Public URL / ngrok Behavior
Verification links remain backed by `VerificationLink` records and `/verify/start/<token>/`.
If an external tenant workspace generates links against the shared database, this Django app continues to resolve them.

Set `PUBLIC_BASE_URL` to the public HTTPS origin that customers should open (ngrok, Render, or your custom domain).

## 12) Render Deployment
This repo includes a Docker-based Render setup in [`render.yaml`](/Users/cipc-002/Herd/PythonProject/render.yaml), [`Dockerfile`](/Users/cipc-002/Herd/PythonProject/Dockerfile), and [`bin/render-start.sh`](/Users/cipc-002/Herd/PythonProject/bin/render-start.sh).

Use a Render `Web Service`, not a `Private Service` or `Background Worker`, because customer phones need a public HTTPS URL.

Why Docker here:
- DeepFace / TensorFlow / OpenCV are more reliable with a controlled Linux image than with Render's native Python runtime.
- The project uses native database drivers, so the runtime includes both MySQL and Postgres support.

Important limitation:
- This app writes captured verification images to `MEDIA_ROOT`.
- Render services have an ephemeral filesystem unless you attach a persistent disk.
- For this project, use at least the `Starter` plan and attach the disk configured in [`render.yaml`](/Users/cipc-002/Herd/PythonProject/render.yaml).

### 12.1 Recommended Render service settings
- Service type: `Web Service`
- Runtime: `Docker`
- Plan: `Starter` or higher
- Region: `Virginia` (or the region nearest your Render Postgres database)
- Health Check Path: `/healthz/`
- Disk mount path: `/var/data/moonkyc/media`
- Disk size: `5 GB` to start

### 12.2 Required environment variables on Render
```env
DB_ENGINE=postgres
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
SECRET_KEY=...
DEBUG=false
PUBLIC_BASE_URL=https://<your-service>.onrender.com
ALLOWED_HOSTS=<your-service>.onrender.com
CSRF_TRUSTED_ORIGINS=https://<your-service>.onrender.com
MEDIA_ROOT=/var/data/moonkyc/media
SERVE_MEDIA_FILES=true
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

Optional:
```env
MISTRAL_API_KEY=...
WEB_CONCURRENCY=1
GUNICORN_TIMEOUT=120
ADMIN_EMAIL=owner@gmail.com
ADMIN_PASSWORD=pass1234
ADMIN_FIRST_NAME=Owner
```

If you prefer not to use `DATABASE_URL`, set the Postgres fields individually:
```env
DB_ENGINE=postgres
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
DB_HOST=...
DB_PORT=5432
```

Set `DB_SSL_MODE=require` only if you are connecting via Render's external Postgres URL or your provider requires TLS. For a Render web service in the same region and workspace, use the internal URL from the database's Connect menu whenever possible.

### 12.3 Render start behavior
The container starts with [`bin/render-start.sh`](/Users/cipc-002/Herd/PythonProject/bin/render-start.sh), which runs:
1. `python manage.py migrate --noinput`
2. `python manage.py create_admin --force` if `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set
3. `gunicorn myproject.wsgi:application --bind 0.0.0.0:$PORT`

### 12.4 Deploy steps
1. Push this repo to GitHub/GitLab.
2. In Render, create a new `Web Service`.
3. Select this repository.
4. Let Render read [`render.yaml`](/Users/cipc-002/Herd/PythonProject/render.yaml) or configure the same values manually.
5. Fill in the Postgres and secret environment variables.
6. Confirm the persistent disk mount path is `/var/data/moonkyc/media`.
7. Deploy.

### 12.5 Post-deploy checklist
- Open `https://<your-service>.onrender.com/healthz/` and confirm it returns `ok`.
- Confirm the Django login page opens over HTTPS.
- Confirm a verification link generated by your Laravel side uses `PUBLIC_BASE_URL`.
- Complete one test session and verify uploaded images remain available after a redeploy.

## 13) Troubleshooting
### 13.1 `ERR_NGROK_3200`
Meaning: ngrok endpoint is offline (dead tunnel URL).
Fix: run ngrok again, update `PUBLIC_BASE_URL`, restart server, resend link.

### 13.2 Mistral SSL error
Example: `SSLCertVerificationError`.
Fix options:
- Ensure certifi installed
- Set `MISTRAL_CA_BUNDLE` to a valid CA file path
- Keep `MISTRAL_SSL_VERIFY=true` (preferred)

### 13.3 Mistral 429 (rate limit)
Meaning: quota/throughput exceeded.
System now retries automatically in queue.
To reduce pressure:
- Keep `MISTRAL_ENABLE_BACK_OCR=false`
- Increase `MISTRAL_MIN_INTERVAL_SECONDS`
- Increase `MISTRAL_QUEUE_RETRY_BASE_SECONDS`

### 13.4 Front vs Back address differences
If your card back has the latest address:
- Set `MISTRAL_ENABLE_BACK_OCR=true`
- The OCR worker stores both addresses under `document_data.ai_document_extraction.address_summary.candidates`
- `selected_address` prefers back-side OCR when available, so reviewer tools can treat it as the current-address candidate

### 13.5 Mistral 400 code 3050
Meaning: missing/invalid `document_annotation_format` schema.
Current code already sends required `json_schema`.
If seen again, ensure latest code is deployed and server restarted.

### 13.6 `ModuleNotFoundError: django`
Use project venv:
```bash
source .venv/bin/activate
```

## 14) Security / Domain Rules
- AI output is assistance only, never final approval.
- Do not log sensitive PII/images/secrets in plaintext.
- Keep tenant linkage strict for customer/session/link operations.
- Maintain auditability of review state transitions.

## 14) Daily Commands
```bash
source .venv/bin/activate
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
# separate terminal
ngrok http 8000
```
