// MedVault API contracts — mirror backend snake_case exactly.

export type FileType = "pdf" | "docx" | "xlsx" | "jpeg" | "png" | "tiff" | "dicom" | "eml" | "mbox";

export type DocumentStatus = "uploaded" | "processing" | "expired" | "done";
export type JobStatus = "queued" | "processing" | "qa_failed" | "complete" | "error";
export type ReidentificationRisk = "low" | "medium" | "high";

export type PrivacyMode =
  "patient_portal" | "research_sharing" | "insurance_processing" | "legal_discovery" | "custom";

export type Verbosity = "standard" | "entity_type";

export type User = {
  id: string;
  email: string;
  is_active: boolean;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
};

export type DocumentResponse = {
  id: string;
  original_filename: string;
  file_type: FileType;
  size_bytes: number | null;
  uploaded_at: string;
  status: DocumentStatus;
  expires_at: string;
};

export type PreviewResponse = {
  file_type: FileType;
  truncated: boolean;
  pages: Array<Record<string, unknown>>;
  text: string | null;
  sheets: Array<Record<string, unknown>>;
  messages: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
};

export type CustomRules = {
  entity_types_to_redact: string[];
  entity_types_to_preserve: string[];
  confidence_threshold: number;
  synthetic_replacement: boolean;
};

export type RedactionRunRequest = {
  document_id: string;
  privacy_mode: PrivacyMode;
  custom_rules?: CustomRules | null;
  verbosity: Verbosity;
  subject_patient_id?: string | null;
};

export type JobResponse = {
  job_id: string;
  document_id: string;
  privacy_mode: PrivacyMode;
  status: JobStatus;
  qa_passed: boolean;
  reidentification_risk: ReidentificationRisk | null;
  reidentification_factors: string[];
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
};

export type BoundingBox = { x0: number; y0: number; x1: number; y1: number };

export type EntityReport = {
  id: string;
  entity_type: string;
  page_number: number | null;
  bbox: BoundingBox | null;
  confidence: number;
  detector_source: string[];
  explanation_text: string;
  was_redacted: boolean;
  privileged_flag: boolean;
};

export type RedactionReport = {
  job: JobResponse;
  entity_count: number;
  redacted_count: number;
  reviewed_not_redacted_count: number;
  entities: EntityReport[];
};

export type ExistingEntityFeedback = {
  job_id: string;
  entity_id: string;
  verdict: "correct" | "false_positive";
  note?: string | null;
};

export type MissedFeedback = {
  job_id: string;
  entity_id?: null;
  verdict: "missed";
  entity_type: string;
  page_number: number;
  bbox?: BoundingBox | null;
  note?: string | null;
};

export type ModeComparisonRequest = {
  document_id: string;
  modes: Array<Exclude<PrivacyMode, "custom">>;
};

export type ModeComparisonResponse = {
  document_id: string;
  baseline_mode: string;
  modes: Record<
    string,
    {
      job_id: string;
      redacted_count: number;
      entity_type_counts: Record<string, number>;
    }
  >;
  redacted_count_difference_from_baseline: Record<string, number>;
};

export type BatchItem = {
  document_id: string;
  redaction_job_id: string | null;
  status: JobStatus;
  error_message: string | null;
};

export type BatchResponse = {
  batch_job_id: string;
  status: JobStatus;
  items: BatchItem[];
};

export type AuditEntry = {
  id: string;
  job_id: string | null;
  event_type: string;
  event_data: Record<string, unknown>;
  entry_hash: string;
  previous_hash: string | null;
  sequence: number;
  created_at: string;
};

export type AuditVerification = {
  valid: boolean;
  entries_checked: number;
  broken_entry_id: string | null;
};

export type PushSubscriptionRequest = {
  endpoint: string;
  keys: { p256dh: string; auth: string };
};

export type ReviewDecision = "pending" | "confirmed" | "flagged";
export type ReviewStatus = "pending" | "approved" | "changes_requested";
export type ShareRole = "reviewer" | "recipient";

export type ReviewEntity = EntityReport & {
  review_decision: ReviewDecision;
  review_note: string | null;
};

export type ReviewQueue = {
  job_id: string;
  document_id: string;
  status: ReviewStatus;
  review_note: string | null;
  reviewed_at: string | null;
  entities: ReviewEntity[];
  pending_count: number;
  flagged_count: number;
};

export type ShareLink = {
  id: string;
  job_id: string;
  role: ShareRole;
  recipient_email: string | null;
  allow_download: boolean;
  max_accesses: number | null;
  access_count: number;
  revoked_at: string | null;
  created_at: string;
  expires_at: string;
  share_url: string | null;
};

export type ShareCreateRequest = {
  role: ShareRole;
  expires_in_hours: number;
  password?: string | null;
  recipient_email?: string | null;
  allow_download: boolean;
  max_accesses?: number | null;
};

export type JobInsight = {
  job_id: string;
  status: string;
  document_type: string;
  privacy_mode: string;
  qa_passed: boolean;
  review_status: ReviewStatus;
  risk_level: string;
  risk_factors: string[];
  entity_count: number;
  redacted_count: number;
  coverage_percent: number;
  category_counts: Record<string, number>;
  detector_counts: Record<string, number>;
  recommendations: string[];
};

export type WorkspaceAnalytics = {
  completed_jobs: number;
  qa_pass_rate: number;
  review_approval_rate: number;
  average_redactions: number;
  privacy_mode_counts: Record<string, number>;
  category_counts: Record<string, number>;
  generated_at: string;
};

export type PublicShare = {
  filename: string;
  file_type: string;
  role: ShareRole;
  allow_download: boolean;
  expires_at: string;
  access_count: number;
  max_accesses: number | null;
};

export const ENTITY_TYPES = [
  "PERSON",
  "PATIENT_NAME",
  "EMAIL_ADDRESS",
  "PHONE_NUMBER",
  "US_SSN",
  "US_DRIVER_LICENSE",
  "US_PASSPORT",
  "US_BANK_NUMBER",
  "CREDIT_CARD",
  "CRYPTO",
  "IBAN_CODE",
  "LOCATION",
  "NRP",
  "IP_ADDRESS",
  "MAC_ADDRESS",
  "URL",
  "MRN",
  "NPI",
  "US_NPI",
  "DEA_NUMBER",
  "INSURANCE_ID",
  "POLICY_NUMBER",
  "MEDICAL_LICENSE",
  "US_ITIN",
  "US_MBI",
  "UK_NHS",
  "UK_NINO",
  "UK_PASSPORT",
  "UK_DRIVING_LICENCE",
  "ES_NIF",
  "ES_NIE",
  "ES_PASSPORT",
  "DATE_TIME",
  "MEDICAL_CONDITION",
  "MEDICATION",
  "CLINICAL_ENTITY",
  "PROCEDURE_CODE",
  "DIAGNOSIS_CODE",
  "BILLING_DATE",
  "PAYER_ID",
] as const;

export const PRIVACY_MODE_LABELS: Record<PrivacyMode, string> = {
  patient_portal: "Patient Portal",
  research_sharing: "Research Sharing",
  insurance_processing: "Insurance Processing",
  legal_discovery: "Legal Discovery",
  custom: "Custom",
};

export const PRIVACY_MODE_DESCRIPTIONS: Record<PrivacyMode, string> = {
  patient_portal:
    "Redacts other direct identifiers while preserving dates and the current patient's identifier (optional).",
  research_sharing:
    "Maximum category redaction with consistent synthetic replacements and re-identification risk analysis.",
  insurance_processing:
    "Preserves claim codes, payer fields, NPI and dates required for claims processing.",
  legal_discovery: "Maximum redaction with attorney/privilege context flags.",
  custom:
    "Choose exactly which categories to redact or preserve, plus confidence threshold and synthetic replacement.",
};
