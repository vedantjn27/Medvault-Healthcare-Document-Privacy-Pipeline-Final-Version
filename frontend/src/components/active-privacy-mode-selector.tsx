import { useState } from "react";
import { Settings2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import {
  ENTITY_TYPES,
  PRIVACY_MODE_DESCRIPTIONS,
  PRIVACY_MODE_LABELS,
  type PrivacyMode,
} from "@/lib/api/types";
import { usePrivacyMode } from "@/lib/session/privacy-mode-context";

export function ActivePrivacyModeSelector() {
  const { mode, setMode, customRules, setCustomRules } = usePrivacyMode();
  const [customOpen, setCustomOpen] = useState(false);
  const canSave = customRules.entity_types_to_redact.length > 0;

  function chooseMode(value: string) {
    const selected = value as PrivacyMode;
    setMode(selected);
    if (selected === "custom") setCustomOpen(true);
  }

  return (
    <>
      <div className="flex items-center gap-1.5">
        <ShieldCheck className="hidden h-4 w-4 text-primary sm:block" />
        <label className="sr-only" htmlFor="active-privacy-mode">
          Active privacy mode
        </label>
        <Select value={mode} onValueChange={chooseMode}>
          <SelectTrigger
            id="active-privacy-mode"
            className="h-9 w-[150px] sm:w-[205px]"
            aria-label="Active privacy mode"
            title={PRIVACY_MODE_DESCRIPTIONS[mode]}
          >
            <span className="hidden text-xs text-muted-foreground sm:inline">Mode:</span>
            <SelectValue />
          </SelectTrigger>
          <SelectContent align="end">
            {(Object.keys(PRIVACY_MODE_LABELS) as PrivacyMode[]).map((privacyMode) => (
              <SelectItem key={privacyMode} value={privacyMode}>
                {PRIVACY_MODE_LABELS[privacyMode]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {mode === "custom" ? (
          <Button
            variant="outline"
            size="icon"
            className="h-9 w-9"
            onClick={() => setCustomOpen(true)}
            aria-label="Configure custom privacy mode"
            title="Configure custom privacy mode"
          >
            <Settings2 className="h-4 w-4" />
          </Button>
        ) : null}
      </div>

      <Dialog open={customOpen} onOpenChange={setCustomOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Configure custom privacy mode</DialogTitle>
            <DialogDescription>
              Choose exactly what to redact or preserve. These rules apply to your next
              single-document redaction and remain available for this browser session.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Confidence threshold: {customRules.confidence_threshold.toFixed(2)}</Label>
              <Slider
                min={0.4}
                max={1}
                step={0.01}
                value={[customRules.confidence_threshold]}
                onValueChange={([confidence_threshold]) =>
                  setCustomRules({ ...customRules, confidence_threshold })
                }
              />
              <p className="text-xs text-muted-foreground">
                Lower values redact more uncertain detections; higher values require stronger
                confidence.
              </p>
            </div>
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <Label>Synthetic replacement</Label>
                <p className="text-xs text-muted-foreground">
                  Use consistent synthetic values instead of redaction labels.
                </p>
              </div>
              <Switch
                checked={customRules.synthetic_replacement}
                onCheckedChange={(synthetic_replacement) =>
                  setCustomRules({ ...customRules, synthetic_replacement })
                }
              />
            </div>
          </div>

          <div>
            <Label>Entity categories</Label>
            <p className="mb-2 text-xs text-muted-foreground">
              Redacted and preserved categories cannot overlap. At least one category must be
              redacted.
            </p>
            <div className="grid max-h-[42vh] gap-1 overflow-y-auto rounded-lg border p-2 sm:grid-cols-2">
              {ENTITY_TYPES.map((entity) => {
                const redacted = customRules.entity_types_to_redact.includes(entity);
                const preserved = customRules.entity_types_to_preserve.includes(entity);
                return (
                  <div
                    key={entity}
                    className="flex items-center justify-between gap-2 rounded px-2 py-1.5 text-xs hover:bg-muted/50"
                  >
                    <span className="truncate font-mono" title={entity}>
                      {entity}
                    </span>
                    <div className="flex shrink-0 items-center gap-2">
                      <label className="flex items-center gap-1">
                        <Checkbox
                          checked={redacted}
                          onCheckedChange={(checked) =>
                            setCustomRules({
                              ...customRules,
                              entity_types_to_redact: checked
                                ? [...new Set([...customRules.entity_types_to_redact, entity])]
                                : customRules.entity_types_to_redact.filter(
                                    (item) => item !== entity,
                                  ),
                              entity_types_to_preserve: checked
                                ? customRules.entity_types_to_preserve.filter(
                                    (item) => item !== entity,
                                  )
                                : customRules.entity_types_to_preserve,
                            })
                          }
                        />
                        <span className="text-destructive">Redact</span>
                      </label>
                      <label className="flex items-center gap-1">
                        <Checkbox
                          checked={preserved}
                          onCheckedChange={(checked) =>
                            setCustomRules({
                              ...customRules,
                              entity_types_to_preserve: checked
                                ? [...new Set([...customRules.entity_types_to_preserve, entity])]
                                : customRules.entity_types_to_preserve.filter(
                                    (item) => item !== entity,
                                  ),
                              entity_types_to_redact: checked
                                ? customRules.entity_types_to_redact.filter(
                                    (item) => item !== entity,
                                  )
                                : customRules.entity_types_to_redact,
                            })
                          }
                        />
                        <span className="text-success">Keep</span>
                      </label>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {!canSave ? (
            <p className="text-sm text-destructive">Select at least one category to redact.</p>
          ) : null}
          <DialogFooter>
            <Button onClick={() => setCustomOpen(false)} disabled={!canSave}>
              Use these custom rules
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
