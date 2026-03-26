# MoonKYC Developer Operations Guide

This guide is a fast reference for engineers and reviewers to understand core features and resolve common production issues quickly.

## 1) Core Features
- Tenant-backed verification architecture with strict tenant isolation on customer/session data.
- Platform admin area for cross-tenant oversight.
- Super-admin-only Django login surface.
- Customer eKYC journey:
  - profile/address input
  - document capture (front/back)
  - liveness challenge
  - selfie capture
  - verification submit
- AI assist pipeline (decision support only):
  - face similarity
  - physical card checks
  - async Mistral OCR (queue worker + retry/backoff)
- Manual review is final authority (`pending`, `approved`, `rejected`, `needs_info`).

## 2) Key Modules
- `accounts/`: super admin auth, login/logout/password management.
- `kyc/models.py`: `Tenant`, `Customer`, `VerificationSession`, `VerificationLink`.
- `kyc/views.py`: admin pages and verification orchestration.
- `kyc/api_views.py`: API endpoints for capture/session/submit.
- `kyc/services/mistral_ai.py`: OCR client, retry logic, queue worker, extracted document fields.
- `kyc/services/card_physical_check.py`: thickness/depth/edge card checks.
- `myproject/settings.py`: env loading and platform configuration.

## 3) Data Ownership Rules
- Final review decision is always manual.
- Never overwrite review status silently.
- No tenant-facing login/UI exists in this repo; tenant linkage is still required for verification records and link resolution.
- OCR/AI output must be stored in auditable fields (`VerificationSession.document_data`).
- Sensitive PII must not be logged.

## 4) VerificationSession Fields to Watch
- Automation outcomes:
  - `verify_similarity`
  - `verify_confidence`
  - `verify_verified`
  - `liveness_verified`
  - `physical_card_verified`
- Review outcomes:
  - `review_status`
  - `review_notes`
  - `reviewed_by`
  - `reviewed_at`
- OCR payload:
  - `document_data.ai_document_extraction`
  - `document_data.identity_assist`

## 5) OCR Extraction Contract (Current)
`ai_document_extraction.front/back.extracted` includes:
- `full_name`
- `date_of_birth`
- `document_number`
- `expiry_date`
- `nationality`
- `address`
- `postal_code`
- `prefecture`
- `city`
- `street_address`
- `address_raw`
- `residence_status`
- `notes`

Address merge output:
- `ai_document_extraction.address_summary.selected_address`
- `ai_document_extraction.address_summary.selected_source`
- `ai_document_extraction.address_summary.has_conflict`
- `ai_document_extraction.address_summary.candidates`

## 6) Required Environment Variables
Database (MySQL only):
- `DB_ENGINE=mysql`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

Email:
- `EMAIL_HOST`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_PORT`
- `EMAIL_USE_TLS`
- `DEFAULT_FROM_EMAIL`

OCR/AI:
- `MISTRAL_API_KEY`
- `MISTRAL_BASE_URL`
- `MISTRAL_ENABLE_OCR`
- `MISTRAL_ENABLE_BACK_OCR`
- `MISTRAL_MAX_RETRIES`
- `MISTRAL_QUEUE_MAX_ATTEMPTS`

## 7) Fast Troubleshooting Matrix
1. Symptom: verification emails are not arriving.
Cause:
`EMAIL_*` misconfig, SMTP quota, TLS/cert issue, or `fail_silently=True` path.
Checks:
- confirm runtime settings in Django shell
- verify Mailtrap quota/credentials
- verify TLS and certificate chain/network interception

2. Symptom: OCR address is wrong or postal-code-like only.
Cause:
front-only OCR, low-quality image, misread structured fields.
Checks:
- ensure `MISTRAL_ENABLE_BACK_OCR=true` when address updates are on back side
- inspect `front/back.extracted.address_raw` and `address_summary`
- confirm card image clarity (glare/blur/crop)

3. Symptom: OCR gets stuck in retries.
Cause:
Mistral 429 rate limiting.
Checks:
- inspect `ai_document_extraction.status`
- tune `MISTRAL_MIN_INTERVAL_SECONDS`
- tune `MISTRAL_QUEUE_RETRY_BASE_SECONDS`
- reduce pressure by disabling unnecessary back OCR when not needed

4. Symptom: session status inconsistent after failures.
Cause:
partial updates during multi-step flow.
Checks:
- confirm transaction coverage for multi-step writes
- check `updated_at`, `status`, `current_step`, and `document_data` progression

## 8) Daily Engineer Checklist
1. Start services (`mysql`, Django app, optional ngrok).
2. Confirm `.env` values and MySQL connectivity.
3. Create one test verification end-to-end.
4. Validate review queue rendering and image inspectability.
5. Confirm OCR state transitions (`queued` -> `completed` or retry).
6. Confirm email path by sending one controlled test message.

## 9) Recommended Incident Workflow
1. Capture exact error text + timestamp.
2. Identify affected tenant/session IDs.
3. Check `document_data` JSON and review status transitions.
4. Reproduce in local with same env flags.
5. Apply minimal fix and record the behavioral change in `README.md`.
