# MoonKYC (Django) - Developer Runbook

This README is the single source of truth for running, debugging, and modifying this project.

## 1) What This Project Is
MoonKYC is a Django-based eKYC system with:
- Multi-tenant dashboards (platform admin + tenant workspace)
- Customer verification flow (document capture, card thickness, liveness, selfie, submit)
- Review queue for manual verification
- Temporary debug routes for flow testing

Main apps:
- `accounts`: auth, login/signup/logout, custom user model
- `kyc`: verification flow, dashboards, APIs, liveness, review

---

## 2) Tech Stack
- Python 3.10+
- Django (custom user model)
- MySQL (default / required)
- OpenCV + NumPy (image handling)
- Browser camera APIs (`getUserMedia`)
- Optional ngrok (phone testing over HTTPS)

---

## 3) Project Structure (Important Files)
- `manage.py`: Django entrypoint
- `myproject/settings.py`: global settings
- `myproject/urls.py`: top-level routes
- `accounts/models.py`: custom `User` model (`AUTH_USER_MODEL`)
- `accounts/views.py`: auth + role-aware login redirect
- `kyc/models.py`: `Tenant`, `Customer`, `VerificationSession`, `VerificationLink`
- `kyc/views.py`: dashboards, page views, review, temp bug routes
- `kyc/api_views.py`: APIs (`/session/start`, `/capture/`, `/session/submit`, `/liveness-result`)
- `kyc/templates/kyc/index.html`: main customer flow UI
- `kyc/templates/kyc/liveness.html`: liveness page
- `kyc/static/js/main.js`: main capture flow logic
- `kyc/static/js/liveness.js`: liveness detection logic
- `kyc/static/css/main.css`: camera overlay, responsive behavior
- `kyc/static/css/liveness.css`: fullscreen liveness styling

---

## 4) First-Time Setup

### 4.1 Create & activate virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4.2 Install dependencies
Current `requirements.txt` contains command lines, not a standard pip freeze format.
Run these manually:
```bash
pip install opencv-python
pip install face-recognition
pip install pytesseract
pip install Pillow
pip install numpy
pip install git+https://github.com/ageitgey/face_recognition_models
pip install setuptools
pip install deepface
pip install tf-keras
```

If using macOS and OCR features:
```bash
brew install tesseract
```

### 4.3 Run migrations
Make sure your `.env` is configured for MySQL first (see section 4.5), then run:
```bash
python manage.py migrate
```

### 4.4 Create super admin user (first login)
```bash
python manage.py createsuperuser
```
Use email/password (username is disabled in custom user model).

### 4.5 Use MySQL permanently with `.env` (instead of re-exporting every time)
`myproject/settings.py` now auto-loads a local `.env` file (if present).

1. Create your local env file:
```bash
cp .env.example .env
```

2. Edit `.env` with your MySQL values (same connection you use in TablePlus):
```env
DB_ENGINE=mysql
DB_NAME=ekyc
DB_USER=root
DB_PASSWORD=
DB_HOST=127.0.0.1
DB_PORT=3306
```

3. Run Django commands normally (no repeated `export` needed):
```bash
python manage.py check
python manage.py migrate
python manage.py runserver
```

4. Verify in TablePlus:
- Refresh tables in the `ekyc` database
- Confirm tables like `django_migrations` and `accounts_user` exist
- Optional SQL check:
```sql
SELECT COUNT(*) FROM django_migrations;
```

Note:
- `.env` is ignored by git.
- Shell `export` variables still override `.env` values if both exist.

---

## 5) Required Settings (`myproject/settings.py`)
These are already present, but verify before running:

- `DEBUG = True` (for local dev)
- `ALLOWED_HOSTS` includes:
  - `127.0.0.1`
  - `localhost`
  - `.ngrok-free.app` (for ngrok URL)
- `CSRF_TRUSTED_ORIGINS` includes:
  - `https://*.ngrok-free.app`
- `AUTH_USER_MODEL = "accounts.User"`
- Static/media:
  - `STATIC_URL = "/static/"`
  - `STATICFILES_DIRS = [BASE_DIR / "kyc" / "static"]`
  - `MEDIA_URL = "/media/"`
  - `MEDIA_ROOT = BASE_DIR / "media"`

Optional but recommended:
- `PUBLIC_BASE_URL` for shareable links (set to your current ngrok URL)
  - Example: `https://xxxx-xx-xx-xx-xx.ngrok-free.app`
- Email settings (`EMAIL_HOST`, `EMAIL_HOST_USER`, etc.) if sending mails

Security note: move hardcoded secrets/passwords to environment variables for real deployments.

Local runtime/artifact folders (recommended to keep out of Git):
- `media/` for uploaded captures and derived images
- `artifacts/` for large local model files (for example `artifacts/shape_predictor_68_face_landmarks.dat`)

---

## 5.1) Internationalization (i18n/l10n) - English + Japanese

The project is configured for English (`en`, default) and Japanese (`ja`).

### Current i18n setup (already added)
- `USE_I18N = True`
- `LANGUAGE_CODE = "en"`
- `LANGUAGES = [("en", "English"), ("ja", "日本語")]`
- `LOCALE_PATHS = [BASE_DIR / "locale"]`
- `django.middleware.locale.LocaleMiddleware` enabled (after session middleware)
- Django language endpoint enabled at `/i18n/` (includes `/i18n/setlang/`)

Key files:
- `myproject/settings.py`
- `myproject/urls.py`
- `locale/ja/LC_MESSAGES/django.po`
- `locale/ja/LC_MESSAGES/django.mo` (compiled)

### How to mark strings for translation (templates)
In Django templates:
```django
{% load i18n %}
<h2>{% trans "Capture the front of your document" %}</h2>
<p>{% trans "Tilt backward so the TOP edge is visible." %}</p>
```

For page language attribute:
```django
{% get_current_language as LANGUAGE_CODE %}
<html lang="{{ LANGUAGE_CODE }}">
```

### How to update/add Japanese translations
1. Mark new UI strings with `{% trans %}` (or `{% blocktrans %}` for longer/variable text).
2. Regenerate/update the message file:
```bash
source .venv/bin/activate
python manage.py makemessages -l ja
```
3. Edit Japanese translations in:
- `locale/ja/LC_MESSAGES/django.po`
4. Compile translations:
```bash
python manage.py compilemessages -l ja
```
5. Restart Django server and refresh the browser.

Notes:
- `compilemessages` requires GNU gettext (`msgfmt`). On macOS: `brew install gettext` (and ensure it is on PATH).
- Only strings wrapped in translation tags/functions will be translated.

### How to switch language at runtime
Option A (automatic):
- Browser `Accept-Language: ja` will render Japanese when `LocaleMiddleware` is active.

Option B (manual, Django standard endpoint):
- POST to `/i18n/setlang/` with `language=ja` or `language=en`

Example form:
```django
{% load i18n %}
<form action="{% url 'set_language' %}" method="post">
  {% csrf_token %}
  <input name="next" type="hidden" value="{{ request.path }}">
  <button type="submit" name="language" value="en">English</button>
  <button type="submit" name="language" value="ja">日本語</button>
</form>
```

### JavaScript text (important)
`kyc/static/js/liveness.js` now reads translated strings injected from `kyc/templates/kyc/liveness.html` via `window.LIVENESS_I18N`.

If you localize more JS-heavy pages (for example `kyc/static/js/main.js`), use one of these patterns:
- Inject translated strings from the Django template into `window.<...>`
- Or use Django JS i18n (`gettext`, `JavaScriptCatalog`) if you want direct translation calls in JS

---

## 6) Start Order (Important)
Always start services in this order:

1. Activate virtual env
```bash
source .venv/bin/activate
```

2. Start Django server
```bash
python manage.py runserver 0.0.0.0:8000
```

3. Start ngrok (for phone camera testing)
```bash
ngrok http 8000
```
Do **not** run `http ngrok 8000`.
Correct command is `ngrok http 8000`.

4. Update `PUBLIC_BASE_URL` in `settings.py` to the new ngrok URL

5. Open app:
- Local: `http://127.0.0.1:8000`
- Phone: ngrok HTTPS URL

---

## 7) Core Route Map

### Platform/Admin
- `/accounts/login/`
- `/admin/dashboard/` (super admin dashboard)
- `/admin/users/`
- `/admin/tenants/<uuid>/...`

### Tenant
- `/<tenant_slug>/dashboard/`
- `/dashboard/team/`
- `/review/`

### Customer Verification
- `/customer/start/`
- `/verify/?tenant_slug=<slug>&customer_id=<id>`
- `/verify/start/<token>/`
- `/liveness?session_id=<uuid>`

### API Endpoints
- `/session/start`
- `/capture/`
- `/session/submit`
- `/liveness-result`
- `/start-liveness/`
- `/check-liveness/`
- `/cancel-liveness/`

### Temporary Debug
- `/bug/liveness/?tenant_slug=<slug>&autostart=1`

---

## 8) How the Verification Flow Works

Frontend flow in `kyc/static/js/main.js`:
1. Start session (`/session/start`)
2. Document capture (front/back)
3. Thickness capture (tilt)
4. Liveness popup (`/liveness`)
5. Selfie capture
6. Submit (`/session/submit` then `/verify/submit/`)

Captured images are uploaded through `/capture/` and stored under `MEDIA_ROOT` (for example `media/front_...jpg`, `media/back_...jpg`).

Derived face crops used during verification are also stored under `MEDIA_ROOT/extracted_faces/`.

---

## 9) Bootstrap Data for Testing

### Option A: Sign up a new tenant owner
- Go to `/accounts/signup/`
- Creates tenant + owner user

### Option B: Use platform dashboard
- Login as super admin
- Go to `/admin/dashboard/`
- Create tenant + owner from UI

Then open tenant dashboard and create customer verification links.

---

## 10) Common Issues + Fix Checklist

### Camera permission denied on phone
- Use HTTPS (ngrok), not plain HTTP
- Confirm browser camera permission is allowed
- Close other tabs/apps using camera
- Ensure liveness popup/tab is closed before selfie starts

### ngrok command not working
- Install ngrok and run:
```bash
ngrok http 8000
```

### Static/CSS/JS changes not visible
- Hard refresh browser
- Check cache-busting query in template script/link tags
- Confirm file loaded from `kyc/static/...`

### `ModuleNotFoundError: django`
- Activate venv first:
```bash
source .venv/bin/activate
```
- Reinstall dependencies

### CSRF/host issues on ngrok
- Add ngrok domain in:
  - `ALLOWED_HOSTS`
  - `CSRF_TRUSTED_ORIGINS`

---

## 11) Where to Edit for UI/Flow Fixes
- Main capture UI text/layout: `kyc/static/js/main.js`, `kyc/static/css/main.css`, `kyc/templates/kyc/index.html`
- Liveness fullscreen and instructions: `kyc/templates/kyc/liveness.html`, `kyc/static/css/liveness.css`, `kyc/static/js/liveness.js`
- Temp debug links/buttons:
  - `kyc/views.py` (`bug_liveness_check`)
  - `kyc/urls.py`
  - `kyc/templates/kyc/tenant_dashboard.html`
  - `kyc/templates/kyc/platform_dashboard.html`

---

## 12) Minimal Daily Run Commands
```bash
source .venv/bin/activate
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
# new terminal:
ngrok http 8000
```

Use this README when debugging so we both reference the same flow and file map.
