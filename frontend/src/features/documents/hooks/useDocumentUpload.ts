import type { ChangeEvent } from "react";
import { useRef, useState } from "react";

export function useDocumentUpload() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function clearSelectedFile() {
    setSelectedFile(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] || null);
  }

  return {
    selectedFile,
    fileInputRef,
    setSelectedFile,
    clearSelectedFile,
    openFilePicker,
    handleFileChange,
  };
}
