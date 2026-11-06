CREATE OR REPLACE FUNCTION public.library_integrity_audit()
RETURNS TABLE(issue text, affected bigint)
LANGUAGE sql STABLE SET search_path = pg_catalog, pg_temp
AS $$
    WITH RECURSIVE rooted(folder_id) AS (
        SELECT f.folder_id FROM public.document_folders AS f WHERE f.parent_folder_id IS NULL
        UNION
        SELECT f.folder_id FROM public.document_folders AS f JOIN rooted AS r ON f.parent_folder_id = r.folder_id
    )
    SELECT 'invalid_parent_owner'::text, count(*) FROM public.document_folders AS f
        LEFT JOIN public.document_folders AS p ON p.folder_id = f.parent_folder_id
        WHERE f.parent_folder_id IS NOT NULL AND (p.folder_id IS NULL OR p.owner_user_id IS DISTINCT FROM f.owner_user_id)
    UNION ALL
    SELECT 'invalid_item_owner', count(*) FROM public.document_folder_items AS i
        LEFT JOIN public.document_folders AS f ON f.folder_id = i.folder_id
        WHERE f.folder_id IS NULL OR f.owner_user_id IS DISTINCT FROM i.owner_user_id
    UNION ALL
    SELECT 'unrooted_or_cyclic_folders', count(*) FROM public.document_folders AS f
        WHERE NOT EXISTS (SELECT 1 FROM rooted AS r WHERE r.folder_id = f.folder_id)
    UNION ALL
    SELECT 'blank_folder_names', count(*) FROM public.document_folders WHERE name !~ '[^[:space:]]'
    UNION ALL
    SELECT 'duplicate_name_groups', count(*) FROM (
        SELECT 1 FROM public.document_folders GROUP BY owner_user_id, parent_folder_id, name HAVING count(*) > 1
    ) AS duplicates
    UNION ALL
    SELECT 'orphan_item_documents', count(*) FROM public.document_folder_items AS i
        WHERE NOT EXISTS (SELECT 1 FROM public.documents AS d WHERE d.document_id = i.document_id)
    UNION ALL
    SELECT 'orphan_favorite_documents', count(*) FROM public.document_favorites AS f
        WHERE NOT EXISTS (SELECT 1 FROM public.documents AS d WHERE d.document_id = f.document_id)
$$;

REVOKE ALL ON FUNCTION public.library_integrity_audit() FROM PUBLIC;
