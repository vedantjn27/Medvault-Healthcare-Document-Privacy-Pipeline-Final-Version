# MedVault — Folder Structure

> Complete annotated directory tree for the MedVault Healthcare Document Privacy Pipeline.

---

```
Medvault- Healthcare Document Privacy Pipeline Final Version/
│
│  ── Root-level documentation ──────────────────────────────────────
├── README.md                          Project overview, architecture, feature set
├── SETUP_GUIDE.md                     Local dev and production deployment steps
├── FOLDER_STRUCTURE.md                This file — annotated directory tree
├── ARCHITECTURE.md                    High-level system design document
├── LICENSE                            Apache License 2.0
├── MANUAL_TESTING_GUIDE.md            End-to-end manual test scenarios
├── MEDVAULT_V2_IMPLEMENTATION.md      Original v2 implementation specification
├── TEST_CREDENTIALS.txt               Synthetic test account (local dev only)
├── requirements.txt                   Top-level convenience requirements
├── .gitignore                         Git ignore rules
│
│  ── Visual assets ──────────────────────────────────────────────────
├── docs/
│   ├── architecture_diagram.png       System architecture diagram (generated)
│   └── workflow_diagram.png           8-stage processing pipeline diagram
│
│  ── Backend (FastAPI · Python 3.12) ────────────────────────────────
├── backend/
│   ├── .env                           Active environment variables (git-ignored)
│   ├── .env.example                   Template for all environment variables
│   ├── requirements.txt               Python package dependencies
│   ├── apt.txt                        System packages for Render deployment
│   │                                  (tesseract-ocr, poppler-utils, libgl1, libzbar0)
│   ├── README.md                      Backend-specific notes
│   ├── SAMPLE_FILES.md                Description of synthetic test files
│   │
│   ├── .venv/                         Python virtual environment (git-ignored)
│   │
│   ├── sample_files/                  Synthetic test documents (NO real PHI)
│   │   ├── pdf/                       Five mode-specific PDF files
│   │   │   ├── patient_portal_mode.pdf
│   │   │   ├── research_sharing_mode.pdf
│   │   │   ├── insurance_processing_mode.pdf
│   │   │   ├── legal_discovery_mode.pdf
│   │   │   └── custom_mode.pdf
│   │   ├── docx/                      Word documents with embedded images
│   │   │   └── mixed_text_and_embedded_image.docx
│   │   ├── xlsx/                      Excel spreadsheets with PHI-labelled columns
│   │   ├── dicom/                     Synthetic DICOM scan files
│   │   ├── jpeg/                      JPEG images with visible faces and text
│   │   ├── png/                       PNG image variants
│   │   ├── tiff/                      TIFF image files
│   │   ├── eml/                       Email archive files (.eml format)
│   │   └── mbox/                      Mailbox files (.mbox format)
│   │
│   ├── scripts/                       Utility scripts (key generation, etc.)
│   │
│   └── app/                           Application source code
│       ├── __init__.py                Package marker; app version string
│       ├── main.py                    FastAPI application factory
│       │                              Registers all routers; manages lifespan:
│       │                              - Database connection/disconnection
│       │                              - Temp-file cleanup background task
│       │                              - Batch job worker background task
│       │                              - CORS middleware configuration
│       │
│       ├── config.py                  Pydantic Settings class
│       │                              All environment variables typed and validated:
│       │                              - MongoDB URI, JWT secret, Mistral API key
│       │                              - VAPID keys, SMTP config, file size limits
│       │                              - Tesseract path, temp directory config
│       │
│       ├── auth/                      Authentication module
│       │   ├── __init__.py
│       │   ├── routes.py              POST /auth/register, /auth/login
│       │   │                          POST /auth/push/subscribe (VAPID)
│       │   ├── jwt.py                 Token creation, verification, dependency
│       │   └── push.py                Web Push subscription storage + send
│       │
│       ├── documents/                 Document management module
│       │   ├── __init__.py
│       │   ├── routes.py              POST /documents/upload
│       │   │                          GET /documents/{id}
│       │   │                          GET /documents/{id}/preview
│       │   └── extractors/            Per-format text + layout extraction
│       │       ├── pdf_extractor.py   pdfplumber (native) + Tesseract (OCR)
│       │       │                      Returns: text chunks + bounding boxes
│       │       ├── docx_extractor.py  python-docx paragraph/run/table walker
│       │       ├── xlsx_extractor.py  openpyxl cell iterator with column context
│       │       ├── dicom_extractor.py pydicom tag reader + pixel data renderer
│       │       ├── image_extractor.py Tesseract OCR + MediaPipe + pyzbar
│       │       └── email_extractor.py email module + recursive attachment routing
│       │
│       ├── detection/                 PHI/PII detection ensemble
│       │   ├── __init__.py
│       │   ├── pipeline.py            Main detection orchestrator:
│       │   │                          - Async chunked processing (4 concurrent)
│       │   │                          - Document-level entity cache
│       │   │                          - Deduplication by span offset
│       │   ├── presidio_setup.py      Presidio AnalyzerEngine initialization
│       │   │                          Registers custom recognizers as plugins
│       │   ├── medical_recognizers.py PatternRecognizer subclasses:
│       │   │                          MRNRecognizer, NPIRecognizer (checksum),
│       │   │                          DEARecognizer, InsuranceRecognizer
│       │   ├── scispacy_recognizer.py EntityRecognizer wrapping scispaCy
│       │   │                          (en_core_sci_md + en_ner_bc5cdr_md)
│       │   ├── context_boost.py       Label proximity scorer:
│       │   │                          - Excel column header detection
│       │   │                          - Inline label ("DOB:", "Patient:") detection
│       │   │                          - Section header context propagation
│       │   └── types.py               DetectedEntity, SpanResult dataclasses
│       │
│       ├── redaction/                 Redaction pipeline and engine
│       │   ├── __init__.py
│       │   ├── pipeline.py            Main redaction orchestrator:
│       │   │                          extract → detect → filter → redact → audit
│       │   ├── mode_configs.py        5 privacy mode dataclasses:
│       │   │                          - patient_portal, research_sharing
│       │   │                          - insurance_processing, legal_discovery
│       │   │                          - custom (JSON-schema validated)
│       │   ├── confidence.py          Composite confidence formula:
│       │   │                          0.45×detector + 0.25×pattern
│       │   │                          + 0.20×context + 0.10×mistral
│       │   ├── dicom_tags.py          PS3.15 Annex E tag dictionary (~50 tags)
│       │   │                          PatientName, PatientID, PatientBirthDate,
│       │   │                          InstitutionName, ReferringPhysicianName, etc.
│       │   ├── feedback_learning.py   Active learning feedback weight update
│       │   ├── report_pdf.py          Compliance PDF report generation
│       │   │                          (Pillow/ReportLab: counts, charts, QA status)
│       │   ├── routes.py              POST /redaction/run
│       │   │                          GET /redaction/{id}/status|report|download
│       │   │                          GET /redaction/{id}/heatmap|preview
│       │   │                          POST /redaction/{id}/feedback
│       │   │                          POST /redaction/compare-modes
│       │   └── redactors/             Per-format redaction writers
│       │       ├── pdf_redactor.py    PyMuPDF add_redact_annot + apply_redactions
│       │       │                      + [REDACTED] text insertion at bbox
│       │       ├── docx_redactor.py   python-docx run-level text replacement
│       │       │                      preserving font/bold/formatting
│       │       ├── xlsx_redactor.py   openpyxl cell value clear
│       │       │                      formula cells preserved
│       │       └── image_redactor.py  Pillow pixel overwrite (solid fill)
│       │                              Face region + barcode region overwrite
│       │
│       ├── ai/                        AI integration module
│       │   ├── __init__.py
│       │   └── mistral_agent.py       Mistral AI client with:
│       │                              - Retry/backoff wrapper
│       │                              - Job A: ambiguity resolution (JSON mode)
│       │                              - Job B: explanation generation
│       │                              - Local template fallback (no API key)
│       │                              - Never sends full document, only ±10 tokens
│       │
│       ├── qa/                        Quality assurance module
│       │   ├── __init__.py
│       │   └── redaction_verifier.py  Re-OCR on redacted output file
│       │                              Re-runs detection stack on extracted text
│       │                              Sets job status: qa_failed if PHI found
│       │
│       ├── risk/                      Re-identification risk module
│       │   ├── __init__.py
│       │   └── reidentification.py    k-anonymity style scoring over surviving fields
│       │                              Returns: low | medium | high
│       │                              Used in research_sharing mode
│       │
│       ├── synthetic/                 Synthetic data replacement module
│       │   ├── __init__.py
│       │   └── faker_replacement.py   Faker-based plausible replacements:
│       │                              DOB → same age-band, same season
│       │                              Name → culturally-matched fake name
│       │                              Document-seeded for cross-page consistency
│       │
│       ├── audit/                     Audit trail module
│       │   ├── __init__.py
│       │   ├── hash_chain.py          SHA-256 hash chain:
│       │   │                          entry_hash = sha256(prev_hash + entry_json)
│       │   │                          Append-only; no update/delete path exposed
│       │   └── routes.py              GET /audit/{document_id}
│       │                              GET /audit/verify/{document_id}
│       │
│       ├── review/                    Human review queue module
│       │   ├── __init__.py
│       │   └── routes.py              GET /review/{job_id}
│       │                              POST /review/{job_id}/confirm/{entity_id}
│       │                              POST /review/{job_id}/flag/{entity_id}
│       │                              POST /review/{job_id}/approve
│       │                              POST /review/{job_id}/request-changes
│       │
│       ├── sharing/                   Secure sharing module
│       │   ├── __init__.py
│       │   ├── routes.py              POST /sharing/{job_id}/links (create link)
│       │   │                          GET /sharing/{job_id}/links (list)
│       │   │                          DELETE /sharing/links/{link_id} (revoke)
│       │   │                          GET /sharing/public/{token} (public viewer)
│       │   └── email.py               SMTP email dispatch for share notifications
│       │
│       ├── intelligence/              Privacy analytics module
│       │   ├── __init__.py
│       │   └── routes.py              GET /intelligence/dashboard
│       │                              Returns: coverage%, QA rate, review rate,
│       │                              avg redactions, risk distribution, category breakdown
│       │
│       ├── batch/                     Batch processing module
│       │   ├── __init__.py
│       │   ├── routes.py              POST /batch/upload
│       │   │                          GET /batch/{id}/status
│       │   │                          GET /batch/{id}/download (ZIP)
│       │   └── job_runner.py          AsyncIO background worker:
│       │                              Per-file isolation (try/except)
│       │                              One failed file does not stop others
│       │
│       ├── storage/                   File storage management module
│       │   ├── __init__.py
│       │   └── temp_manager.py        Per-job temp directory creation
│       │                              TTL sweep (default 1-hour)
│       │                              Auto-delete orphaned job folders
│       │                              No persistent disk; ephemeral only
│       │
│       ├── db/                        Database layer
│       │   ├── __init__.py
│       │   ├── client.py              Motor async client initialization
│       │   │                          Beanie init_beanie() on startup
│       │   │                          Graceful connection close on shutdown
│       │   └── models.py              Beanie Document models (Pydantic):
│       │                              User, Document, RedactionJob,
│       │                              RedactionEntity, AuditLog,
│       │                              Feedback, BatchJob, ShareLink
│       │
│       └── assets/                    Static assets (e.g., report template images)
│
│  ── Frontend (React 19 · TypeScript · TanStack) ─────────────────────
└── frontend/
    ├── .env                           Active environment variables (git-ignored)
    ├── .env.example                   Template (VITE_API_BASE_URL)
    ├── package.json                   NPM dependencies and scripts
    ├── package-lock.json              Locked dependency tree
    ├── tsconfig.json                  TypeScript compiler options
    ├── vite.config.ts                 Vite build configuration
    ├── eslint.config.js               ESLint rules
    ├── .prettierrc                    Prettier formatting rules
    ├── components.json                shadcn/ui configuration
    │
    ├── public/                        Static public assets
    │
    └── src/
        ├── start.ts                   TanStack Start entry point
        ├── router.tsx                 TanStack Router setup
        ├── server.ts                  Server-side entry (SSR config)
        ├── routeTree.gen.ts           Auto-generated route tree (do not edit)
        ├── styles.css                 Global CSS + Tailwind v4 base styles
        │
        ├── routes/                    File-based routing (TanStack Router)
        │   ├── __root.tsx             Root layout: HTML shell, theme provider
        │   ├── README.md              Routes documentation
        │   ├── index.tsx              Public landing page
        │   │                          Animated hero section, feature highlights,
        │   │                          dark/light theme toggle, navigation
        │   ├── auth.login.tsx         Login form with JWT token handling
        │   ├── auth.register.tsx      Registration form with validation
        │   ├── app.tsx                Protected route wrapper (requires auth)
        │   ├── app.index.tsx          Main dashboard:
        │   │                          Privacy intelligence summary cards,
        │   │                          recent documents list, session stats
        │   ├── app.upload.tsx         Single document upload:
        │   │                          Drag-and-drop, mode selection, progress
        │   ├── app.documents.$documentId.tsx
        │   │                          Document detail page:
        │   │                          Original preview, job history, new job button
        │   ├── app.jobs.$jobId.tsx    Job detail page (largest route):
        │   │                          Original + redacted previews,
        │   │                          Confidence heatmap viewer,
        │   │                          Entity report with explanations,
        │   │                          Human review queue,
        │   │                          Secure share link management,
        │   │                          Download controls,
        │   │                          Re-identification risk badge
        │   ├── app.batch.tsx          Batch section layout
        │   ├── app.batch.index.tsx    Batch upload (multi-file drag-and-drop)
        │   │                          Per-file status tracking
        │   ├── app.batch.$batchId.tsx Batch job detail with ZIP download
        │   ├── app.compare.tsx        Mode comparison view:
        │   │                          Upload + select 2-5 modes,
        │   │                          Side-by-side redacted output previews,
        │   │                          Category/count diff table
        │   ├── app.audit.tsx          Audit trail viewer:
        │   │                          Event list with timestamps,
        │   │                          Hash integrity verify button
        │   ├── app.settings.tsx       Push notification settings:
        │   │                          Enable/disable, permission state display
        │   ├── app.contact.tsx        Contact page:
        │   │                          Email, phone, LinkedIn cards in sidebar
        │   └── share.$token.tsx       Public secure-share viewer:
        │                              Token validation, password entry,
        │                              Redacted file metadata, download (if recipient)
        │
        ├── components/               Shared React components
        │   ├── app-shell.tsx         Main application shell:
        │   │                         Collapsible sidebar navigation,
        │   │                         Top bar with mode selector + theme toggle,
        │   │                         Responsive layout
        │   ├── active-privacy-mode-selector.tsx
        │   │                         Top-bar mode dropdown:
        │   │                         Patient Portal / Research Sharing /
        │   │                         Insurance Processing / Legal Discovery / Custom
        │   │                         Custom sub-form with entity type picker
        │   ├── document-preview.tsx  Document viewer component:
        │   │                         Page thumbnail navigation,
        │   │                         Zoomable text/image preview
        │   ├── capsule-loader.tsx    Animated job progress indicator:
        │   │                         Rotating capsule SVG during processing
        │   ├── theme-toggle.tsx      Dark/light mode toggle button
        │   ├── error-banner.tsx      Error display component
        │   ├── logo.tsx              MedVault logo component
        │   └── ui/                   Radix + shadcn component library:
        │       (accordion, alert, avatar, badge, button, calendar,
        │        card, checkbox, collapsible, command, context-menu,
        │        dialog, dropdown-menu, form, hover-card, input,
        │        label, menubar, navigation-menu, popover, progress,
        │        radio-group, scroll-area, select, separator, sheet,
        │        skeleton, slider, sonner, switch, table, tabs,
        │        textarea, toast, toggle, toggle-group, tooltip)
        │
        ├── hooks/                    Custom React hooks
        │   (auth state, API query hooks, push subscription)
        │
        └── lib/                     Utilities and API client
            (API client with JWT auth headers, class merge utilities)
```

---

## Module Responsibility Summary

| Module | Responsibility | Key Files |
|--------|---------------|-----------|
| `auth/` | JWT authentication, VAPID push subscription | `routes.py`, `jwt.py`, `push.py` |
| `documents/` | Upload, preview, file extraction routing | `routes.py`, `extractors/` |
| `detection/` | 4-layer PHI ensemble, chunking, entity cache | `pipeline.py`, `presidio_setup.py` |
| `redaction/` | Pipeline orchestration, mode filtering, redaction | `pipeline.py`, `mode_configs.py`, `redactors/` |
| `ai/` | Mistral integration + local fallback | `mistral_agent.py` |
| `qa/` | Re-OCR verification loop | `redaction_verifier.py` |
| `risk/` | Re-identification risk scoring | `reidentification.py` |
| `synthetic/` | Faker-based PHI replacement | `faker_replacement.py` |
| `audit/` | SHA-256 hash chain, verify endpoint | `hash_chain.py`, `routes.py` |
| `review/` | Human review workflow (confirm/flag/approve) | `routes.py` |
| `sharing/` | Password-protected secure share links + SMTP | `routes.py`, `email.py` |
| `intelligence/` | Privacy analytics dashboard | `routes.py` |
| `batch/` | Batch job runner with per-file isolation | `job_runner.py`, `routes.py` |
| `storage/` | Temp directory management + TTL cleanup | `temp_manager.py` |
| `db/` | MongoDB connection + Beanie ODM models | `client.py`, `models.py` |
