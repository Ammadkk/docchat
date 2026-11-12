import { useDropzone } from "react-dropzone";
import { Loader2, Upload } from "lucide-react";
import { cn } from "../lib/utils";

interface Props {
  onFiles: (files: File[]) => void;
  uploading: boolean;
}

export function UploadDropzone({ onFiles, uploading }: Props) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { "application/pdf": [".pdf"] },
    multiple: true,
    disabled: uploading,
    onDrop: (accepted) => accepted.length && onFiles(accepted),
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "cursor-pointer rounded-lg border-2 border-dashed px-3 py-4 text-center text-sm transition-colors",
        isDragActive
          ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/40"
          : "border-zinc-300 hover:border-indigo-400 dark:border-zinc-700",
        uploading && "cursor-wait opacity-60",
      )}
    >
      <input {...getInputProps()} />
      {uploading ? (
        <Loader2 className="mx-auto mb-1 size-5 animate-spin text-indigo-500" />
      ) : (
        <Upload className="mx-auto mb-1 size-5 text-zinc-400" />
      )}
      <p className="text-zinc-600 dark:text-zinc-400">
        {uploading ? "Uploading…" : isDragActive ? "Drop PDFs here" : "Drop PDFs or click to upload"}
      </p>
    </div>
  );
}
