import type { FormEvent, MouseEvent, ReactNode } from "react";
import type { DriveConnection, DriveFile, DriveInput } from "./types.ts";
export type ImportEvent = Pick<
  FormEvent<HTMLFormElement> | MouseEvent<HTMLButtonElement>,
  "preventDefault"
>;
export interface DriveImportViewProps {
  history: ReactNode;
  onCancel: () => void;
  connection: DriveConnection;
  fileIds: string;
  isBusy: boolean;
  pickerConfigured: boolean;
  selectedFiles: DriveFile[];
  operationScope: string | null;
  onConnect: () => void;
  onDisconnect: () => void;
  onFileIdsChange: (value: string) => void;
  onImport: (event: ImportEvent, previousInput?: DriveInput | null) => void;
  onOpenPicker: () => void;
}
