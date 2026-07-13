import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";

import { UploadsProvider } from "@/components/uploads/uploads-context";
import { UploadTray } from "@/components/uploads/upload-tray";

/** App-wide providers: TanStack Query (data fetching). Wrap the tree once in main.tsx. */
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 60 * 1000, refetchOnWindowFocus: false },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <UploadsProvider>
        {children}
        <UploadTray />
        <Toaster position="bottom-right" richColors closeButton />
      </UploadsProvider>
    </QueryClientProvider>
  );
}
