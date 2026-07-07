import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  Link,
} from "@tanstack/react-router";
import { HomePage } from "@/routes/home";
import { AboutPage } from "@/routes/about";
import { DashboardPage } from "@/routes/dashboard";

/**
 * TanStack Router route tree. The root route renders the shared shell (nav + a
 * single <Outlet/> for the active page); index ("/") and "/about" hang off it.
 * Add routes by declaring another createRoute({ getParentRoute, path, component })
 * and appending it to addChildren below.
 */
const rootRoute = createRootRoute({
  component: function RootLayout() {
    return (
      <div className="min-h-dvh bg-background text-foreground">
        <header className="border-b">
          <nav className="mx-auto flex max-w-3xl items-center gap-4 px-4 py-3 text-sm">
            <Link to="/" className="font-semibold [&.active]:underline">
              {"Collateral AI"}
            </Link>
            <Link to="/about" className="[&.active]:underline">
              About
            </Link>
          </nav>
        </header>
        <main className="mx-auto max-w-3xl px-4 py-8">
          <Outlet />
        </main>
      </div>
    );
  },
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: HomePage,
});

const aboutRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/about",
  component: AboutPage,
});

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/dashboard",
  component: DashboardPage,
});

const routeTree = rootRoute.addChildren([indexRoute, aboutRoute, dashboardRoute]);

export const router = createRouter({ routeTree });

// Register the router instance for full type-safety across the app.
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
