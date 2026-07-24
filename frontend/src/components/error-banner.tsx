import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ApiError } from "@/lib/api/client";

export function ErrorBanner({
  error,
  title = "Something went wrong",
}: {
  error: unknown;
  title?: string;
}) {
  const msg =
    error instanceof ApiError
      ? `${error.message} (HTTP ${error.status})`
      : error instanceof Error
        ? error.message
        : String(error);
  return (
    <Alert variant="destructive" role="alert" aria-live="assertive">
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        <p>{msg}</p>
        {error instanceof ApiError && error.fieldErrors.length > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {error.fieldErrors.map((item, index) => (
              <li key={`${item.path}-${index}`}>
                <span className="font-medium">{item.path}:</span> {item.message}
              </li>
            ))}
          </ul>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}
