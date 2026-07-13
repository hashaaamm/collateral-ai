import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentsTab } from "./documents-tab";
import * as documentsApi from "@/lib/api/documents";

vi.mock("@/lib/api/documents", () => ({
  useDocuments: vi.fn(),
  useCompleteDocument: vi.fn(),
  useDeleteDocument: vi.fn(),
  uploadDocument: vi.fn(),
  fetchDocumentViewUrl: vi.fn(),
}));

const mocked = vi.mocked(documentsApi);

type Deferred = {
  promise: Promise<documentsApi.Document>;
  resolve: (v?: unknown) => void;
  reject: (e: unknown) => void;
  onProgress: (pct: number) => void;
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

function selectFiles(files: File[]) {
  const input = screen.getByLabelText("Upload PDF documents") as HTMLInputElement;
  fireEvent.change(input, { target: { files } });
}

let qc: QueryClient;

function renderTab() {
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <DocumentsTab companyId={3} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mocked.useDocuments.mockReturnValue({ data: [], isLoading: false } as never);
  mocked.useCompleteDocument.mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
  mocked.useDeleteDocument.mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DocumentsTab uploads", () => {
  it("renders one uploading row per selected PDF and fires all uploads concurrently", async () => {
    const defs = [deferred(), deferred(), deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(({ onProgress }) => {
      const d = defs[call++];
      d.onProgress = onProgress;
      return d.promise;
    });

    renderTab();
    selectFiles([pdf("a.pdf"), pdf("b.pdf"), pdf("c.pdf")]);

    // All three fired before any resolves — proves concurrency, not sequential await.
    expect(mocked.uploadDocument).toHaveBeenCalledTimes(3);

    expect(await screen.findByText("a.pdf")).toBeInTheDocument();
    expect(screen.getByText("b.pdf")).toBeInTheDocument();
    expect(screen.getByText("c.pdf")).toBeInTheDocument();
    expect(screen.getAllByText(/uploading/i)).toHaveLength(3);

    defs.forEach((d) => d.resolve());
  });

  it("routes onProgress to only the matching file's row", async () => {
    const defs = [deferred(), deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(({ onProgress }) => {
      const d = defs[call++];
      d.onProgress = onProgress;
      return d.promise;
    });

    renderTab();
    selectFiles([pdf("first.pdf"), pdf("second.pdf")]);

    await screen.findByText("first.pdf");

    // Advance only the second file's progress.
    defs[1].onProgress(42);

    await waitFor(() => {
      const secondRow = screen.getByText("second.pdf").closest("li")!;
      expect(within(secondRow).getByText(/42%/)).toBeInTheDocument();
    });
    const firstRow = screen.getByText("first.pdf").closest("li")!;
    expect(within(firstRow).queryByText(/42%/)).toBeNull();
    expect(within(firstRow).getByText(/0%/)).toBeInTheDocument();

    defs.forEach((d) => d.resolve());
  });

  it("shows a failed row for a rejected upload while the others reach done", async () => {
    const defs = [deferred(), deferred(), deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(({ onProgress }) => {
      const d = defs[call++];
      d.onProgress = onProgress;
      return d.promise;
    });

    renderTab();
    selectFiles([pdf("ok1.pdf"), pdf("bad.pdf"), pdf("ok2.pdf")]);

    await screen.findByText("bad.pdf");

    defs[0].resolve();
    defs[2].resolve();
    defs[1].reject(new Error("upload_not_configured"));

    await waitFor(() => {
      const badRow = screen.getByText("bad.pdf").closest("li")!;
      expect(
        within(badRow).getByText(/Document upload isn't configured in this environment\./i),
      ).toBeInTheDocument();
    });

    const ok1Row = screen.getByText("ok1.pdf").closest("li")!;
    const ok2Row = screen.getByText("ok2.pdf").closest("li")!;
    expect(within(ok1Row).getByText(/done/i)).toBeInTheDocument();
    expect(within(ok2Row).getByText(/done/i)).toBeInTheDocument();
  });

  it("invalidates the documents query once after all uploads settle", async () => {
    const defs = [deferred(), deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(() => defs[call++].promise);

    renderTab();
    const spy = vi.spyOn(qc, "invalidateQueries");
    selectFiles([pdf("a.pdf"), pdf("b.pdf")]);

    expect(spy).not.toHaveBeenCalled();

    defs[0].resolve();
    defs[1].resolve();

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({ queryKey: ["documents", 3] });
    });
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("rejects a non-PDF file with an inline error and never uploads it", async () => {
    mocked.uploadDocument.mockImplementation(() => deferred().promise);

    renderTab();
    const bad = new File(["x"], "notes.txt", { type: "text/plain" });
    selectFiles([bad]);

    expect(await screen.findByText("notes.txt")).toBeInTheDocument();
    const row = screen.getByText("notes.txt").closest("li")!;
    expect(within(row).getByText(/Only PDF files are supported\./i)).toBeInTheDocument();
    expect(mocked.uploadDocument).not.toHaveBeenCalled();
  });
});
