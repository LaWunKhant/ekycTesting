# AGENTS.md

## Project Context
- Stack: Django project (`manage.py`, `myproject/settings.py`) configured for MySQL via environment variables.
- `myproject/settings.py` is MySQL-only.
- Local database file artifacts are not used by this project.

## What To Check First (before edits)
- Search for project-level database/backend references (exclude `.venv/` noise).
- Confirm database backend in `myproject/settings.py`.
- Confirm `README.md` database/setup docs match the current backend (MySQL-only).
- Check `git status --short` because this repo may already have user changes.

## Backend Consistency Checks
- Ignore dependency/package noise inside `.venv/` (third-party packages).
- Check docs (`README.md`) for outdated database/backend references after backend changes.

## MySQL Configuration Notes
- MySQL branch is selected when `DB_ENGINE=mysql`.
- App is intended to run with MySQL only.
- Expected env vars used in `myproject/settings.py`:
  - `DB_ENGINE`
  - `DB_NAME`
  - `DB_USER`
  - `DB_PASSWORD`
  - `DB_HOST`
  - `DB_PORT`

## eKYC Domain Guide (Project-Specific)
- Treat verification state changes as sensitive operations; preserve auditability (status, timestamps, reviewer actions, reasons).
- Do not silently overwrite verification outcomes (`approved`, `rejected`, `needs_info`, `pending`) without checking the existing state and business intent.
- Keep tenant isolation strict: always filter tenant data by `request.user.tenant` (unless in platform/super admin views).
- For upload/capture flows, validate ownership and tenant linkage before saving images or updating `VerificationSession`.
- Prefer explicit server-side validation for customer-facing API inputs even if frontend JS already validates.
- When sending emails (verification links, temp passwords), keep a safe fallback UX if mail delivery fails (show actionable message to admin).
- Avoid logging sensitive PII/images/secrets in plain text (document images, passwords, tokens, full IDs).

## Django Best Practices (This Repo)
- Keep business logic out of templates; use views/forms/services for validation and state transitions.
- Reuse `forms.Form` / model validation for admin POST actions instead of parsing raw `request.POST` everywhere.
- Use helper functions for repeated behavior (password generation, email sending, permission checks).
- Prefer `select_related` / `prefetch_related` for dashboard lists to avoid N+1 queries.
- Return clear user-facing errors for admin actions (create tenant, reset password, review actions) and avoid generic failures.
- Wrap multi-step writes in transactions when partial saves would leave inconsistent state (e.g., tenant + admin user creation + side effects).
- Keep settings and secrets environment-driven; avoid adding new hardcoded credentials/URLs.

## Design Pattern Guide (UI / Templates)
- Follow existing Tailwind component patterns from `kyc/templates/kyc/platform_dashboard.html` and related admin pages.
- Reuse visual structures already present in the project: cards, alert banners, form spacing, button styles, and status chips.
- Keep forms semantically correct (labels, input types, CSRF, error/success messages near the form).
- For new admin/tenant pages, maintain responsive behavior (single-column mobile, multi-column desktop) consistent with current templates.
- Prefer progressive enhancement: server-rendered Django views first, then add JS only for interactive/camera workflows.
- Keep user messaging precise for operational actions (email sent, fallback shown, tenant created, review updated).

## Safe Working Style For This Repo
- Prefer `find` + `grep` if `rg` is unavailable.
- Make targeted edits only; avoid overwriting user changes in `myproject/settings.py`.
- If changing DB config, explain whether the app remains MySQL-only.
- For UI changes, reference existing Tailwind CSS patterns/classes in current templates (especially dashboard pages) to keep design consistent.

## Common Fixes To Consider (only with user confirmation)
- Update `README.md` if database/setup docs are outdated.
- Keep new frontend/admin UI changes aligned with existing Tailwind-based design patterns.
