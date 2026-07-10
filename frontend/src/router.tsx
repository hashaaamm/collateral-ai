import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
  Outlet,
} from "@tanstack/react-router";

import { isAuthenticated } from "@/lib/auth";
import { LandingPage } from "@/routes/landing";
import { LoginPage } from "@/routes/login";
import { AppShell } from "@/components/app-shell";
import { DashboardPage } from "@/routes/dashboard";
import { CompaniesListPage } from "@/routes/companies-list";
import { CompanyDetailPage } from "@/routes/company-detail";
import { CreateCompanyPage } from "@/routes/create-company";
import { EditCompanyPage } from "@/routes/edit-company";
import { CreatePage } from "@/routes/create";
import { MaterialsPage } from "@/routes/materials";
import { MaterialDetailPage } from "@/routes/material-detail";
import { TemplatesPage } from "@/routes/templates";
import { TemplateNewPage } from "@/routes/template-new";

/** Bare root — each group provides its own chrome (or none). */
const rootRoute = createRootRoute({ component: () => <Outlet /> });

/** Public marketing landing page — full-bleed, provides its own chrome. */
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: LandingPage,
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
const materialDetailRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/materials/$materialId",
  component: MaterialDetailPage,
});
const templatesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/templates",
  component: TemplatesPage,
});
const templateNewRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/templates/new",
  component: TemplateNewPage,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  appRoute.addChildren([
    dashboardRoute,
    companiesRoute,
    createCompanyRoute,
    companyDetailRoute,
    companyEditRoute,
    createMaterialRoute,
    materialsRoute,
    materialDetailRoute,
    templatesRoute,
    templateNewRoute,
  ]),
]);

export const router = createRouter({ routeTree });

// Register the router instance for full type-safety across the app.
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
