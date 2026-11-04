class ManageConversations:
    def __init__(self, repository) -> None:
        self._repository = repository

    def list(self, include_archived=False):
        return self._repository.list(include_archived)

    def create(self, payload):
        return self._repository.create(payload.title, payload.metadata)

    def get(self, conversation_id):
        return self._repository.get(conversation_id)

    def update(self, conversation_id, payload):
        return self._repository.update(conversation_id, payload.title, payload.archived)

    def delete(self, conversation_id):
        return self._repository.delete(conversation_id)

    def list_messages(self, conversation_id, limit, before):
        return self._repository.list_messages(conversation_id, limit, before)

    def add_message(self, conversation_id, payload):
        return self._repository.add_message(conversation_id, payload.role, payload.content, payload.sources, payload.metadata)

    def list_documents(self, conversation_id):
        return self._repository.list_documents(conversation_id)

    def add_document(self, conversation_id, document_id):
        return self._repository.add_document(conversation_id, document_id)

    def remove_document(self, conversation_id, document_id):
        return self._repository.remove_document(conversation_id, document_id)
