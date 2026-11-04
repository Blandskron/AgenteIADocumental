ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_status_check;
ALTER TABLE documents ADD CONSTRAINT documents_status_check
    CHECK (status IN ('PENDING', 'REINDEX_REQUIRED', 'PROCESSING', 'PROCESSED', 'FAILED'));

ALTER TABLE document_embeddings DROP CONSTRAINT IF EXISTS document_embeddings_document_chunk_unique;
ALTER TABLE document_embeddings ADD CONSTRAINT document_embeddings_document_chunk_unique
    UNIQUE (document_id, chunk_index);

ALTER TABLE chat_messages DROP CONSTRAINT IF EXISTS chat_messages_role_check;
ALTER TABLE chat_messages ADD CONSTRAINT chat_messages_role_check
    CHECK (role IN ('user', 'assistant', 'system'));

ALTER TABLE transfer_events DROP CONSTRAINT IF EXISTS transfer_events_direction_check;
ALTER TABLE transfer_events ADD CONSTRAINT transfer_events_direction_check
    CHECK (direction IN ('UPLOAD', 'DOWNLOAD'));

ALTER TABLE transfer_events DROP CONSTRAINT IF EXISTS transfer_events_status_check;
ALTER TABLE transfer_events ADD CONSTRAINT transfer_events_status_check
    CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'));

ALTER TABLE transfer_events DROP CONSTRAINT IF EXISTS transfer_events_progress_check;
ALTER TABLE transfer_events ADD CONSTRAINT transfer_events_progress_check
    CHECK (progress >= 0 AND progress <= 100);

ALTER TABLE conversation_messages DROP CONSTRAINT IF EXISTS conversation_messages_role_check;
ALTER TABLE conversation_messages ADD CONSTRAINT conversation_messages_role_check
    CHECK (role IN ('user', 'assistant', 'system'));
