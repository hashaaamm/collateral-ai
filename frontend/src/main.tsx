import "@fontsource/hanken-grotesk/400.css";
import "@fontsource/hanken-grotesk/500.css";
import "@fontsource/hanken-grotesk/600.css";
import "@fontsource/hanken-grotesk/700.css";
import "@fontsource/hanken-grotesk/800.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Providers } from "@/components/providers";
import { App } from "@/App";
import "@/index.css";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error('Missing #root element in index.html');

createRoot(rootEl).render(
  <StrictMode>
    <Providers>
      <App />
    </Providers>
  </StrictMode>,
);
