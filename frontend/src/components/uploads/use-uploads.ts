import { createContext, useContext } from "react";

export type UploadStatus = "uploading" | "processing" | "done" | "error";

export type UploadItem = {
  id: string;
  name: string;
  companyId: number;
  status: UploadStatus;
  progress: number;
  error?: string;
};

export type UploadsContextValue = {
  items: UploadItem[];
  enqueue: (files: FileList | File[], companyId: number) => void;
  dismiss: () => void;
};

export const UploadsContext = createContext<UploadsContextValue | null>(null);

export function useUploads() {
  const ctx = useContext(UploadsContext);
  if (ctx === null) {
    throw new Error("useUploads must be used within an UploadsProvider");
  }
  return ctx;
}
