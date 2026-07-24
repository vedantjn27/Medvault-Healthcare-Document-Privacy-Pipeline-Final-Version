import { createFileRoute } from "@tanstack/react-router";
import { AboutMedVault } from "@/components/about-medvault";

export const Route = createFileRoute("/app/about")({
  component: () => <AboutMedVault inApp />,
  head: () => ({ meta: [{ title: "About MedVault" }] }),
});
