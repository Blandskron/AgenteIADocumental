import type { Metadata } from "@/shared/api/types.ts";
export interface Profile {
  profile_id: string;
  user_id: string;
  version: number;
  email: string | null;
  phone_number: string | null;
  profile_picture_url: string | null;
  additional_info: Metadata;
  groups?: string[];
  roles?: string[];
  permissions?: string[];
  is_staff?: boolean;
  is_superuser?: boolean;
}
export type ProfileUpdate = Pick<
  Profile,
  "email" | "phone_number" | "additional_info"
> & { profile_picture_url?: string | null };
