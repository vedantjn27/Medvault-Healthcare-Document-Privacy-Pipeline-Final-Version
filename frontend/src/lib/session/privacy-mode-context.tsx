/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ENTITY_TYPES, type CustomRules, type PrivacyMode } from "@/lib/api/types";

const STORAGE_KEY = "medvault.activePrivacyMode";
const CUSTOM_RULES_STORAGE_KEY = "medvault.customPrivacyRules";
const DEFAULT_MODE: PrivacyMode = "research_sharing";
const VALID_MODES = new Set<PrivacyMode>([
  "patient_portal",
  "research_sharing",
  "insurance_processing",
  "legal_discovery",
  "custom",
]);
const VALID_ENTITY_TYPES = new Set<string>(ENTITY_TYPES);

export const DEFAULT_CUSTOM_RULES: CustomRules = {
  entity_types_to_redact: [
    "PERSON",
    "PATIENT_NAME",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "US_SSN",
    "MRN",
  ],
  entity_types_to_preserve: ["DATE_TIME"],
  confidence_threshold: 0.7,
  synthetic_replacement: true,
};

type PrivacyModeContextValue = {
  mode: PrivacyMode;
  setMode: (mode: PrivacyMode) => void;
  customRules: CustomRules;
  setCustomRules: (rules: CustomRules) => void;
};

const PrivacyModeContext = createContext<PrivacyModeContextValue | null>(null);

export function PrivacyModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<PrivacyMode>(DEFAULT_MODE);
  const [customRules, setCustomRules] = useState<CustomRules>(DEFAULT_CUSTOM_RULES);

  useEffect(() => {
    const saved = window.sessionStorage.getItem(STORAGE_KEY) as PrivacyMode | null;
    if (saved && VALID_MODES.has(saved)) setMode(saved);
    const savedRules = window.sessionStorage.getItem(CUSTOM_RULES_STORAGE_KEY);
    if (savedRules) {
      try {
        const parsed = JSON.parse(savedRules) as unknown;
        if (isValidCustomRules(parsed)) setCustomRules(parsed);
      } catch {
        window.sessionStorage.removeItem(CUSTOM_RULES_STORAGE_KEY);
      }
    }
  }, []);

  useEffect(() => {
    window.sessionStorage.setItem(STORAGE_KEY, mode);
  }, [mode]);

  useEffect(() => {
    window.sessionStorage.setItem(CUSTOM_RULES_STORAGE_KEY, JSON.stringify(customRules));
  }, [customRules]);

  const value = useMemo(
    () => ({ mode, setMode, customRules, setCustomRules }),
    [mode, customRules],
  );
  return <PrivacyModeContext.Provider value={value}>{children}</PrivacyModeContext.Provider>;
}

export function usePrivacyMode(): PrivacyModeContextValue {
  const context = useContext(PrivacyModeContext);
  if (!context) throw new Error("usePrivacyMode must be used inside PrivacyModeProvider");
  return context;
}

function isValidCustomRules(value: unknown): value is CustomRules {
  if (!value || typeof value !== "object") return false;
  const rules = value as Partial<CustomRules>;
  if (
    !Array.isArray(rules.entity_types_to_redact) ||
    !Array.isArray(rules.entity_types_to_preserve) ||
    rules.entity_types_to_redact.length < 1 ||
    typeof rules.confidence_threshold !== "number" ||
    rules.confidence_threshold < 0.4 ||
    rules.confidence_threshold > 1 ||
    typeof rules.synthetic_replacement !== "boolean"
  ) {
    return false;
  }
  const redact = new Set(rules.entity_types_to_redact);
  const preserve = new Set(rules.entity_types_to_preserve);
  return (
    [...redact, ...preserve].every((entity) => VALID_ENTITY_TYPES.has(entity)) &&
    [...redact].every((entity) => !preserve.has(entity))
  );
}
