import { useCurrentUser } from "@/lib/api/queries";

export function AboutPage() {
  // Same query is cached and shared across routes by TanStack Query.
  const { data: user } = useCurrentUser();

  return (
    <section className="space-y-4">
      <h1 className="text-3xl font-bold tracking-tight">About</h1>
      <p className="text-muted-foreground">
        Replace this with your story. This page shares the cached current-user
        query with the home route{user?.name ? ` (you are ${user.name})` : ""}.
      </p>
    </section>
  );
}
