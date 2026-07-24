import { Link } from "@tanstack/react-router";
import { ShieldCheck } from "lucide-react";

export function Logo({ className = "" }: { className?: string }) {
  return (
    <Link to="/" className={`group flex items-center gap-2 ${className}`}>
      <div className="relative grid h-9 w-9 place-items-center rounded-xl gradient-hero shadow-glow">
        <ShieldCheck className="h-5 w-5 text-white" strokeWidth={2.5} />
        <span className="absolute inset-0 rounded-xl ring-1 ring-white/20" />
      </div>
      <div className="flex flex-col leading-tight">
        <span className="font-display text-base font-bold tracking-tight">MedVault</span>
        <span className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
          Privacy Pipeline
        </span>
      </div>
    </Link>
  );
}
