/**
 * PUT a file straight to a signed GCS URL, reporting 0–100 progress.
 * Uses XHR because fetch() cannot report upload progress.
 */
export function putWithProgress(
  url: string,
  file: File,
  onProgress: (pct: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("Content-Type", file.type);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new Error("upload_failed"));
    xhr.onerror = () => reject(new Error("upload_failed"));
    xhr.send(file);
  });
}
