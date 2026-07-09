import { afterEach, describe, expect, it, vi } from "vitest";
import { deleteDocument, fetchDocumentViewUrl, uploadDocument } from "./documents";
import { api } from "./client";
import * as upload from "./upload";

afterEach(() => vi.restoreAllMocks());

function pdf() {
  return new File(["x"], "report.pdf", { type: "application/pdf" });
}

describe("uploadDocument", () => {
  it("creates the doc, PUTs the bytes with progress, then completes it", async () => {
    const post = vi.spyOn(api, "POST");
    post.mockResolvedValueOnce({
      data: { id: 7, upload_url: "https://gcs/put", status: "pending" },
      error: undefined,
    } as never);
    post.mockResolvedValueOnce({
      data: { id: 7, status: "processing" },
      error: undefined,
    } as never);
    const put = vi.spyOn(upload, "putWithProgress").mockResolvedValue();
    const onProgress = vi.fn();

    const doc = await uploadDocument({ companyId: 3, file: pdf(), onProgress });

    expect(post).toHaveBeenNthCalledWith(1, "/api/companies/{company_pk}/documents/", {
      params: { path: { company_pk: 3 } },
      body: { file_name: "report.pdf", content_type: "application/pdf" },
    });
    expect(put).toHaveBeenCalledWith("https://gcs/put", expect.any(File), onProgress);
    expect(post).toHaveBeenNthCalledWith(
      2,
      "/api/companies/{company_pk}/documents/{id}/complete/",
      { params: { path: { company_pk: 3, id: 7 } } },
    );
    expect(doc.status).toBe("processing");
  });

  it("throws upload_not_configured when create returns 503", async () => {
    vi.spyOn(api, "POST").mockResolvedValue({
      data: undefined,
      error: { detail: "no" },
      response: { status: 503 },
    } as never);
    await expect(
      uploadDocument({ companyId: 3, file: pdf(), onProgress: vi.fn() }),
    ).rejects.toThrow("upload_not_configured");
  });
});

describe("deleteDocument", () => {
  it("issues a nested DELETE for the given company + id", async () => {
    const del = vi.spyOn(api, "DELETE").mockResolvedValue({ data: undefined, error: undefined } as never);
    await deleteDocument(3, 7);
    expect(del).toHaveBeenCalledWith("/api/companies/{company_pk}/documents/{id}/", {
      params: { path: { company_pk: 3, id: 7 } },
    });
  });
});

describe("fetchDocumentViewUrl", () => {
  it("GETs the view-url endpoint and returns the url", async () => {
    const get = vi.spyOn(api, "GET").mockResolvedValue({
      data: { url: "https://signed-get" },
      error: undefined,
    } as never);
    const url = await fetchDocumentViewUrl(3, 7);
    expect(get).toHaveBeenCalledWith(
      "/api/companies/{company_pk}/documents/{id}/view-url/",
      { params: { path: { company_pk: 3, id: 7 } } },
    );
    expect(url).toBe("https://signed-get");
  });

  it("throws view_url_failed on error", async () => {
    vi.spyOn(api, "GET").mockResolvedValue({
      data: undefined,
      error: { detail: "no" },
    } as never);
    await expect(fetchDocumentViewUrl(3, 7)).rejects.toThrow("view_url_failed");
  });
});
