# MedVault Backend

> **Render runtime:** deploy this backend with Python **3.12.5**. The committed `.python-version` file selects it automatically when `backend` is the Render service root. If your service already has a `PYTHON_VERSION` environment variable, set it to `3.12.5` or remove it so the file can take effect.

> **Render system dependencies:** deploy as a **Docker** web service using `backend/Dockerfile`. MedVault requires native OCR, PDF, barcode, and OpenCV libraries; Render's native Python runtime does not install packages listed in `apt.txt`.

MedVault is a FastAPI backend for detecting and destructively redacting PHI/PII from healthcare documents. Uploaded and generated files use short-lived local working directories; file bytes are never persisted in MongoDB.

## Current status

- Project scaffold: complete
- Configuration and dependency baseline: complete
- Local Python 3.12 virtual environment and pinned dependency installation: complete
- Phase 1 (core foundation): complete and verified
- Phase 2 (ephemeral storage and document ingestion): complete and verified
- Phase 3 (layered PHI/PII detection foundation): complete and verified
- Phase 4 (end-to-end PDF pipeline): complete and verified
- Phase 5 (DOCX and XLSX pipelines): complete and verified
- Phase 6 (image and DICOM pipelines): complete and verified
- Phase 7 (EML/MBOX recursive email pipelines): complete and verified
- Phase 8 (Mistral ambiguity resolution and synthetic replacement): complete and verified
- Phase 9 (post-redaction QA and re-identification risk): complete and verified
- Phase 10 (audit, feedback, mode comparison, and heatmaps): complete and verified
- Phase 11 (batch processing and notifications): complete and verified
- Backend feature implementation audit and closure: complete and verified
- Local 10-page mixed-content performance validation: complete and verified
- Synthetic cross-format sample corpus: generated and fully verified across all 22 files, including XLSX drawing-layer images
- Functional endpoints: authentication, document ingestion/preview, redaction jobs, reports, and session-scoped downloads

No scaffold module returns mocked, hardcoded, or fabricated application results.

## Planned implementation phases

1. Core FastAPI, configuration, MongoDB/Beanie models, JWT authentication, ownership enforcement, and tests. **Complete.**
2. Ephemeral storage, secure document ingestion, metadata/status/preview APIs, cleanup, and tests. **Complete.**
3. Presidio/scispaCy detection, medical recognizers, context boosting, confidence scoring, mode policies, and tests. **Complete.**
4. End-to-end PDF extraction, OCR, coordinate mapping, destructive redaction, reporting, and tests. **Complete.**
5. DOCX and XLSX extraction/redaction with formatting preservation and tests. **Complete.**
6. Image and DICOM OCR, face/barcode detection, tag removal, pixel redaction, and tests. **Complete.**
7. EML/MBOX processing with recursive attachment routing and tests. **Complete.**
8. Mistral ambiguity resolution, privacy-safe fallback explanations, and synthetic replacements. **Complete.**
9. Post-redaction QA blocking and re-identification risk analysis. **Complete.**
10. Audit hash chains, feedback, mode comparison, and heatmaps. **Complete.**
11. Isolated batch processing, Web Push, and optional SMTP notifications. **Complete.**
12. Docker/Render deployment. **Deferred until frontend/backend integration by project decision.** Local mixed-content performance validation is complete.

This status and the relevant setup/API sections will be updated after every approved phase.

## Requirements

- Python 3.12
- MongoDB 7+ locally, or a MongoDB Atlas connection
- Tesseract OCR, Poppler, and zbar system libraries
- A Mistral API key only if AI-assisted ambiguity resolution is desired
- VAPID keys only if browser push notifications are desired
- Bundled local MediaPipe BlazeFace model at `app/assets/blaze_face_short_range.tflite`

Python dependencies and official NLP model artifacts are pinned in `requirements.txt`. The validated NLP stack is spaCy 3.7.5, scispaCy 0.5.5, `en_core_web_lg` 3.7.1, `en_core_sci_md` 0.5.4, and `en_ner_bc5cdr_md` 0.5.4.

## Local configuration

1. Copy `.env.example` to `.env` if `.env` does not already exist.
2. Keep `JWT_SECRET` private. The checked-out local `.env` already contains a securely generated value.
3. Replace `MONGODB_URI` with a MongoDB Atlas URI if local MongoDB is not being used.
4. Add optional Mistral, VAPID, and SMTP credentials only when those services are enabled.

The real `.env` is ignored by Git. `.env.example` uses visible `<...>` placeholders. Replace placeholders in `.env` before starting the API; optional services may instead be assigned an empty value.

### Where configuration values come from

- `MONGODB_URI`: create a free MongoDB Atlas project and M0 cluster, create a database user, allow the backend's network address, then copy the Drivers connection string from **Connect > Drivers**. For local MongoDB, use `mongodb://localhost:27017`.
- `JWT_SECRET`: this is created locally, not issued by a website. In PowerShell run the command below and paste its output into `.env`:

  ```powershell
  $bytes = New-Object byte[] 48
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $rng.GetBytes($bytes)
  $rng.Dispose()
  [Convert]::ToBase64String($bytes).Replace('+','-').Replace('/','_').TrimEnd('=')
  ```

- `MISTRAL_API_KEY`: create an account in the Mistral AI console, open the API keys section, and create a key. Leave it empty to use the local deterministic fallback.
- `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY`: generate this pair locally after dependencies are installed with `py_vapid --gen`. Keep the private key secret. `VAPID_SUBJECT` is a contact URI such as `mailto:security@example.com`. Leave all three empty until Web Push is enabled.
- SMTP values: obtain these from the chosen mail provider. For Gmail, enable two-step verification and create an app password; use `smtp.gmail.com`, port `587`, the Gmail address as username/sender, and the app password. Brevo provides equivalent SMTP credentials under its SMTP/API settings. Leave SMTP values empty if email fallback is disabled.
- `TESSERACT_CMD`: leave empty when `tesseract` is available on `PATH`. On a default Windows installation it is commonly `C:\\Program Files\\Tesseract-OCR\\tesseract.exe`.
- Storage, upload, concurrency, token lifetime, model name, and application values are configuration choices rather than issued secrets. Their provided defaults can be adjusted for deployment capacity.

`CORS_ORIGINS` is currently `["*"]` as requested. Before production deployment, restrict it to the exact frontend domains. Wildcard origins must not be used with credentialed cross-origin cookies; MedVault uses bearer tokens.

## Local installation

From the `backend` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the API from the `backend` directory:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

The API documentation is then available at `http://127.0.0.1:8000/docs`. Run all implemented tests with:

```powershell
python -m pytest -q
```

## Phase 1 implementation

Phase 1 provides:

- Typed Pydantic settings loaded from `backend/.env`, including required-secret validation and masked secret representations.
- FastAPI application factory, MongoDB lifecycle, wildcard CORS configured without cross-origin cookies, and `GET /health`.
- Motor + Beanie initialization against the configured MongoDB database.
- Beanie models for `users`, `documents`, `redaction_jobs`, `redaction_entities`, `audit_log`, `feedback`, and `batch_jobs`.
- Unique email, ownership, job-status, document/job relationship, audit-ordering, and MongoDB TTL indexes.
- Argon2 password hashing and a 12–128 character password policy requiring lowercase, uppercase, number, and special characters.
- Signed JWT access tokens containing only subject, issue/not-before/expiry, and token-type claims.
- Constant-work password verification for unknown accounts to reduce timing-based email enumeration.
- Active-user bearer authentication and a reusable ownership guard that returns `404` for foreign resources.

### Implemented API endpoints

| Method | Path | Authentication | Purpose |
|---|---|---|---|
| `GET` | `/health` | None | Process health check |
| `POST` | `/api/v1/auth/register` | None | Register an email/password account |
| `POST` | `/api/v1/auth/login` | None | Obtain a bearer access token |
| `GET` | `/api/v1/auth/me` | Bearer JWT | Read the authenticated account |
| `POST` | `/api/v1/documents/upload` | Bearer JWT | Stream and classify one supported document |
| `GET` | `/api/v1/documents/{document_id}` | Bearer JWT, owner only | Read metadata, availability, and expiry status |
| `GET` | `/api/v1/documents/{document_id}/preview` | Bearer JWT, owner only | Read a bounded, non-cacheable original-content preview |
| `POST` | `/api/v1/redaction/run` | Bearer JWT, owner only | Queue PDF/DOCX/XLSX redaction with a privacy mode |
| `GET` | `/api/v1/redaction/{job_id}/status` | Bearer JWT, owner only | Poll queued/processing/complete/error state |
| `GET` | `/api/v1/redaction/{job_id}/report` | Bearer JWT, owner only | Read the privacy-safe entity/confidence report |
| `GET` | `/api/v1/redaction/{job_id}/preview` | Bearer JWT, owner only | Parse a bounded preview from the actual generated redacted file |
| `GET` | `/api/v1/redaction/{job_id}/download` | Bearer JWT, owner only | Download additional copies while authenticated and temporary storage remains valid |

Registration and login accept JSON bodies. Password hashes and raw passwords are never returned by an endpoint.

Redaction-run and batch-upload creation accept an optional `Idempotency-Key` header. Reusing the same key for the same authenticated user returns the previously created job or batch, preventing duplicates after ambiguous network failures.

## Phase 2 implementation

Phase 2 provides:

- Isolated temporary directories under `TEMP_JOB_DIR`, one directory per MongoDB document ObjectId.
- Streamed uploads in 1 MiB chunks with the configured `MAX_UPLOAD_SIZE_BYTES` enforced while writing.
- Atomic partial-file removal for empty, oversized, malformed, mismatched, or failed uploads.
- Unicode-normalized, traversal-safe filenames; client paths are never trusted or returned.
- Root-containment checks on every stored-path read and delete operation.
- Automatic orphan sweeps at startup and every `TEMP_CLEANUP_INTERVAL_SECONDS`, removing entries older than `TEMP_JOB_TTL_SECONDS` without following symlinks.
- MongoDB expiry timestamps and the Phase 1 TTL index as defense in depth.
- Content/structure classification rather than MIME or filename trust:
  - PDF signatures
  - DOCX/XLSX OPC archive structure
  - JPEG/PNG/TIFF parser verification
  - DICOM preamble verification
  - EML header parsing
  - MBOX separator parsing
- Office archive limits for entry count, expanded size, individual entry size, and unsafe compression ratios.
- Image decompression-bomb rejection.
- Owner-only metadata and preview queries that return `404` for another user's document.
- Expired or missing file metadata reported as `status: "expired"`; sensitive preview access is blocked with HTTP `410`.
- `Cache-Control: no-store`, `Pragma: no-cache`, and `X-Content-Type-Options: nosniff` on preview responses.

### Preview behavior

- PDF: up to 10 page thumbnails plus bounded native text and total page count.
- DOCX: bounded paragraph, table, header, and footer text.
- XLSX: bounded rows/columns from up to 20 worksheets, preserving formulas as text for review.
- JPEG/PNG/TIFF: bounded thumbnails, including up to 10 TIFF frames.
- DICOM: bounded pixel thumbnails when decodable plus non-PHI structural metadata; patient metadata is not echoed by the preview summary.
- EML/MBOX: bounded headers and plain-text bodies plus attachment filenames; attachments are not executed or extracted during preview.

Preview is intentionally pre-redaction and can contain PHI. It is therefore authenticated, owner-only, short-lived, and non-cacheable.

### Upload responses

- `201`: stored, classified, and metadata persisted
- `400`: missing filename or empty upload
- `401`: missing or invalid bearer token
- `413`: configured size limit exceeded
- `415`: unsupported, malformed, or extension/content-mismatched file

## Phase 3 implementation

Phase 3 provides:

- A fully local Presidio analyzer backed by `en_core_web_lg`; document text is not sent to any external service.
- Presidio's predefined recognizers for email, phone, SSN, credit card, IP/MAC address, URL, dates, locations, passports, licenses, financial identifiers, and other supported regional identifiers.
- A custom healthcare identifier recognizer with exact sensitive-value offsets for:
  - MRN
  - NPI with the CMS-required `80840` Luhn prefix validation
  - DEA registration number with check-digit validation
  - insurance/member/subscriber identifiers
  - policy numbers
  - ICD-10 diagnosis codes
  - CPT/HCPCS procedure codes
  - payer identifiers
- A Presidio-compatible scispaCy recognizer mapping BC5CDR diseases to `MEDICAL_CONDITION`, chemicals/drugs to `MEDICATION`, and lower-confidence generic biomedical spans to `CLINICAL_ENTITY`.
- Deterministic label-proximity evidence for lines such as `Patient:`, `DOB:`, `MRN:`, and `NPI:`, plus structural labels supplied by the Excel, PDF, DOCX, and email extractors.
- Exact ensemble scoring:

  ```text
  confidence = 0.45 * detector_score
             + 0.25 * pattern_validation
             + 0.20 * context_boost
             + 0.10 * mistral_score
  ```

- Scores at or above the selected mode threshold become `auto_redact`; scores from 0.40 to the threshold become `ambiguity_review`; lower scores remain `reviewed_not_redacted` for audit visibility.
- Mistral review populates the final 10% only for ambiguous candidates; API failure leaves the deterministic decision intact.
- Immutable policies for all five privacy modes, including:
  - patient-portal date and requesting-subject preservation
  - full research/legal wildcard coverage
  - insurance preservation of claim codes, payer/provider identifiers, and billing dates
  - legal privilege-flagging configuration
  - strict custom-rule validation with unknown and conflicting entity rejection
- Sentence/paragraph chunking capped at 2,000 characters with two-sentence overlap and hard splitting for oversized sentences.
- Bounded asynchronous chunk processing using the configured `MAX_CONCURRENT_CHUNKS` semaphore.
- General Presidio/custom-regex inference and scispaCy biomedical inference execute as parallel branches inside each bounded chunk, then merge before structural scoring.
- Restoration of document-global offsets, exact duplicate merging, and near-identical overlap deduplication.
- A document entity cache that propagates an exact high-confidence value to later occurrences without rerunning or weakening its evidence.
- Runtime-only sensitive values and a `safe_report()` representation which cannot serialize the raw matched text.

### Phase 3 model compatibility

AllenAI's current public biomedical artifacts require spaCy 3.7.x. The environment therefore uses the coherent supported versions below instead of mixing spaCy 3.8 with incompatible biomedical models:

| Component | Version |
|---|---:|
| spaCy | 3.7.5 |
| scispaCy | 0.5.5 |
| `en_core_web_lg` | 3.7.1 |
| `en_core_sci_md` | 0.5.4 |
| `en_ner_bc5cdr_md` | 0.5.4 |
| Presidio Analyzer/Anonymizer | 2.2.363 |

All three model packages pass spaCy's official compatibility validator and real inference checks.

## Phase 4 implementation: PDF

Phase 4 provides:

- Native PDF word/character extraction through pdfplumber with page coordinates and document-global offsets.
- Automatic scanned-page fallback when native text is below the minimum useful threshold.
- Scanned rendering at 300 DPI and Tesseract `--psm 6` extraction with OCR pixel boxes mapped back into PDF coordinates.
- Character-level layout tokens for precise partial-token redaction rather than removing an entire surrounding line.
- Detection mapped back to its source page and rectangle.
- PyMuPDF redaction annotations followed by `apply_redactions`, removing underlying PDF text objects rather than drawing a recoverable overlay.
- Pixel-level removal for scanned-page image regions.
- Solid replacement regions containing `[REDACTED]` or `[REDACTED: ENTITY_TYPE]` according to mode/request verbosity.
- Clean, deflated output saves with garbage collection of removed PDF objects.
- Password-protected and malformed PDF rejection without unsafe partial output.

## Phase 5 implementation: DOCX and XLSX

### DOCX

- Direct OOXML traversal and editing of exact `w:t` text nodes.
- Coverage of paragraphs, split runs, tables, headers, footers, and text boxes without flattening the Word package.
- Exact cross-run replacement: the first affected node receives `[REDACTED]` and remaining fragments of the same sensitive span are removed.
- Existing run formatting remains attached to the replacement node.
- Paragraph/table-cell adjacency supplies structural evidence where labels and values live in separate cells.
- Embedded image OCR with exact pixel-region overwrite and replacement text; face/barcode enhancement follows in Phase 6.
- Untouched OOXML/media package members are preserved; unsafe unmapped detections fail the job instead of producing partial redaction.
- `docx2txt` is available as malformed-content fallback, while export fails closed if a sensitive fallback span lacks a safe OOXML location.

### XLSX

- Every worksheet and non-formula populated cell receives exact global/local offsets.
- First-row column headers and adjacent labels provide per-cell structural context without boosting unrelated columns.
- Only matched substrings are replaced, so surrounding cell content remains intact.
- Workbook structure, sheets, styles, number formats, dimensions, merged cells, and formulas remain intact through openpyxl saves.
- Formula cells are never modified; openpyxl clears stale calculated caches when rewriting a workbook.
- Insurance mode preserves diagnosis/procedure codes and other configured claim fields.

## Redaction job and report behavior

- Submission validates ownership, file availability, mode/custom-rule consistency, and supported format before creating a job.
- Background processing moves jobs through `queued`, `processing`, `complete`, or `error` without blocking the request.
- Failures are reduced to safe exception-class messages; filenames, document text, and matched values are not stored in error fields.
- Entity records contain type, page/bounding box where applicable, confidence, detector sources, safe explanation, and decision—never the matched value.
- Ambiguous candidates receive bounded Mistral review when configured; low-confidence candidates remain reviewed/not-redacted.
- Download is owner-only and non-cacheable. A completed output can be downloaded repeatedly while the JWT and temporary storage remain valid; normal TTL cleanup removes the files.
- `qa_passed` is true only after the generated output is re-extracted and passes the full residual-PHI scan.

## Phase 6 implementation: images and DICOM

### Plain images

- JPEG, PNG, and multi-frame TIFF use one shared extraction/redaction contract.
- Tesseract `--psm 6` supplies character-level visible-text coordinates.
- MediaPipe Tasks uses the bundled Google BlazeFace short-range TFLite model; inference is CPU-local and never downloads or uploads image data at runtime.
- Face rectangles are padded by 10% and destructively overwritten with solid black pixels.
- pyzbar detects QR codes and barcodes; their full regions are blacked out regardless of decoded content because the symbol itself is identifying.
- OCR-selected PII receives a black pixel region and `[REDACTED]` where space permits.
- Multi-frame TIFF frame count and timing are preserved.
- Output saves omit EXIF and other source metadata, preventing metadata-carried identifiers from surviving.
- Decompression-bomb protections from Phase 2 remain active before processing.

### DICOM

- The PS3.15 Basic Application Level Confidentiality Profile identifying keywords are hardcoded and traversed recursively through nested sequences.
- Direct metadata identifiers are removed, private tags are removed, and identifying UIDs are consistently remapped with newly generated DICOM UIDs.
- `SOPInstanceUID` and file-meta `MediaStorageSOPInstanceUID` remain synchronized after remapping.
- `PatientIdentityRemoved=YES` and a MedVault de-identification method are written to the output.
- Every decodable frame receives the same MediaPipe face, barcode, and OCR analysis as a plain image.
- Pixel rectangles are written into the original typed pixel array, preserving frame count, dimensions, bit depth, and photometric structure.
- `MONOCHROME1` uses its visually black sample value; other monochrome and color data use zero-valued black regions.
- Compressed transfer syntaxes are decompressed before pixel mutation; undecodable pixel data fails closed.
- Successful burned-in processing sets `BurnedInAnnotation=NO`.
- Reports include safe `DICOM_METADATA`, `FACE`, `BARCODE`, and OCR-derived records without tag values or decoded barcode contents.

## Phase 7 implementation: EML and MBOX

- EML and each MBOX message are parsed with Python's standards-based email package.
- `From`, `To`, `Cc`, and `Subject` are extracted and redacted separately with their own structural labels.
- Plain-text and HTML MIME bodies receive exact substring replacement without flattening the entire MIME message.
- MIME content types, multipart boundaries, attachment filenames, and base64 transfer encoding are reconstructed safely.
- Supported attachments are recursively classified by content and routed through PDF, DOCX, XLSX, image, DICOM, EML, or MBOX processing.
- Nested email/attachment depth is capped at five levels to prevent recursive archive abuse.
- Unsupported or malformed attachments fail the job instead of being copied through without inspection.
- Attachment temporary files are deleted in `finally` paths after extraction and redaction.
- MBOX messages are independently processed so one message's offsets cannot affect another message.

## Phases 8 and 9 implementation

- Only ambiguous spans, their proposed category, and at most ten surrounding tokens on each side are sent to Mistral. Full documents are never sent.
- Mistral responses use strict JSON schemas, bounded concurrency, retry/backoff, leak checks, and deterministic local fallbacks.
- Audit explanations receive category/evidence metadata only and never the underlying matched value.
- Research mode creates document-seeded, internally consistent synthetic names, emails, phones, dates, locations, identifiers, and category-safe clinical replacements.
- Synthetic mappings remain process-memory only and are never stored in MongoDB or returned in reports.
- Every rendered output is re-extracted and passed through the detector stack before the job can become `complete`.
- Residual PHI changes the job to `qa_failed`; the existing download endpoint rejects every state other than `complete`.
- Research jobs receive a low/medium/high re-identification score based on surviving exact age, age band, gender, ZIP3, and clinical quasi-identifiers. Reports expose only safe factor names.

## Phases 10 and 11 implementation

- Document upload, redaction start/completion/failure, feedback, and each session export create canonical SHA-256 audit entries chained to the previous entry.
- `GET /audit/{document_id}` returns the owner-scoped append-only trail; `GET /audit/verify/{document_id}` recomputes every link and reports the first broken entry.
- Feedback accepts correct/false-positive entity verdicts and document-level missed-entity reports without storing the missed PHI value.
- `POST /redaction/compare-modes` compares the latest completed runs for two to five modes using safe entity-category counts.
- `GET /redaction/{job_id}/heatmap` returns a no-store SVG made only from page coordinates and confidence intensity; original text is never rendered.
- Batch upload accepts up to `MAX_BATCH_FILES`, creates isolated document/redaction jobs, and contains each item failure independently.
- Batch status exposes per-file terminal states, while batch ZIP export includes successful redacted files and a combined privacy-safe compliance report.
- Authenticated devices can register an HTTPS Web Push subscription. Terminal jobs attempt VAPID delivery and fall back to optional TLS SMTP without including document contents or entity values.
- Legal discovery detects attorney-client, work-product, counsel, and privileged-note context and persists the corresponding safe `privileged_flag`.
- Correct/false-positive/missed feedback produces a user-local, Laplace-smoothed detector adjustment capped at ±0.10; missed reports require entity category and page location.
- Mode comparison automatically executes any missing selected mode before calculating the category-count difference.
- Audit chains use a unique per-document sequence index with optimistic retry, preventing competing worker writes from creating undetected forks.
- Audit decision records contain each safe explanation, category, confidence, decision, and privilege status, never the matched value.
- The batch worker polls MongoDB and resumes queued or interrupted batches; archive names include document identifiers to prevent filename collisions.

## Local mixed-content benchmark

Run `python scripts/benchmark_mixed_pdf.py --output-json benchmark_results.json` from `backend/` to regenerate the synthetic benchmark. It creates ten pages (five native, five scanned/OCR), exercises the real detector models, performs destructive PDF redaction, and reruns residual-PHI QA.

Validated local result on the configured Python 3.12 environment:

- 10 pages: 5 native and 5 scanned
- 306 candidates reviewed; 80 automatically redacted
- residual-PHI QA passed
- 609,957-byte input and 479,433-byte output
- extraction 5.982 s, detection 17.108 s, rendering 0.727 s, QA 0.258 s
- total processing time 24.075 s
- the configured MongoDB Atlas connection and all Beanie indexes initialize successfully via `python scripts/check_database.py`
- the configured Mistral key, strict JSON response, bounded ambiguity review, and non-leaking explanation path pass a synthetic-only live check via `python scripts/check_mistral.py`

### Verification

- The complete non-deployment backend test suite passes: 116 tests.
- Python compilation succeeds for application and test modules.
- `pip check` reports no broken dependencies.
- The configured MongoDB connection initializes successfully with all declared Beanie collections and indexes.
- OpenAPI contains the four Phase 4–5 redaction paths in addition to all Phase 1–2 paths.
- Tests cover traversal, root deletion refusal, streamed size limits, partial cleanup, TTL sweeps, format mismatch, ownership isolation, expired files, no-cache headers, and real parser previews for all supported format families.
- Detection tests cover checksum acceptance/rejection, exact span boundaries, mode preservation, custom-rule failures, exact confidence arithmetic, structural context, chunk overlap, global offsets, bounded concurrency, deduplication, entity-cache propagation, and raw-value-safe reports.
- A real ensemble integration test detects general PII, MRN/NPI, medication, and disease entities using Presidio plus all installed spaCy/scispaCy models.
- Native PDF tests prove original sensitive text is absent from extracted output text after redaction.
- Scanned-PDF tests re-render and OCR output to prove the sensitive pixel text is absent.
- DOCX tests cover split bold runs, tables, headers, nested text boxes, and embedded-image OCR redaction.
- XLSX tests prove exact substring replacement while formulas and cell styling remain unchanged.
- API verification covers background completion, privacy-safe reports, cross-user isolation, sanitized failures, repeat session downloads, and TTL cleanup.
- The bundled BlazeFace model initializes successfully through MediaPipe Tasks, and a real generated QR code is detected through pyzbar.
- Image tests prove OCR text, forced face boxes, and forced barcode boxes are physically blacked out while multi-frame TIFF remains multi-frame.
- DICOM tests prove identifying/private tags are absent, UIDs are remapped consistently, multi-frame structure survives, and burned-in email text is absent under re-OCR.
- EML tests prove header, body, nested EML, and attached-PDF values are removed; MBOX tests prove independent multi-message reconstruction.
- The processing registry and download MIME map cover exactly PDF, DOCX, XLSX, JPEG, PNG, TIFF, DICOM, EML, and MBOX.

## Privacy and security invariants

## Review, controlled sharing, and privacy intelligence

The completed-output workflow now has three additional safeguards and demonstration features:

- `GET /review/{job_id}` provides an owner-only human-review queue with category, confidence, page, and safe explanation metadata. It never returns matched values.
- `PUT /review/{job_id}/entities/{entity_id}` records a `confirmed`, `flagged`, or `pending` finding decision. `POST /review/{job_id}/finalize` approves the output only when every finding is decided and none is flagged. All decisions are hash-chained audit events.
- `POST /shares/{job_id}` creates a cryptographically random, revocable, expiring share link for a QA-passed and review-approved output. Links may be password protected, recipient-labelled, review-only, or download-enabled, and can enforce a maximum download count. `GET /shares/{job_id}` lists the owner's links and `POST /shares/{share_id}/revoke` disables one immediately.
- `POST /shares/public/{token}` and `/download` provide the recipient workflow. They expose only redacted-file metadata, enforce expiry/password/access limits, deliver the source-compatible redacted artifact, and audit downloads. Original documents are never available through a share link.
- When `recipient_email` is provided, a privacy-safe SMTP message delivers the controlled share URL. The email contains no document name, source text, or PHI. Set `FRONTEND_PUBLIC_URL` to the deployed frontend HTTPS origin before production use; it defaults to the local frontend during development.
- `GET /intelligence/jobs/{job_id}` provides per-document, PHI-free category/detector counts, QA/review state, risk factors, and next-step recommendations. `GET /intelligence/workspace` provides owner-scoped aggregate rates and trends.

The frontend exposes these through the completed-job **Review queue**, **Secure share**, and **Intelligence** tabs; the dashboard adds a compact privacy-intelligence summary; and `/share/:token` is a standalone recipient page.

- Raw matched PHI/PII must never be stored in MongoDB audit or entity records.
- Raw documents and redacted outputs exist only in TTL-controlled temporary directories.
- Redaction must remove underlying text/pixels destructively, not cover recoverable content.
- Export remains blocked whenever post-redaction QA detects residual PHI.
- Mistral receives only an ambiguous span and a small context window, never a full document.
- Explanations describe entity categories and evidence without repeating sensitive values.
- Every protected endpoint enforces authenticated document ownership; privacy modes are not roles.
