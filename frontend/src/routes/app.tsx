import { createFileRoute, Outlet } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { PrivacyModeProvider } from "@/lib/session/privacy-mode-context";

export const Route = createFileRoute("/app")({
  component: () => (
    <PrivacyModeProvider>
      <AppShell>
        <Outlet />
      </AppShell>
    </PrivacyModeProvider>
  ),
});
