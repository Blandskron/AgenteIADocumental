import type { Metadata } from "@/shared/api/types.ts";
import type {
  importGoogleDriveFiles,
  listGoogleDriveImportFiles,
} from "./api/google-drive-import.api.ts";
export interface DriveFile {
  fileId: string;
  id?: string;
  name?: string;
  mimeType?: string;
  exportMimeType?: string;
}
export interface DriveInput {
  files: DriveFile[];
  folderId?: string | null;
  metadata?: Metadata;
}
export interface ImportAttempt {
  signature: string;
  operationId: string;
  connectionVersion?: number;
  finished: boolean;
  outcome?: string;
}
export interface DriveConnection {
  connected: boolean;
  enabled?: boolean;
  version?: number;
  grantStatus?: string;
  busy?: boolean;
  providerAccountId?: string;
  oauthClientId?: string;
  pickerAppId?: string;
  providerAccountEmail?: string;
  scopes?: string[];
  expiresAt?: string;
}
export interface DriveState {
  busy: boolean;
  error: string;
  success: string;
}
export type DriveImport = Awaited<ReturnType<typeof importGoogleDriveFiles>>;
export type DriveImportFile = Awaited<
  ReturnType<typeof listGoogleDriveImportFiles>
>["items"][number];
