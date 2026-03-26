# MoonKYC Tenant Workspace - Developer Operations Guide

This guide is a fast reference for engineers working on the Laravel tenant workspace.

## 1) Core Features
- Tenant login and authenticated workspace shell.
- Tenant dashboard for customer creation and verification-link generation.
- Shared database access to tenant/customer/link/user tables used by Django.
- SMTP-backed verification-link email sending with operational fallback warnings.
- Scaffolded sessions, review, and team pages ready for backend wiring.

## 2) Key Modules
- `routes/web.php`: tenant workspace routes.
- `routes/auth.php`: auth routes.
- `app/Http/Controllers/TenantDashboardController.php`: customer create + link generation.
- `app/Http/Controllers/TenantSessionsController.php`: tenant sessions list placeholder.
- `app/Http/Controllers/TenantReviewController.php`: tenant review queue placeholder.
- `app/Http/Controllers/TenantTeamController.php`: tenant team placeholder.
- `app/Http/Requests/TenantCreateCustomerRequest.php`: dashboard create-customer validation.
- `app/Models/Tenant.php`: shared tenant model.
- `app/Models/Customer.php`: shared customer model.
- `app/Models/VerificationLink.php`: shared verification link model.
- `app/Models/User.php`: shared staff user model, including Django PBKDF2 password compatibility.

## 3) Operational Split
Laravel owns:
- tenant login
- tenant dashboard UX
- customer creation
- verification-link generation
- tenant workspace pages

Django owns:
- customer verification flow
- `/verify/start/<token>/` and `/verify/`
- AI/OCR processing
- super-admin review and admin pages

## 4) Shared Tables to Protect
- `tenants`
- `customers`
- `kyc_verification_links`
- `staff_users`

Risks if changed carelessly:
- broken customer link routing
- broken tenant isolation
- broken Django verification-token resolution
- password compatibility regressions between Laravel and Django-authored users

## 5) Verification Link Contract
`TenantDashboardController` currently:
1. validates customer input
2. creates a `customers` row scoped by `tenant_uuid`
3. creates a `kyc_verification_links` row
4. builds `<PUBLIC_BASE_URL>/verify/start/<token>/`
5. optionally emails the link

Keep these fields stable:
- `tenant_uuid`
- `customer_id`
- `token`
- `expires_at`

## 6) Required Environment Variables
Core:
- `APP_URL`
- `APP_KEY`
- `APP_ENV`
- `APP_DEBUG`

Database:
- `DB_CONNECTION=mysql`
- `DB_HOST`
- `DB_PORT`
- `DB_DATABASE`
- `DB_USERNAME`
- `DB_PASSWORD`

Mail:
- `MAIL_MAILER`
- `MAIL_HOST`
- `MAIL_PORT`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `MAIL_FROM_ADDRESS`
- `MAIL_FROM_NAME`

Django handoff:
- `PUBLIC_BASE_URL`

## 7) Fast Troubleshooting Matrix
1. Symptom: customer gets link to the wrong host.
Cause:
`PUBLIC_BASE_URL` missing or wrong.
Checks:
- confirm `.env` value
- run `php artisan config:clear`
- regenerate link

2. Symptom: link generated but email not sent.
Cause:
SMTP credentials missing or invalid.
Checks:
- confirm `MAIL_MAILER=smtp`
- inspect flash message from dashboard
- verify Mailtrap credentials
- inspect `storage/logs/laravel.log`

3. Symptom: tenant user login fails after migration from Django.
Cause:
password hash format mismatch.
Checks:
- inspect `staff_users.password`
- confirm `User::canAuthenticateWithPassword()` path for Django hashes

4. Symptom: sessions/review/team pages look empty.
Cause:
current controllers are placeholders.
Checks:
- confirm controller payloads
- wire real queries against shared session/review data

## 8) Daily Engineer Checklist
1. Start Laravel app and Vite.
2. Confirm `.env` values and MySQL connectivity.
3. Log in as a tenant user.
4. Create one customer and generate one verification link.
5. Confirm the link opens the Django verification app.
6. Check mail behavior and fallback messaging.

## 9) Recommended Incident Workflow
1. Capture exact tenant/user/customer identifiers.
2. Check `tenants`, `customers`, and `kyc_verification_links` rows.
3. Confirm the generated link host/token.
4. Reproduce with the same `.env` and tenant account.
5. If the issue touches Django verification routing, inspect both repos before changing shared logic.
