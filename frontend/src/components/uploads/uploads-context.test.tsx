import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { UploadsProvider } from "./uploads-context";
import { useUploads } from "./use-uploads";
import * as documentsApi from "@/lib/api/documents";

vi.mock("@/lib/api/documents", () => ({
  uploadDocument: vi.fn(),
}));

const mocked = vi.mocked(documentsApi);

type Deferred = {
  promise: Promise<documentsApi.Document>;
  resolve: () => void;
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

/** Harness: exposes an input that enqueues, and renders the items list. */
function Harness({ companyId = 3 }: { companyId?: number }) {
  const { items, enqueue, dismiss } = useUploads();
  return (
    <div>
      <input
        aria-label="pick"
        type="file"
        onChange={(e) => {
          if (e.target.files) enqueue(e.target.files, companyId);
        }}
      />
      <button type="button" onClick={() => dismiss()}>
        dismiss
      </button>
      <ul>
        {items.map((u) => (
          <li key={u.id} data-testid="item">
            <span>{u.name}</span>
            <span data-testid="status">{u.status}</span>
            <span data-testid="progress">{u.progress}</span>
            {u.error ? <span data-testid="error">{u.error}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

let qc: QueryClient;
let invalidateSpy: ReturnType<typeof vi.spyOn>;

function renderHarness(companyId = 3) {
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  invalidateSpy = vi.spyOn(qc, "invalidateQueries");
  return render(
    <QueryClientProvider client={qc}>
      <UploadsProvider>
        <Harness companyId={companyId} />
      </UploadsProvider>
    </QueryClientProvider>,
  );
}

function selectFiles(files: File[]) {
  const input = screen.getByLabelText("pick") as HTMLInputElement;
  fireEvent.change(input, { target: { files } });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe("useUploads / UploadsProvider", () => {
  it("throws when used outside a provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    function Bare() {
      useUploads();
      return null;
    }
    expect(() => render(<Bare />)).toThrow(/UploadsProvider/);
    spy.mockRestore();
  });

  it("enqueues all PDFs concurrently before any resolve", () => {
    const defs = [deferred(), deferred(), deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(({ onProgress }) => {
      const d = defs[call++];
      d.onProgress = onProgress;
      return d.promise;
    });

    renderHarness();
    selectFiles([pdf("a.pdf"), pdf("b.pdf"), pdf("c.pdf")]);

    // All three fired before any resolves — proves concurrency.
    expect(mocked.uploadDocument).toHaveBeenCalledTimes(3);
    expect(screen.getAllByTestId("item")).toHaveLength(3);

    defs.forEach((d) => d.resolve());
  });

  it("routes onProgress to only the matching item", async () => {
    const defs = [deferred(), deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(({ onProgress }) => {
      const d = defs[call++];
      d.onProgress = onProgress;
      return d.promise;
    });

    renderHarness();
    selectFiles([pdf("first.pdf"), pdf("second.pdf")]);

    defs[1].onProgress(42);

    await waitFor(() => {
      const secondRow = screen.getByText("second.pdf").closest("li")!;
      expect(within(secondRow).getByTestId("progress")).toHaveTextContent("42");
    });
    const firstRow = screen.getByText("first.pdf").closest("li")!;
    expect(within(firstRow).getByTestId("progress")).toHaveTextContent("0");

    defs.forEach((d) => d.resolve());
  });

  it("invalidates the documents query per successful file, not once total", async () => {
    const defs = [deferred(), deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(() => defs[call++].promise);

    renderHarness(7);
    selectFiles([pdf("a.pdf"), pdf("b.pdf")]);

    expect(invalidateSpy).not.toHaveBeenCalled();

    defs[0].resolve();
    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["documents", 7] }),
    );
    expect(invalidateSpy).toHaveBeenCalledTimes(1);

    defs[1].resolve();
    await waitFor(() => expect(invalidateSpy).toHaveBeenCalledTimes(2));
  });

  it("maps upload_not_configured errors and never blocks siblings", async () => {
    const defs = [deferred(), deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(() => defs[call++].promise);

    renderHarness();
    selectFiles([pdf("ok.pdf"), pdf("bad.pdf")]);

    defs[0].resolve();
    defs[1].reject(new Error("upload_not_configured"));

    await waitFor(() => {
      const badRow = screen.getByText("bad.pdf").closest("li")!;
      expect(within(badRow).getByTestId("error")).toHaveTextContent(
        "Document upload isn't configured in this environment.",
      );
    });
    const okRow = screen.getByText("ok.pdf").closest("li")!;
    expect(within(okRow).getByTestId("status")).toHaveTextContent("done");
  });

  it("appends to existing items rather than replacing", async () => {
    const defs = [deferred(), deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(() => defs[call++].promise);

    renderHarness();
    selectFiles([pdf("a.pdf")]);
    expect(screen.getAllByTestId("item")).toHaveLength(1);

    selectFiles([pdf("b.pdf")]);
    expect(screen.getAllByTestId("item")).toHaveLength(2);
    expect(screen.getByText("a.pdf")).toBeInTheDocument();
    expect(screen.getByText("b.pdf")).toBeInTheDocument();

    defs.forEach((d) => d.resolve());
  });

  it("rejects a non-PDF as an error item and never uploads it", () => {
    mocked.uploadDocument.mockImplementation(() => deferred().promise);

    renderHarness();
    selectFiles([new File(["x"], "notes.txt", { type: "text/plain" })]);

    const row = screen.getByText("notes.txt").closest("li")!;
    expect(within(row).getByTestId("status")).toHaveTextContent("error");
    expect(within(row).getByTestId("error")).toHaveTextContent(
      "Only PDF files are supported.",
    );
    expect(mocked.uploadDocument).not.toHaveBeenCalled();
  });

  it("auto-dismisses a fully-successful batch after ~5s", async () => {
    vi.useFakeTimers();
    const defs = [deferred(), deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(() => defs[call++].promise);

    renderHarness();
    selectFiles([pdf("a.pdf"), pdf("b.pdf")]);

    defs[0].resolve();
    defs[1].resolve();
    // Let the settled promises flush and both items reach "done" (which is what
    // schedules the auto-dismiss timer).
    await vi.waitFor(() =>
      expect(screen.getAllByTestId("status").map((n) => n.textContent)).toEqual([
        "done",
        "done",
      ]),
    );

    vi.advanceTimersByTime(5000);
    await vi.waitFor(() => expect(screen.queryAllByTestId("item")).toHaveLength(0));
  });

  it("does NOT auto-dismiss a batch containing an error", async () => {
    vi.useFakeTimers();
    const defs = [deferred(), deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(() => defs[call++].promise);

    renderHarness();
    selectFiles([pdf("ok.pdf"), pdf("bad.pdf")]);

    defs[0].resolve();
    defs[1].reject(new Error("boom"));
    await vi.waitFor(() => {
      const badRow = screen.getByText("bad.pdf").closest("li")!;
      expect(within(badRow).getByTestId("status")).toHaveTextContent("error");
    });

    vi.advanceTimersByTime(5000);
    // Still present — errors keep the tray open.
    expect(screen.getAllByTestId("item")).toHaveLength(2);
  });

  it("dismiss() clears items immediately", async () => {
    const defs = [deferred()];
    let call = 0;
    mocked.uploadDocument.mockImplementation(() => defs[call++].promise);

    renderHarness();
    selectFiles([pdf("a.pdf")]);
    expect(screen.getAllByTestId("item")).toHaveLength(1);

    fireEvent.click(screen.getByText("dismiss"));
    expect(screen.queryAllByTestId("item")).toHaveLength(0);

    defs.forEach((d) => d.resolve());
  });
});
