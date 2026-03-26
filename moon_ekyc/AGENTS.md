# AGENTS.md

## Project Context
- Stack: Laravel 12 + Inertia.js + Vue 3 + TypeScript.
- This repo is the tenant-facing MoonKYC workspace.
- Django under `Herd/PythonProject` owns customer verification UI, verification APIs, OCR/AI, and super-admin review.
- This repo shares tenant/customer/link/user tables with the Django app.

## What To Check First (Before Edits)
- Check repo state from the Laravel project root.
- Confirm whether the change affects the Laravel-only tenant UX or the shared Laravel-Django contract.
- Search references excluding `node_modules/` and `vendor/` noise.
- Keep `README.md` aligned with any behavior/config changes.

## Shared Data Contract
- Do not casually rename or repurpose shared tables:
  - `tenants`
  - `customers`
  - `kyc_verification_links`
  - `staff_users`
- Preserve tenant UUID/customer/link relationships.
- Keep token behavior compatible with Django `/verify/start/<token>/` resolution.
- If changing shared schema assumptions, update both repos' docs.

## Tenant Workspace Rules
- Tenant users must stay scoped to their own tenant.
- Do not introduce cross-tenant reads/writes in dashboard, sessions, review, or team flows.
- Keep operational messages explicit when mail/link generation partially succeeds.
- If SMTP is unavailable, do not fail silently; keep the generated link path recoverable.

## Laravel Best Practices (This Repo)
- Keep business logic in controllers/requests/services, not Vue pages.
- Use Form Requests for tenant write validation.
- Prefer explicit Eloquent relations and scopes for tenant isolation.
- Preserve Inertia page contracts when changing controller payloads.
- Keep placeholder pages clearly marked until fully wired.

## Frontend Rules
- Preserve the current visual language in `resources/js/pages/` and `resources/js/components/`.
- Keep layouts responsive and consistent with the current tenant workspace shell.
- Do not regress navigation between dashboard, sessions, review, and team pages.
- Use actionable UX copy for mail/link errors and empty states.

## Environment / Config Rules
- Prefer MySQL for the shared eKYC setup even if Laravel defaults still show SQLite.
- Keep `PUBLIC_BASE_URL` documented because verification links depend on the Django app URL.
- Do not hardcode credentials, hosts, or mail settings.

## Safe Working Style
- Prefer `find` + `grep` if `rg` is unavailable.
- Make targeted edits; avoid clobbering user changes.
- Ignore `node_modules/` and `vendor/` dependency noise.
- If changing runtime behavior/config, update `.env.example` and `README.md` in the same change.

## Common Follow-Up Fixes (With User Confirmation)
- Wire real tenant session metrics into dashboard cards.
- Replace scaffolded tenant sessions/review/team pages with live queries and actions.
- Tighten registration/login policy if tenant onboarding should stop being self-service.
- Align `.env.example` to the shared MySQL + Django verification setup.
