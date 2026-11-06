CREATE UNIQUE INDEX IF NOT EXISTS document_folders_owner_root_name_unique
    ON public.document_folders (owner_user_id, name)
    WHERE parent_folder_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS document_folders_owner_child_name_unique
    ON public.document_folders (owner_user_id, parent_folder_id, name)
    WHERE parent_folder_id IS NOT NULL;
