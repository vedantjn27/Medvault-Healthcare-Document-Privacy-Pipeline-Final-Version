# MedVault Synthetic Sample Corpus

All files under `sample_files/` contain generated demonstration data only. They do not contain real patient information.

## Mode PDFs

- `pdf/patient_portal_mode.pdf`
- `pdf/research_sharing_mode.pdf`
- `pdf/insurance_processing_mode.pdf`
- `pdf/legal_discovery_mode.pdf`
- `pdf/custom_mode_mixed_native_scanned.pdf`

The custom-mode PDF contains both native PDF text and a scanned image page.

## Format samples

- DOCX: two documents, including `mixed_text_and_embedded_image.docx`
- XLSX: two structured workbooks with cells, styles, formulas, and multiple sheets
- JPEG: two OCR images
- PNG: two OCR images
- TIFF: two OCR images
- DICOM: two files containing identifying metadata and burned-in pixel text
- EML: two messages, one with a PDF attachment and one with an inline image attachment
- MBOX: two multi-message archives with mixed PDF/image attachments

`xlsx/capability_probe_embedded_image.xlsx` is an additional diagnostic fixture and is not counted as one of the two standard XLSX samples.

## Validation result

Run these commands from `backend/`:

```powershell
.\.venv\Scripts\python.exe scripts\generate_sample_files.py
.\.venv\Scripts\python.exe scripts\validate_sample_files.py
```

The latest result is stored in `sample_validation_results.json`:

- 22 files classified and processed
- all 22 files passed destructive redaction and residual-PHI QA
- all five privacy-mode PDFs passed
- DOCX mixed native text + embedded-image OCR redaction passed
- PDF mixed native text + scanned-page OCR redaction passed
- EML/MBOX text plus supported image/PDF attachment redaction passed
- DICOM metadata plus burned-in pixel-text redaction passed
- XLSX native cells plus drawing-layer embedded-image OCR redaction passed

The XLSX capability probe verifies that native cell PHI and OCR text inside its drawing-layer image are both destructively redacted. Embedded workbook images use the same OCR, face and barcode analysis as standalone images, and the output image is rescanned during QA.
