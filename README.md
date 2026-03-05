# MoonKYC (Django) - Developer Runbook

This README is the single source of truth for setup, runtime, troubleshooting, and recent architecture decisions.

## 1) Project Overview
MoonKYC is a Django-based multi-tenant eKYC platform with:
- Platform admin workspace (`/admin/dashboard/`)
- Tenant workspace (`/<tenant_slug>/dashboard/`)
- Customer verification flow (document capture, liveness, selfie, submit)
- Manual review queue for final approval/rejection
- AI assist (face similarity + optional Mistral OCR) with strict human-in-the-loop final decision

Core apps:
- `accounts`: authentication, login/logout/signup/password change
- `kyc`: tenants/customers/sessions, verification APIs, review workflows, OCR queue integration

## 2) Stack
- Python 3.10+
- Django
- MySQL only
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
`requirements.txt` in this repo is not a lock file. Install explicitly as needed:
```bash
pip install django opencv-python numpy deepface tf-keras certifi
```

### 4.3 Configure `.env`
```bash
cp .env.example .env
```

Required database fields:
```env
DB_ENGINE=mysql
DB_NAME=ekyc
DB_USER=root
DB_PASSWORD=
DB_HOST=127.0.0.1
DB_PORT=3306
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
### 5.1 Database (MySQL only)
- `DB_ENGINE` (must be `mysql`)
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

### 5.2 Core app
- `SECRET_KEY`
- `PUBLIC_BASE_URL`
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

## 6) Authentication and Account Flows
- Login: `/accounts/login/`
- Logout: `/accounts/logout/`
- Signup (tenant owner bootstrap): `/accounts/signup/`
- Password change: `/accounts/password/change/`

Password changes use Django `PasswordChangeForm` and keep session active via `update_session_auth_hash`.

## 7) Route Map
### 7.1 Platform Admin
- `/admin/dashboard/`
- `/admin/users/`
- `/admin/tenants/<uuid>/...`
- `/review/`

### 7.2 Tenant
- `/<tenant_slug>/dashboard/`
- `/<tenant_slug>/sessions/`
- `/dashboard/team/`
- `/review/` (tenant-scoped list for non-super admins)

### 7.3 Customer Verification
- `/customer/start/`
- `/verify/?tenant_slug=<slug>&customer_id=<id>`
- `/verify/start/<token>/`
- `/liveness?session_id=<uuid>`

### 7.4 API
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

When OCR completes, worker updates:
- `document_data.ai_document_extraction`
- `document_data.identity_assist` (recomputed in `with_ocr` mode)

## 10) Reviewer UX
`kyc/templates/kyc/admin_session_detail.html` includes:
- Click-to-preview large images in a modal
- `Open in new tab` fallback for full-size image
- `Esc` and outside-click modal close

## 11) Public URL / ngrok Behavior
Tenant-generated verification email links use runtime `.env` lookup (`PUBLIC_BASE_URL`) via helper in `kyc/views.py`.

If links are wrong:
1. Update `.env` `PUBLIC_BASE_URL`
2. Restart Django server
3. Generate/send a new link

Note: old emails keep old URLs.

## 12) Troubleshooting
### 12.1 `ERR_NGROK_3200`
Meaning: ngrok endpoint is offline (dead tunnel URL).
Fix: run ngrok again, update `PUBLIC_BASE_URL`, restart server, resend link.

### 12.2 Mistral SSL error
Example: `SSLCertVerificationError`.
Fix options:
- Ensure certifi installed
- Set `MISTRAL_CA_BUNDLE` to a valid CA file path
- Keep `MISTRAL_SSL_VERIFY=true` (preferred)

### 12.3 Mistral 429 (rate limit)
Meaning: quota/throughput exceeded.
System now retries automatically in queue.
To reduce pressure:
- Keep `MISTRAL_ENABLE_BACK_OCR=false`
- Increase `MISTRAL_MIN_INTERVAL_SECONDS`
- Increase `MISTRAL_QUEUE_RETRY_BASE_SECONDS`

### 12.4 Mistral 400 code 3050
Meaning: missing/invalid `document_annotation_format` schema.
Current code already sends required `json_schema`.
If seen again, ensure latest code is deployed and server restarted.

### 12.5 `ModuleNotFoundError: django`
Use project venv:
```bash
source .venv/bin/activate
```

## 13) Security / Domain Rules
- AI output is assistance only, never final approval.
- Do not log sensitive PII/images/secrets in plaintext.
- Keep tenant isolation strict (`request.user.tenant` scope for non-platform users).
- Maintain auditability of review state transitions.

## 14) Daily Commands
```bash
source .venv/bin/activate
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
# separate terminal
ngrok http 8000
```
