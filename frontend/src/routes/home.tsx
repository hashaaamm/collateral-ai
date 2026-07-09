import { useCurrentUser } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function HomePage() {
  // Example TanStack Query hook hitting the typed API client.
  const { data: user, isLoading, isError } = useCurrentUser();

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Collateral AI</h1>
        <p className="text-muted-foreground">
          React + Vite SPA starter — TanStack Router &amp; Query, an OpenAPI-typed API
          client, and Tailwind + shadcn/ui.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Backend connectivity</CardTitle>
          <CardDescription>
            Live call to the Django API through the typed client (<code>/api/users/me/</code>).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm">
            {isLoading
              ? (
                <span className="inline-flex items-center gap-2">
                  <Spinner size={14} /> Loading current user…
                </span>
              )
              : isError
                ? "Not signed in (the example /api/users/me/ call returned an error — expected until you authenticate)."
                : `Signed in as ${user?.name || "unknown"}.`}
          </p>
          <Button asChild>
            <a href="http://localhost:8000/api/docs/" target="_blank" rel="noreferrer">
              Open API docs
            </a>
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}
