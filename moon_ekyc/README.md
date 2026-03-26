# MoonKYC Tenant Workspace (Laravel) - Developer Runbook

This README is the source of truth for setup, runtime behavior, and the Laravel-to-Django split for the tenant workspace.

Need a faster engineer handoff doc? See `DEVELOPER_OPERATIONS_GUIDE.md`.
Japanese design documentation is available at `SYSTEM_DESIGN_JP.md`.

## 1) Project Overview
MoonKYC Laravel is the tenant-facing workspace for the eKYC platform. It is responsible for:
- Tenant login and tenant dashboard UX
- Customer creation for a tenant
- Verification link generation and share/email flow
- Tenant-facing session list, review queue, and team pages
- Shared database access to the same tenant/customer/link tables used by the Django verification backend

This app is not the customer verification UI and not the super-admin review console.
Those responsibilities live in the Django project under `Herd/PythonProject`.

Core responsibilities split:
- Laravel (`Herd/moon_ekyc`): tenant auth and tenant workspace
- Django (`Herd/PythonProject`): customer verification UI, verification APIs, OCR/AI processing, and super-admin review

## 2) Stack
- PHP 8.2+
- Laravel 12
- Inertia.js + Vue 3 + TypeScript
- Tailwind CSS
- MySQL-compatible shared database tables
- Mailtrap/SMTP for verification-link email delivery

## 3) Important Files
- `artisan`
- `composer.json`
- `package.json`
- `routes/web.php`
- `routes/auth.php`
- `app/Http/Controllers/TenantDashboardController.php`
- `app/Http/Controllers/TenantSessionsController.php`
- `app/Http/Controllers/TenantReviewController.php`
- `app/Http/Controllers/TenantTeamController.php`
- `app/Http/Requests/TenantCreateCustomerRequest.php`
- `app/Models/Tenant.php`
- `app/Models/Customer.php`
- `app/Models/VerificationLink.php`
- `app/Models/User.php`
- `resources/js/pages/Dashboard.vue`
- `resources/js/pages/Tenant/Sessions.vue`
- `resources/js/pages/Tenant/Review.vue`
- `resources/js/pages/Tenant/Team.vue`

## 4) Local Setup
### 4.1 Install dependencies
```bash
composer install
npm install
```

### 4.2 Configure `.env`
```bash
cp .env.example .env
php artisan key:generate
```

Recommended database configuration for this project:
```env
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=ekyc
DB_USERNAME=root
DB_PASSWORD=
```

Recommended app/link settings:
```env
APP_NAME="MoonKYC Tenant Workspace"
APP_URL=http://moon_ekyc.test
PUBLIC_BASE_URL=http://127.0.0.1:8000
```

`PUBLIC_BASE_URL` should point to the Django verification app base URL because verification links generated here resolve to `/verify/start/<token>/` on the Django side.

### 4.3 Run locally
```bash
composer run dev
```

Or run services separately:
```bash
php artisan serve
php artisan queue:listen --tries=1
php artisan pail --timeout=0
npm run dev
```

## 5) Environment Variables
### 5.1 Core app
- `APP_NAME`
- `APP_ENV`
- `APP_KEY`
- `APP_DEBUG`
- `APP_URL`
- `APP_LOCALE`
- `APP_FALLBACK_LOCALE`

### 5.2 Database
- `DB_CONNECTION` should be `mysql` for the shared eKYC setup
- `DB_HOST`
- `DB_PORT`
- `DB_DATABASE`
- `DB_USERNAME`
- `DB_PASSWORD`

### 5.3 Mail
- `MAIL_MAILER`
- `MAIL_HOST`
- `MAIL_PORT`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `MAIL_FROM_ADDRESS`
- `MAIL_FROM_NAME`

### 5.4 Verification handoff
- `PUBLIC_BASE_URL`
  - Base URL of the Django verification app
  - Used when building `/verify/start/<token>/` links for customers

## 6) Authentication and Account Flows
Current routes are defined in `routes/auth.php`.

Available flows:
- Login: `/login`
- Register: `/register`
- Logout: `/logout`
- Forgot password: `/forgot-password`
- Reset password: `/reset-password/{token}`
- Settings pages: `/settings/...`

Tenant dashboard access is behind Laravel `auth` middleware.

## 7) Route Map
### 7.1 Tenant Workspace
- `/dashboard`
- `/sessions`
- `/team`
- `/review`

### 7.2 Auth
- `/login`
- `/register`
- `/forgot-password`
- `/reset-password/{token}`
- `/logout`

## 8) Shared Data Contract With Django
This Laravel app shares key tables with the Django verification backend.

Current shared models:
- `tenants`
- `customers`
- `kyc_verification_links`
- `staff_users`

Important mappings:
- `App\Models\Tenant` uses table `tenants`
- `App\Models\Customer` uses table `customers` and links by `tenant_uuid -> tenants.uuid`
- `App\Models\VerificationLink` uses table `kyc_verification_links`
- `App\Models\User` uses table `staff_users`

Verification-link handoff:
1. Tenant user creates a customer in Laravel.
2. Laravel creates a `kyc_verification_links` row.
3. Laravel builds a URL like `<PUBLIC_BASE_URL>/verify/start/<token>/`.
4. Customer opens the Django verification UI.
5. Django resolves the token, tenant, and customer, then runs the verification flow.

Important constraints:
- Keep tenant/customer/link schema compatible with Django.
- Do not change table names or foreign-key semantics casually.
- `tenant_uuid`, `customer_id`, and token formatting must stay compatible across both apps.

## 9) Current Feature Status
Implemented now:
- Tenant auth shell
- Tenant dashboard customer-create form
- Verification link generation
- SMTP send attempt with fallback message when credentials are missing
- Shared table models for tenant, customer, link, and staff user

Currently scaffolded / placeholder:
- `/sessions` page data wiring
- `/review` page data wiring
- `/team` create/manage actions beyond placeholder UI
- deeper tenant metrics on the dashboard

This is important: the dashboard create-customer flow is live, but the sessions/review/team pages are still UI scaffolds and need backend query/action wiring.

## 10) Mail / Verification Link Behavior
`TenantDashboardController` sends verification-link email only when a customer email exists.

Behavior:
- If SMTP is configured, Laravel sends the verification email.
- If SMTP credentials are missing or masked, Laravel still creates the link and shows an operational warning.
- If `PUBLIC_BASE_URL` is set, it is used as the Django verification host.
- Otherwise link generation falls back to `config('app.url')`, which is usually wrong for customer verification if Laravel and Django are split.

Set `PUBLIC_BASE_URL` explicitly in this app.

## 11) Troubleshooting
### 11.1 Customer link opens the Laravel app instead of Django
Cause:
- `PUBLIC_BASE_URL` is missing or wrong.

Fix:
1. Set `PUBLIC_BASE_URL` to the Django verification base URL.
2. Clear config if needed: `php artisan config:clear`
3. Generate a fresh verification link.

### 11.2 Verification email is not sent
Cause:
- SMTP credentials missing, invalid, or masked.

Checks:
- verify `MAIL_MAILER=smtp`
- verify `MAIL_USERNAME` and `MAIL_PASSWORD`
- verify Mailtrap inbox/credentials
- check Laravel logs and UI flash messages

### 11.3 Tenant dashboard shows zero stats
Cause:
- metrics are still scaffold placeholders in the current controller/page implementation.

Fix:
- wire tenant session/review queries into `TenantDashboardController`
- wire actual session data into `TenantSessionsController` and `TenantReviewController`

### 11.4 Shared login fails for migrated Django users
Cause:
- password hash format mismatch.

Checks:
- `App\Models\User::canAuthenticateWithPassword()` supports Django `pbkdf2_sha256`
- confirm stored password format in `staff_users`

## 12) Security / Domain Rules
- Tenant users in Laravel must remain tenant-scoped.
- Do not allow cross-tenant customer/session/link creation or access.
- Final approval is manual; AI/OCR is handled on the Django side.
- Avoid logging sensitive PII or secrets.
- Keep the shared database contract stable and auditable.

## 13) Daily Commands
```bash
composer install
npm install
cp .env.example .env
php artisan key:generate
composer run dev
```
