import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { UploadsProvider } from "./uploads-context";
import { useUploads } from "./use-uploads";
import { UploadTray } from "./upload-tray";
import * as documentsApi from "@/lib/api/documents";

vi.mock("@/lib/api/documents", () => ({
  uploadDocument: vi.fn(),
}));

const mocked = vi.mocked(documentsApi);

type Deferred = {
  promise: Promise<documentsApi.Document>;
  resolve: () => void;
  reject: (e: unknown) => void;
};

function deferred(): Deferred {
  const d = {} as Deferred;
  d.promise = new Promise((res, rej) => {
    d.resolve = () => res({ status: "processing" } as documentsApi.Document);
    d.reject = rej;
  });
  return d;
}

function pdf(name: string) {
  return new File(["x"], name, { type: "application/pdf" });
}

/** Hidden picker so tests can drive enqueue via the real provider. */
function Picker() {
  const { enqueue } = useUploads();
  return (
    <input
      aria-label="pick"
      type="file"
      onChange={(e) => {
        if (e.target.files) enqueue(e.target.files, 3);
      }}
    />
  );
}

let qc: QueryClient;

function renderTray() {
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <UploadsProvider>
        <Picker />
        <UploadTray />
      </UploadsProvider>
    </QueryClientProvider>,
  );
}

function selectFiles(files: File[]) {
  fireEvent.change(screen.getByLabelText("pick"), { target: { files } });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("UploadTray", () => {
  it("renders nothing when there are no items", () => {
    renderTray();
    expect(screen.queryByText(/upload/i)).toBeNull();
  });

  it("renders one row per item and an in-flight summary", () => {
    const defs = [deferred(), deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(() => defs[call++].promise);

    renderTray();
    selectFiles([pdf("a.pdf"), pdf("b.pdf")]);

    expect(screen.getByText("a.pdf")).toBeInTheDocument();
    expect(screen.getByText("b.pdf")).toBeInTheDocument();
    expect(screen.getByText("Uploading 0 of 2")).toBeInTheDocument();

    defs.forEach((d) => d.resolve());
  });

  it("shows a complete summary when all succeed", async () => {
    const defs = [deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(() => defs[call++].promise);

    renderTray();
    selectFiles([pdf("a.pdf")]);
    defs[0].resolve();

    expect(await screen.findByText("Uploads complete")).toBeInTheDocument();
  });

  it("shows a failed summary when an upload errors", async () => {
    const defs = [deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(() => defs[call++].promise);

    renderTray();
    selectFiles([pdf("bad.pdf")]);
    defs[0].reject(new Error("boom"));

    expect(await screen.findByText("1 failed")).toBeInTheDocument();
  });

  it("chevron toggles the list visibility", () => {
    const defs = [deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(() => defs[call++].promise);

    renderTray();
    selectFiles([pdf("a.pdf")]);

    expect(screen.getByText("a.pdf")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Collapse uploads"));
    expect(screen.queryByText("a.pdf")).toBeNull();
    fireEvent.click(screen.getByLabelText("Expand uploads"));
    expect(screen.getByText("a.pdf")).toBeInTheDocument();

    defs.forEach((d) => d.resolve());
  });

  it("close button empties the tray", async () => {
    const defs = [deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(() => defs[call++].promise);

    renderTray();
    selectFiles([pdf("a.pdf")]);
    expect(screen.getByText("a.pdf")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Close uploads"));
    await waitFor(() => expect(screen.queryByText("a.pdf")).toBeNull());

    defs.forEach((d) => d.resolve());
  });
});
