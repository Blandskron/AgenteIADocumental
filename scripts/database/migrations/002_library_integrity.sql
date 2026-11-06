-- Run inside a transaction, either run_all.sql or psql --single-transaction.
\ir ../functions/002_library_integrity_audit.sql

LOCK TABLE public.document_folders, public.document_folder_items, public.document_favorites IN SHARE ROW EXCLUSIVE MODE;

DO $$
DECLARE
    problems text;
BEGIN
    SELECT string_agg(issue || '=' || affected::text, ', ' ORDER BY issue) INTO problems
    FROM public.library_integrity_audit() WHERE affected > 0;
    IF problems IS NOT NULL THEN
        RAISE EXCEPTION 'Library integrity preflight failed: %', problems
            USING ERRCODE = '23514', HINT = 'Review library_integrity_audit() and repair explicitly; no data was removed.';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'public.document_folders'::regclass AND conname = 'document_folders_id_owner_key') THEN
        ALTER TABLE public.document_folders ADD CONSTRAINT document_folders_id_owner_key UNIQUE (folder_id, owner_user_id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'public.document_folders'::regclass AND conname = 'document_folders_parent_owner_fkey') THEN
        ALTER TABLE public.document_folders ADD CONSTRAINT document_folders_parent_owner_fkey
            FOREIGN KEY (parent_folder_id, owner_user_id) REFERENCES public.document_folders (folder_id, owner_user_id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'public.document_folder_items'::regclass AND conname = 'document_folder_items_folder_owner_fkey') THEN
        ALTER TABLE public.document_folder_items ADD CONSTRAINT document_folder_items_folder_owner_fkey
            FOREIGN KEY (folder_id, owner_user_id) REFERENCES public.document_folders (folder_id, owner_user_id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'public.document_folders'::regclass AND conname = 'document_folders_name_nonblank_check') THEN
        ALTER TABLE public.document_folders ADD CONSTRAINT document_folders_name_nonblank_check CHECK (name ~ '[^[:space:]]');
    END IF;
END
$$;

\ir ../indexes/002_folder_names.sql

ALTER TABLE public.document_folders DROP CONSTRAINT IF EXISTS document_folders_parent_folder_id_fkey;
ALTER TABLE public.document_folder_items DROP CONSTRAINT IF EXISTS document_folder_items_folder_id_fkey;

CREATE OR REPLACE FUNCTION public.guard_document_folder_structure()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.folder_id IS DISTINCT FROM OLD.folder_id OR NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id
           OR NEW.parent_folder_id IS DISTINCT FROM OLD.parent_folder_id THEN
            RAISE EXCEPTION 'Folder identity and parent are immutable.'
                USING ERRCODE = '23514', CONSTRAINT = 'document_folders_structure_immutable';
        END IF;
    ELSIF NEW.parent_folder_id IS NOT NULL THEN
        -- Parent-first insertion and immutable edges prevent cycles, including multi-row INSERTs.
        PERFORM 1 FROM public.document_folders AS p
            WHERE p.folder_id = NEW.parent_folder_id AND p.owner_user_id = NEW.owner_user_id FOR KEY SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'An existing parent owned by the same user is required.'
                USING ERRCODE = '23503', CONSTRAINT = 'document_folders_parent_owner_fkey';
        END IF;
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS document_folders_guard_structure ON public.document_folders;
CREATE TRIGGER document_folders_guard_structure BEFORE INSERT OR UPDATE ON public.document_folders
    FOR EACH ROW EXECUTE FUNCTION public.guard_document_folder_structure();
