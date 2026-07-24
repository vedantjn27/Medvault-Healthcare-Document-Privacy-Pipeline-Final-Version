import { createFileRoute, Link } from "@tanstack/react-router";
import { AboutMedVault } from "@/components/about-medvault";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth/auth-context";

export const Route = createFileRoute("/about")({
  component: PublicAboutPage,
  head: () => ({ meta: [{ title: "About MedVault — Healthcare Privacy Pipeline" }] }),
});

function PublicAboutPage() {
  const { status } = useAuth();
  return <div className="min-h-screen bg-background"><header className="sticky top-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-lg"><div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 lg:px-8"><Logo /><div className="flex items-center gap-2"><ThemeToggle /><Link to={status === "authenticated" ? "/app" : "/auth/login"}><Button size="sm" variant="outline">{status === "authenticated" ? "Open app" : "Log in"}</Button></Link><Link to="/"><Button size="sm">Home</Button></Link></div></div></header><AboutMedVault /></div>;
}
