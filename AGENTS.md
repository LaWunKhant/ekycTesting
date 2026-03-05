# AGENTS.md

## Project Context
- Stack: Django project (`manage.py`, `myproject/settings.py`) with MySQL only.
- Local DB file artifacts are not used.
- eKYC flow includes manual review, DeepFace matching, and asynchronous Mistral OCR assist.

## What To Check First (Before Edits)
- Check repo state: `git status --short`.
- Confirm DB backend remains MySQL in `myproject/settings.py`.
- Search project references excluding `.venv/` noise.
- Keep `README.md` aligned with any behavior/config changes.

## Backend Consistency
- Ignore dependency/package noise under `.venv/`.
- Do not introduce non-MySQL database branches.
- Keep settings/env driven; avoid hardcoded credentials.

## MySQL Configuration Notes
- `DB_ENGINE` must be `mysql`.
- Expected env keys:
  - `DB_ENGINE`
  - `DB_NAME`
  - `DB_USER`
  - `DB_PASSWORD`
  - `DB_HOST`
  - `DB_PORT`

## eKYC Domain Rules
- Treat review state transitions as sensitive and auditable.
- Never silently overwrite review outcomes (`pending`, `approved`, `rejected`, `needs_info`).
- Keep tenant isolation strict (`request.user.tenant`) unless platform admin path explicitly allows cross-tenant access.
- Validate ownership/tenant linkage before any image/session update.
- Avoid logging sensitive PII or secrets.

## AI/OCR Rules (Project-Specific)
- AI is decision support only; final approval remains manual.
- Persist AI outputs in auditable fields (`VerificationSession.document_data`).
- OCR runs asynchronously through queue worker; customer submit path must stay non-blocking.
- Handle Mistral 429 with queue retry/backoff (do not block customer requests).
- Keep front OCR default enabled; back OCR default disabled unless explicitly needed.

## Django Best Practices (This Repo)
- Keep business logic in views/services/forms, not templates.
- Use reusable helpers for repeated actions (permission checks, link building, OCR enqueue, etc.).
- Prefer `select_related` / `prefetch_related` where list/detail pages need related models.
- Return explicit operational errors for admin actions.
- Use transactions for multi-step writes where partial failure causes inconsistency.
- For password changes, use `PasswordChangeForm` + `update_session_auth_hash`.

## UI/Template Design Rules
- Follow existing Tailwind patterns from platform/tenant pages.
- Preserve responsive behavior (mobile single-column, desktop multi-column).
- Keep action messages clear and operationally useful.
- For review images, preserve full-size inspectability (modal/new-tab access).

## Safe Working Style
- Prefer `find` + `grep` if `rg` is unavailable.
- Make targeted edits; avoid clobbering existing user changes.
- If changing runtime behavior/config, update `.env.example` and `README.md` in the same change.
- If changing public link behavior, explicitly verify `PUBLIC_BASE_URL` handling.

## Common Follow-Up Fixes (With User Confirmation)
- Tune OCR queue retry/backoff settings for quota constraints.
- Tune physical card threshold/UX guidance when false negatives are frequent.
- Expand reviewer UI surfacing of queued OCR state if needed.
