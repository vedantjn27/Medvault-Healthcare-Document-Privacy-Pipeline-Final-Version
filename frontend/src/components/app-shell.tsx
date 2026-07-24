import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "@/lib/auth/auth-context";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { ActivePrivacyModeSelector } from "@/components/active-privacy-mode-selector";
import { CapsuleLoader } from "@/components/capsule-loader";
import {
  LayoutDashboard,
  Upload,
  GitCompareArrows,
  Layers,
  ShieldAlert,
  Bell,
  LogOut,
  Mail,
  Menu,
  X,
  FileText,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Info,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

type NavItem = { to: string; label: string; icon: typeof LayoutDashboard; exact?: boolean };
const NAV: NavItem[] = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { to: "/app/upload", label: "Upload & Redact", icon: Upload },
  { to: "/app/compare", label: "Mode Comparison", icon: GitCompareArrows },
  { to: "/app/batch", label: "Batch Processing", icon: Layers },
  { to: "/app/audit", label: "Audit Trail", icon: ShieldAlert },
  { to: "/app/settings", label: "Notifications", icon: Bell },
  { to: "/app/contact", label: "Contact & Help", icon: Mail },
  { to: "/app/about", label: "About MedVault", icon: Info },
];

export function AppShell({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const nav = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (auth.status === "unauthenticated") {
      nav({ to: "/auth/login", search: { redirect: pathname } as never, replace: true });
    }
  }, [auth.status, nav, pathname]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  if (auth.status !== "authenticated") {
    return (
      <div className="grid min-h-screen place-items-center bg-background">
        <div className="flex items-center gap-3 text-muted-foreground">
          <CapsuleLoader compact label="" />
          Restoring your session…
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex flex-col border-r bg-sidebar transition-[width,transform] duration-300 lg:static lg:translate-x-0",
          collapsed ? "w-[4.75rem]" : "w-72",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b px-4">
          {collapsed ? (
            <div className="grid h-9 w-9 place-items-center rounded-xl gradient-hero text-white">
              <ShieldCheck className="h-5 w-5" />
            </div>
          ) : <Logo />}
          <Button
            variant="ghost"
            size="icon"
            className="hidden lg:inline-flex"
            onClick={() => setCollapsed((value) => !value)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setMobileOpen(false)}
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {NAV.map(({ to, label, icon: Icon, exact }) => {
            const active = exact ? pathname === to : pathname.startsWith(to);
            return (
              <Link
                key={to}
                to={to as "/app"}
                className={cn(
                  "flex items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  collapsed ? "justify-center" : "gap-3",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm"
                    : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {collapsed ? <span className="sr-only">{label}</span> : <span className="truncate">{label}</span>}
              </Link>
            );
          })}
        </nav>
        <div className="border-t p-3">
          <div className={cn("flex items-center rounded-lg bg-muted/50 p-3", collapsed ? "justify-center" : "gap-3")}>
            <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full gradient-hero text-sm font-bold text-white">
              {auth.user?.email.charAt(0).toUpperCase()}
            </div>
            {collapsed ? null : <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium">{auth.user?.email}</p>
              <p className="text-[10px] text-muted-foreground">Session-only</p>
            </div>}
            <Button variant="ghost" size="icon" onClick={auth.logout} aria-label="Log out" title="Log out">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>

      {/* Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Main */}
      <div className="flex flex-1 min-w-0 flex-col">
        <header className="sticky top-0 z-20 flex min-h-16 items-center justify-between gap-2 border-b bg-background/80 px-4 py-2 backdrop-blur-md lg:px-8">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </Button>
            <Link to="/" className="text-xs text-muted-foreground hover:text-foreground">
              ← Home
            </Link>
          </div>
          <div className="flex items-center gap-2">
            <ActivePrivacyModeSelector />
            <Link to="/app/upload">
              <Button size="sm" className="gap-2">
                <FileText className="h-4 w-4" />
                <span className="hidden sm:inline">New document</span>
              </Button>
            </Link>
            <ThemeToggle />
          </div>
        </header>
        <main className="app-surface flex-1 p-4 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
