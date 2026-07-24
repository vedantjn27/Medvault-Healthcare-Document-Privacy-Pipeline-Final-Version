# MedVault — System Architecture

> High-level architecture reference for the MedVault Healthcare Document Privacy Pipeline.

---

## Overview

MedVault is designed around three non-negotiable principles:

1. **No PHI at rest** — Raw document files exist only in ephemeral temp directories during active job processing (maximum 1-hour TTL). MongoDB stores only metadata: entity types, locations, confidence scores, and audit hashes — never the text content of any PHI.

2. **Destructive redaction** — PHI is physically removed from output files using PyMuPDF's `apply_redactions()` (for PDFs), pixel overwrite (for images), and run-level text replacement (for DOCX/XLSX). There is no recoverable overlay.

3. **Self-verifying outputs** — Every redacted file is re-OCR'd and re-scanned by the full detection stack before export is permitted. A QA failure status blocks the download endpoint until the issue is resolved.

---

## System Boundary Diagram

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              BROWSER (User)                                    │
│                                                                                │
│   React 19 SPA                                                                 │
│   TanStack Router · TanStack Query · Radix UI · Tailwind CSS v4                │
│   Motion animations · Recharts · Lucide icons                                  │
│                                                                                │
│   Pages: Landing · Auth · Dashboard · Upload · Job Detail · Batch             │
│           Compare Modes · Audit · Settings · Contact · Secure Share            │
└────────────────────────────────────┬───────────────────────────────────────────┘
                                     │
                              HTTPS / REST
                              JWT Bearer token
                              /api/v1/* prefix
                                     │
┌────────────────────────────────────▼───────────────────────────────────────────┐
│                         FastAPI Application (Python 3.12)                       │
│                           Deployed on Render                                    │
│                                                                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │   auth   │  │documents │  │redaction │  │  batch   │  │   sharing    │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────────┘    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────────────────┐    │
│  │  audit   │  │  review  │  │intelli-  │  │       Background Workers   │    │
│  │  trail   │  │  queue   │  │  gence   │  │  temp-cleanup · batch-job  │    │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────────────────┘    │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                        DETECTION PIPELINE                                │  │
│  │                                                                          │  │
│  │  Input text chunks (paragraph/page, 2-sentence sliding overlap)         │  │
│  │                                                                          │  │
│  │  ┌───────────────┐  ┌───────────────┐  ┌──────────────┐  ┌──────────┐  │  │
│  │  │   Presidio    │  │   scispaCy    │  │Custom Regex  │  │ Context  │  │  │
│  │  │  Built-in     │  │  Medical NER  │  │  MRN/NPI     │  │  Boost   │  │  │
│  │  │  Recognizers  │  │  BC5CDR model │  │  DEA/Ins.    │  │  Engine  │  │  │
│  │  └───────────────┘  └───────────────┘  └──────────────┘  └──────────┘  │  │
│  │                                ↓                                         │  │
│  │                    Merge + deduplicate by span offset                    │  │
│  │                    Document-level entity cache                           │  │
│  │                                ↓                                         │  │
│  │          confidence = 0.45×detector + 0.25×pattern                      │  │
│  │                     + 0.20×context + 0.10×mistral                       │  │
│  │                                ↓                                         │  │
│  │         ┌─────────────────────────────────────────┐                     │  │
│  │         │     Mistral AI Ambiguity Resolver        │                     │  │
│  │         │  (only for spans scoring 0.40–0.75)     │                     │  │
│  │         │  ±10 token context · JSON mode · No PHI │                     │  │
│  │         │  Local template fallback if no API key  │                     │  │
│  │         └─────────────────────────────────────────┘                     │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                         REDACTION ENGINE                                 │  │
│  │                                                                          │  │
│  │  Mode filter → Allow/deny list per privacy mode                         │  │
│  │                                                                          │  │
│  │  PDF:   PyMuPDF add_redact_annot + apply_redactions + [REDACTED] text  │  │
│  │  DOCX:  python-docx run-level replacement (preserves formatting)        │  │
│  │  XLSX:  openpyxl cell value clear (formula cells untouched)             │  │
│  │  Image: Pillow pixel overwrite (MediaPipe faces + pyzbar barcodes)      │  │
│  │  DICOM: PS3.15 tag strip + pixel region overwrite                       │  │
│  │  EML:   Header + body redaction + recursive attachment routing          │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌──────────────────────────┐   ┌─────────────────────────────────────────┐  │
│  │       QA VERIFIER        │   │          OUTPUT GENERATOR               │  │
│  │                          │   │                                         │  │
│  │  Re-OCR redacted output  │   │  Confidence heatmap PNG (per-page)      │  │
│  │  Re-run detection stack  │   │  Compliance report PDF                  │  │
│  │  QA_FAILED → blocks DL   │   │  ZIP export (batch)                    │  │
│  │  QA_PASSED → unlocks DL  │   │  Hash-chain audit entry                │  │
│  └──────────────────────────┘   └─────────────────────────────────────────┘  │
│                                                                                │
└──────────────┬──────────────────────────────────────────┬─────────────────────┘
               │                                          │
               ▼                                          ▼
┌─────────────────────────────┐            ┌─────────────────────────────────┐
│    MongoDB Atlas M0 (Free)  │            │   Ephemeral Temp Storage        │
│                             │            │   /tmp/medvault_jobs/{job_id}/  │
│  Metadata only — NO files   │            │                                 │
│  NO raw PHI values          │            │   Created: per job              │
│                             │            │   Deleted: TTL 1hr or download  │
│  collections:               │            │   Zero PHI survives a redeploy  │
│  • users                    │            └─────────────────────────────────┘
│  • documents                │
│  • redaction_jobs           │            ┌─────────────────────────────────┐
│  • redaction_entities       │            │   SMTP Email (optional)         │
│  • audit_log (hash-chain)   │            │   Brevo / Gmail App Password    │
│  • feedback                 │            │   For secure share notifications │
│  • batch_jobs               │            └─────────────────────────────────┘
│  • share_links              │
└─────────────────────────────┘            ┌─────────────────────────────────┐
                                           │   Web Push (VAPID, optional)    │
                                           │   Job completion browser alerts  │
                                           └─────────────────────────────────┘
```

---

## Privacy Mode Architecture

The privacy mode system is implemented as a set of **pure Python dataclasses** in `backend/app/redaction/mode_configs.py`. Adding a new mode requires only editing this one file — no pipeline logic changes.

```
Request: { document_id, privacy_mode: "research_sharing", custom_rules: null }
          │
          ▼
ModeConfig = load_mode_config("research_sharing")
  → confidence_threshold: 0.65
  → entity_types_to_redact: [all 18 HIPAA Safe Harbor identifiers]
  → entity_types_to_preserve: []
  → synthetic_replacement: True
  → privileged_tagging: False
  → verbosity: "[REDACTED]"    (no entity type label in research mode)
          │
          ▼
Detection pipeline runs with ModeConfig injected as context
          │
          ▼
Mode filter: each detected entity checked against allow/deny list
          │
          ▼
Redaction: entities passing filter are redacted
Synthetic: for research_sharing, replaced with Faker values
          │
          ▼
Risk scoring: k-anonymity check on surviving structured fields
          │
          ▼
Output: { redacted_file, heatmap, report_pdf, risk_badge }
```

### Mode Comparison Feature

The `POST /redaction/compare-modes` endpoint accepts `{document_id, modes: [...]}` and runs the pipeline for each mode independently. The result is a structured diff showing per-mode entity counts and a side-by-side preview of redacted output. This is implemented without storing intermediate files — each mode's redaction runs sequentially against the same extracted text cache.

---

## Audit Trail Architecture

The audit log is the trust anchor of the system. It is designed to be:
- **Append-only** — no update or delete endpoints exist for the `audit_log` collection
- **Hash-chained** — each entry includes the SHA-256 hash of the previous entry
- **Verifiable** — the `/audit/verify/{document_id}` endpoint walks the chain and confirms integrity

```
Entry N-1:
  entry_hash = sha256("0000...000" + entry_N-1_json)

Entry N:
  entry_hash = sha256(entry_N-1.entry_hash + entry_N_json)
  previous_hash = entry_N-1.entry_hash

Verify:
  Walk all entries for document_id in creation order
  Recompute each entry_hash from (previous_hash + entry_json)
  Compare to stored entry_hash
  Any mismatch → integrity failure reported
```

This approach does not require blockchain infrastructure — it is a self-verifying chain of MongoDB documents that proves the log was not retroactively edited.

---

## Confidence Scoring Architecture

```
Span: "John Alvarez" at position [45:57] in page 2

Layer 1 — Presidio score:        0.85  (PERSON entity, high confidence)
Layer 2 — Pattern validation:    1.00  (name structure validated)
Layer 3 — Context boost:         0.95  (preceded by "Patient:" label, 3 tokens prior)
Layer 4 — Mistral score:         N/A   (span already above 0.75 threshold)

Composite:
  confidence = 0.45 × 0.85  +  0.25 × 1.00  +  0.20 × 0.95  +  0.10 × 0.0
             = 0.3825        +  0.25         +  0.19          +  0.0
             = 0.82

Decision: confidence 0.82 >= threshold 0.75 → Auto-redact
Explanation: "Redacted as PATIENT_NAME — appeared directly after a 'Patient:' label
              and matched person-name structure (confidence 0.82)"
```

---

## Data Flow — Single Document

```
User Browser                Backend                    Storage
     │                         │                          │
     │── POST /documents/upload ─►                        │
     │                         │── create temp dir ──────►│
     │◄─ { document_id } ──────│                          │
     │                         │                          │
     │── POST /redaction/run ──►│                          │
     │◄─ { job_id } ───────────│                          │
     │                         │                          │
     │     (polling)           │── extract text ──────────►│
     │── GET /redaction/status ─►── detect PHI            │
     │◄─ { status: processing }│── score confidence       │
     │                         │── resolve ambiguity (Mistral)
     │── GET /redaction/status ─►── apply mode filter     │
     │◄─ { status: processing }│── redact output file ────►│
     │                         │── QA verify              │
     │                         │── generate heatmap ──────►│
     │                         │── write audit entry      │
     │                         │── save job metadata ──►MongoDB
     │                         │                          │
     │── GET /redaction/status ─►                         │
     │◄─ { status: complete }  │                          │
     │                         │                          │
     │── GET /redaction/download►── read redacted file ───►│
     │◄─ [file bytes] ─────────│── delete temp dir ──────►│
     │                         │                          │
```

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         PRODUCTION                              │
│                                                                 │
│  ┌───────────────────┐          ┌───────────────────────────┐  │
│  │  Vercel           │          │  Render (Web Service)     │  │
│  │  (Frontend)       │          │  (Backend)                │  │
│  │                   │          │                           │  │
│  │  React SPA        │◄────────►│  FastAPI + Uvicorn        │  │
│  │  Static build     │  REST    │  Python 3.12              │  │
│  │  CDN-distributed  │  HTTPS   │  Workers: 1-2 (CPU-bound) │  │
│  │                   │          │  System: Tesseract, zbar  │  │
│  └───────────────────┘          └──────────────┬────────────┘  │
│                                                │               │
│                                    ┌───────────▼────────────┐  │
│                                    │  MongoDB Atlas (M0)    │  │
│                                    │  512MB · Free forever  │  │
│                                    │  External managed DB   │  │
│                                    │  Not a Render add-on   │  │
│                                    └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

RENDER CONFIGURATION:
  Root Directory: backend
  Build Command:  pip install -r requirements.txt
  Start Command:  uvicorn app.main:app --host 0.0.0.0 --port $PORT
  apt.txt:        tesseract-ocr poppler-utils libgl1 libzbar0
  TEMP_JOB_DIR:   /tmp/medvault_jobs  (ephemeral, per-request lifecycle)
  WEB_CONCURRENCY: 1-2 (OCR/CV workloads are CPU-heavy)
```

---

## Security Architecture

| Concern | Mitigation |
|---------|-----------|
| **PHI at rest** | Files deleted within 1-hour TTL; only metadata persists in MongoDB |
| **Raw PHI in database** | `redaction_entities` stores entity TYPE + LOCATION + EXPLANATION, never the PHI value |
| **Audit tampering** | SHA-256 hash chain; append-only collection; no update/delete routes exposed |
| **Redaction bypass** | QA loop re-OCRs and re-scans output; blocks download on failure |
| **Overlay attack** | PyMuPDF `apply_redactions()` is destructive — no text layer survives under visual boxes |
| **AI data leakage** | Mistral receives only ±10 token context window, never full documents |
| **Share link abuse** | Password protection, per-link expiry, per-link download caps, revocation |
| **Authentication** | JWT with Argon2-hashed passwords; no SMS/phone number collected |
| **CORS** | Explicit origin allowlist; credentials blocked for wildcard origins |
| **Upload safety** | File size limit (50MB); file type validation; per-job isolation |

---

## Technology Rationale Summary

| Choice | Alternative Considered | Why This Was Chosen |
|--------|----------------------|---------------------|
| **Microsoft Presidio** | Hand-rolled spaCy regex | Purpose-built PII framework; higher out-of-box accuracy; MIT licensed; pluggable |
| **scispaCy** | Generic spaCy | Trained on biomedical text; catches clinical entities that generic NER misses |
| **MongoDB** | PostgreSQL | Document-oriented fits variable-length entity arrays; no migration overhead for schema evolution |
| **Destructive PyMuPDF redaction** | Black-box overlay | Prevents copy-paste recovery of "redacted" content — the most common real-world failure mode |
| **Process-and-discard storage** | Object storage (S3, R2) | Zero PHI at rest; no storage cost; no Render paid disk add-on needed |
| **Mistral AI** | OpenAI GPT | User's explicit preference; comparable capability; competitive pricing |
| **VAPID Web Push** | Twilio SMS | Free, no third-party account required, no phone number collection |
| **Beanie ODM** | pymongo raw | Pydantic-native; auto-validates on insert; reuses FastAPI's Pydantic schema |
| **BackgroundTasks** | Celery + Redis | No additional infrastructure on free-tier deploy; clear upgrade path exists |
