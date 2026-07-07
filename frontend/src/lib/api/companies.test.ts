import { afterEach, describe, expect, it, vi } from "vitest";
import { requestUploadAndPut } from "./companies";
import { api } from "./client";

afterEach(() => vi.restoreAllMocks());

function file() {
  return new File(["x"], "logo.png", { type: "image/png" });
}

describe("requestUploadAndPut", () => {
  it("requests a signed URL then PUTs the file and returns the object path", async () => {
    vi.spyOn(api, "POST").mockResolvedValue({
      data: { upload_url: "https://gcs/put", object_path: "media/companies/logos/x/logo.png" },
      error: undefined,
    } as never);
    const put = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true } as Response);

    const path = await requestUploadAndPut(file());

    expect(path).toBe("media/companies/logos/x/logo.png");
    expect(put).toHaveBeenCalledWith(
      "https://gcs/put",
      expect.objectContaining({ method: "PUT", headers: { "Content-Type": "image/png" } }),
    );
  });

  it("throws upload_not_configured on 503", async () => {
    vi.spyOn(api, "POST").mockResolvedValue({
      data: undefined,
      error: { detail: "not configured" },
      response: { status: 503 },
    } as never);
    await expect(requestUploadAndPut(file())).rejects.toThrow("upload_not_configured");
  });

  it("throws upload_failed when the GCS PUT fails", async () => {
    vi.spyOn(api, "POST").mockResolvedValue({
      data: { upload_url: "https://gcs/put", object_path: "p" },
      error: undefined,
    } as never);
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: false, status: 403 } as Response);
    await expect(requestUploadAndPut(file())).rejects.toThrow("upload_failed");
  });
});
