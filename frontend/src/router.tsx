import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
  Outlet,
  Link,
} from "@tanstack/react-router";

import { isAuthenticated } from "@/lib/auth";
import { HomePage } from "@/routes/home";
import { AboutPage } from "@/routes/about";
import { LoginPage } from "@/routes/login";
import { AppShell } from "@/components/app-shell";
import { DashboardPage } from "@/routes/dashboard";
import { CompaniesListPage } from "@/routes/companies-list";
import { CompanyDetailPage } from "@/routes/company-detail";
import { CreateCompanyPage } from "@/routes/create-company";
import { EditCompanyPage } from "@/routes/edit-company";
import { CreatePage } from "@/routes/create";
import { MaterialsPage } from "@/routes/materials";
import { TemplatesPage } from "@/routes/templates";

/** Bare root — each group provides its own chrome (or none). */
const rootRoute = createRootRoute({ component: () => <Outlet /> });

/** Existing marketing shell (top nav) — unchanged public pages. */
const marketingRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "marketing",
  component: function MarketingLayout() {
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
  getParentRoute: () => marketingRoute,
  path: "/",
  component: HomePage,
});

const aboutRoute = createRoute({
  getParentRoute: () => marketingRoute,
  path: "/about",
  component: AboutPage,
});

/** Standalone login. Logged-in users skip straight to the dashboard. */
const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  beforeLoad: () => {
    if (isAuthenticated()) throw redirect({ to: "/dashboard" });
  },
  component: LoginPage,
});

/** Guarded app shell (sidebar). Anonymous users are sent to login. */
const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app",
  beforeLoad: () => {
    if (!isAuthenticated()) throw redirect({ to: "/login" });
  },
  component: AppShell,
});

const dashboardRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/dashboard",
  component: DashboardPage,
});
const companiesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/companies",
  component: CompaniesListPage,
});
const companyDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/companies/$companyId",
  component: CompanyDetailPage,
});
const createCompanyRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/companies/new",
  component: CreateCompanyPage,
});
const companyEditRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/companies/$companyId/edit",
  component: EditCompanyPage,
});
const createMaterialRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/create",
  component: CreatePage,
});
const materialsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/materials",
  component: MaterialsPage,
});
const templatesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/templates",
  component: TemplatesPage,
});

const routeTree = rootRoute.addChildren([
  marketingRoute.addChildren([indexRoute, aboutRoute]),
  loginRoute,
  appRoute.addChildren([
    dashboardRoute,
    companiesRoute,
    createCompanyRoute,
    companyDetailRoute,
    companyEditRoute,
    createMaterialRoute,
    materialsRoute,
    templatesRoute,
  ]),
]);

export const router = createRouter({ routeTree });

// Register the router instance for full type-safety across the app.
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
