# MedVault Manual End-to-End Test Guide

This guide validates the frontend and backend together through the normal user workflow. Use only the synthetic files in `backend/sample_files/`; they do not contain real patient data.

## 1. Pre-flight setup

1. Confirm `backend/.env` contains working MongoDB, JWT, Mistral, SMTP, and Tesseract settings.
2. For local secure-share testing, retain `FRONTEND_PUBLIC_URL=http://127.0.0.1:5173` in `backend/.env` and `VITE_API_BASE_URL=http://127.0.0.1:8000` in `frontend/.env`.
3. Use the credentials in `TEST_CREDENTIALS.txt`. If the account has not yet been created, use the Register page once, then log in with the same credentials.
4. Use the synthetic source files described in `backend/SAMPLE_FILES.md`. The five mode-specific PDFs are in `backend/sample_files/pdf/`.

## 2. Start the application

Open two PowerShell windows from the project root.

1. Backend:

   ```powershell
   Set-Location backend
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

   Expected result: Uvicorn reports that it is running on `http://127.0.0.1:8000`. Opening `http://127.0.0.1:8000/health` returns a JSON healthy status.

2. Frontend:

   ```powershell
   Set-Location frontend
   npm.cmd run dev -- --host 127.0.0.1 --port 5173
   ```

   Expected result: the terminal reports `http://127.0.0.1:5173`. Open that address in a browser.

## 3. Home, authentication, and visual checks

1. On the public Home page, test dark/light theme switching, the interactive branding animations, and navigation to the application.
2. Open **Create an account** if the test account does not exist. Register with `admin@gmail.com` and `P@ssw0rd1234`.
3. Sign in with the test credentials.
4. Expected result: the dashboard opens, the selected privacy mode is visible in the top bar, and the session counters begin at zero after a fresh login.
5. Open **Contact** from the sidebar. Test the sidebar collapse/expand arrow, email, phone, and LinkedIn links. Expected result: the sidebar transitions cleanly and all contact values remain inside their cards.

## 4. Privacy mode selection

1. Use the top-bar **Mode** selector.
2. Check each standard mode and its explanation:
   - Patient Portal: preserves patient-facing utility while protecting identifiers.
   - Research Sharing: uses consistent synthetic replacements where appropriate.
   - Insurance Processing: protects sensitive identity and clinical details for claims handling.
   - Legal Discovery: protects privileged/legal context as well as identifiers.
3. Select **Custom**. Configure at least one entity type to redact and, optionally, preservation rules where permitted.
4. Expected result: invalid/conflicting custom rules prevent processing; valid rules are retained and shown when the job starts.

## 5. Core single-document workflow

1. Open **New document** or **Upload**.
2. Upload `backend/sample_files/pdf/patient_portal_mode.pdf`.
3. Expected result: upload progress completes, a document detail page opens, and the original preview shows a safely authenticated preview.
4. Select **Patient Portal** mode and start redaction.
5. Expected result: the capsule loader rotates while the job is queued/processing, then opens/disappears at completion. The job page changes to the completed state.
6. On the completed job page, validate all sections:
   - **Original** and **Redacted output** previews are both present.
   - Click either preview to open the larger readable preview/modal. Check that the original is readable and the sensitive values are destructively redacted in the output.
   - Review metadata, safe entity categories, confidence values, and QA status. Raw PHI must not appear in the report metadata.
   - Inspect the heatmap. Expected result: page-relative redaction locations/intensity are visible without original text.
   - Use **Download copy**. Expected result: the redacted file downloads with the original-compatible file extension, not `.bin`. Download it a second time in the same login session; both downloads must work.
   - Use the report download action. Expected result: a PDF report downloads with summary information and charts.

## 6. Human review queue and controlled sharing

1. On the same completed job, open **Review queue**.
2. Select an individual **Confirm** and one **Flag** to verify the decisions visually change.
3. Click **Confirm all**. Expected result: every remaining pending item becomes confirmed; a previously flagged item remains flagged.
4. Try **Approve output** while an item is flagged. Expected result: approval is blocked with a clear explanation.
5. Change the flagged item to Confirm, then click **Request changes** once.
6. Expected result: a success notice appears, status becomes `changes requested`, an explanatory warning is displayed, and secure sharing remains locked. This action is an auditable review state change; it does not silently alter the already rendered file.
7. Click **Approve output** after every item is confirmed.
8. Expected result: the review becomes approved and the success notice states that secure sharing is available.
9. Open **Secure share**:
   - Create a reviewer link. Expected result: reviewer access is view-only and download is disabled.
   - Create a recipient link with your email, a password of at least ten characters, a short expiry, and optionally a download cap.
   - Expected result: the link is copied, an SMTP email is delivered, and the active-link list shows role, expiry, access count, and revoke control.
10. Open the recipient email link on the same computer during local testing. Enter the share password if set.
11. Expected result: the public page exposes only redacted-file metadata. Recipient links can download the redacted file; reviewer links cannot. Use **Revoke**, reload the link, and confirm it is unavailable.

## 7. Intelligence and audit verification

1. On the job page, open **Intelligence**.
2. Expected result: coverage, finding count, redacted count, risk level, category profile, and recommendations appear. No raw document value or PHI is displayed.
3. Return to the dashboard.
4. Expected result: the Privacy intelligence card updates from the active session's completed jobs: completed count, QA pass rate, review-approval rate, and average redactions.
5. Open **Audit trail** and select the document.
6. Expected result: upload, redaction, review, sharing, and download events appear as safe audit entries. Run verification; the hash chain should report valid.

## 8. Feedback and re-processing behavior

1. In the job/report findings, submit a correct detection and a false-positive feedback item where available.
2. Submit a missed-entity report using only a category and page/location information; do not enter real PHI.
3. Expected result: feedback is accepted, recorded safely, and no raw missed value is stored or displayed.
4. To change actual redaction output after a requested review change, start a new job from the document page with the desired privacy mode/custom rules. Expected result: a separate auditable job is created and processed.

## 9. Mode comparison

1. Open **Compare modes**.
2. Upload `backend/sample_files/pdf/research_sharing_mode.pdf`, choose two to five standard modes, then run comparison.
3. Expected result: each selected mode runs as needed. The comparison view shows mode-specific safe category/count differences and direct side-by-side previews of the original plus selected outputs.
4. Download an output from the comparison workflow. Expected result: the file extension matches its original format.

## 10. Batch processing

1. Open **Batch redact**.
2. Choose a single privacy mode and upload several synthetic files from different format folders.
3. Expected result: the batch page reports each file independently. One unsupported/broken input must not stop the other files.
4. When complete, inspect each job and download the combined ZIP/report export if offered.
5. Expected result: successful outputs are included; failed items are explicitly identified and isolated.

## 11. File-format coverage

Run the core workflow with representative files below. For each one, check the preview/report where supported, verify destructive redaction, and verify the download extension.

| Format | Suggested synthetic files | Expected result |
| --- | --- | --- |
| PDF | all five files in `sample_files/pdf/` | native text and scanned/OCR text are redacted; each privacy mode behaves differently. |
| DOCX | `sample_files/docx/mixed_text_and_embedded_image.docx` | body, table/header, and embedded-image OCR content are redacted. |
| XLSX | either standard XLSX sample and the capability probe | cells/formulas/styles remain usable; native cell and embedded-image OCR data are redacted. |
| JPEG/PNG/TIFF | files in corresponding image folders | OCR text, detected faces, and barcodes are blacked out while preserving a valid image. |
| DICOM | files in `sample_files/dicom/` | identifying metadata/private tags and burned-in pixel text are removed while a valid DICOM remains. |
| EML/MBOX | files in `sample_files/eml/` and `sample_files/mbox/` | headers, body content, and supported nested PDF/image attachments are redacted. |

## 12. Notifications, logout, and expiry

1. Open **Settings** and enable browser notifications.
2. Expected result: browser permission/subscription state is accurately shown. Disable and re-enable to verify the state changes correctly. Job completion still remains visible through normal in-app polling if push is unavailable.
3. Log out.
4. Expected result: session activity, dashboard counters, session intelligence, downloaded-state indicators, and authenticated pages clear. A protected page should redirect to login.
5. For expiry behavior, set a short secure-share expiry, wait until it passes, then reload the public link. Expected result: it is unavailable. Temporary document files also become unavailable after the configured backend TTL.

## Pass criteria

The project passes manual verification when every tested synthetic input either produces a QA-passed redacted artifact in its original-compatible format or clearly reports an isolated, safe failure; previews, reports, review controls, audit verification, intelligence, sharing, notifications, logout, and expiry behave as described above.
