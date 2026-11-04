BEGIN;

SET LOCAL ROLE embedding_runtime;

DO $$
DECLARE
    fixture_id text;
BEGIN
    IF has_schema_privilege(current_user, 'public', 'CREATE')
       OR has_table_privilege(current_user, 'public.auth_user', 'SELECT')
       OR has_table_privilege(current_user, 'public.chat_messages', 'SELECT')
       OR has_table_privilege(current_user, 'public.documents', 'DELETE')
       OR has_column_privilege(current_user, 'public.documents', 'owner_user_id', 'UPDATE')
       OR has_column_privilege(current_user, 'public.documents', 'storage_path', 'UPDATE')
       OR has_any_column_privilege(current_user, 'public.document_embeddings', 'UPDATE') THEN
        RAISE EXCEPTION 'embedding_runtime exceeds its permissions';
    END IF;

    INSERT INTO public.documents (filename, storage_path, mime_type)
    VALUES ('fixture.txt', 'fixture.txt', 'text/plain') RETURNING document_id INTO fixture_id;
    PERFORM document_id FROM public.documents WHERE document_id = fixture_id FOR NO KEY UPDATE NOWAIT;
    INSERT INTO public.document_embeddings (document_id, chunk_index, chunk_content, embedding)
    VALUES (fixture_id, 0, 'Synthetic chunk', array_fill(1.0::real, ARRAY[384])::vector);
    UPDATE public.documents SET status = 'PROCESSED' WHERE document_id = fixture_id;
    DELETE FROM public.document_embeddings WHERE document_id = fixture_id;
END
$$;

ROLLBACK;
