import { RouterProvider } from "@tanstack/react-router";
import { router } from "@/router";

/**
 * Root application component: hands the typed router tree to TanStack Router.
 * Providers (Query) wrap <App/> in main.tsx.
 */
export function App() {
  return <RouterProvider router={router} />;
}
