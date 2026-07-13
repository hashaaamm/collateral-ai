import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentsTab } from "./documents-tab";
import * as documentsApi from "@/lib/api/documents";
import * as uploadsContext from "@/components/uploads/use-uploads";

vi.mock("@/lib/api/documents", () => ({
  useDocuments: vi.fn(),
  useCompleteDocument: vi.fn(),
  useDeleteDocument: vi.fn(),
  uploadDocument: vi.fn(),
  fetchDocumentViewUrl: vi.fn(),
}));

vi.mock("@/components/uploads/use-uploads", () => ({
  useUploads: vi.fn(),
}));

const mocked = vi.mocked(documentsApi);
const mockedUploads = vi.mocked(uploadsContext);
const enqueue = vi.fn();

function pdf(name: string) {
  return new File(["x"], name, { type: "application/pdf" });
}

function selectFiles(files: File[]) {
  const input = screen.getByLabelText("Upload PDF documents") as HTMLInputElement;
  fireEvent.change(input, { target: { files } });
}

function renderTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
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
  mockedUploads.useUploads.mockReturnValue({ items: [], enqueue, dismiss: vi.fn() });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DocumentsTab", () => {
  it("dispatches selected files to enqueue with the companyId", () => {
    renderTab();
    const files = [pdf("a.pdf"), pdf("b.pdf")];
    selectFiles(files);

    expect(enqueue).toHaveBeenCalledTimes(1);
    const [passedFiles, companyId] = enqueue.mock.calls[0];
    expect(Array.from(passedFiles as FileList)).toHaveLength(2);
    expect(companyId).toBe(3);
    // Orchestration lives in the uploads context now, not here.
    expect(mocked.uploadDocument).not.toHaveBeenCalled();
  });

  it("does not render inline upload rows", () => {
    renderTab();
    selectFiles([pdf("a.pdf")]);

    // No inline per-file upload status text is rendered by the tab itself.
    expect(screen.queryByText(/uploading/i)).toBeNull();
    expect(screen.queryByText(/^done$/i)).toBeNull();
  });

  it("renders the empty-state when there are no documents", () => {
    renderTab();
    expect(
      screen.getByText(/No documents yet\. Upload a PDF to get started\./i),
    ).toBeInTheDocument();
  });

  it("renders a documents table row per document", () => {
    mocked.useDocuments.mockReturnValue({
      data: [
        {
          id: 1,
          file_name: "report.pdf",
          status: "processed",
          page_count: 3,
          chunks_count: 10,
          tables_count: 1,
          images_count: 2,
        },
      ],
      isLoading: false,
    } as never);

    renderTab();
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
  });
});
