import { useRef, useState } from "react";

export function useDocumentUpload() {
  const [selectedFile, setSelectedFile] = useState(null);
  const fileInputRef = useRef(null);

  function clearSelectedFile() {
    setSelectedFile(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  function handleFileChange(event) {
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
