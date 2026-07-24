import { cn } from "@/lib/utils";

export function CapsuleLoader({
  label = "Loading",
  compact = false,
  tone = "clinical",
  complete = false,
  className,
}: {
  label?: string;
  compact?: boolean;
  tone?: "clinical" | "red";
  complete?: boolean;
  className?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "capsule-loader",
        compact && "capsule-loader-compact",
        tone === "red" && "capsule-loader-red",
        complete && "capsule-loader-complete",
        className,
      )}
    >
      <span className="capsule-loader-pill" aria-hidden="true">
        <span className="capsule-loader-half capsule-loader-half-left" />
        <span className="capsule-loader-half capsule-loader-half-right" />
        <span className="capsule-loader-core" />
      </span>
      <span className="capsule-loader-label">{label}</span>
    </div>
  );
}
