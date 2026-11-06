class ManageLibrary:
    def __init__(self, repository) -> None:
        self._repository = repository

    def list_folders(self, parent_folder_id=None, limit=50, offset=0):
        return self._repository.list_folders(parent_folder_id, limit, offset)

    def create_folder(self, payload):
        return self._repository.create_folder(payload.name, payload.parent_folder_id, payload.metadata)

    def update_folder(self, folder_id, payload):
        return self._repository.update_folder(folder_id, payload.name, payload.metadata)

    def delete_folder(self, folder_id):
        return self._repository.delete_folder(folder_id)

    def list_folder_documents(self, folder_id, limit=50, offset=0):
        return self._repository.list_folder_documents(folder_id, limit, offset)

    def add_document_to_folder(self, folder_id, document_id):
        return self._repository.add_document_to_folder(folder_id, document_id)

    def remove_document_from_folder(self, folder_id, document_id):
        return self._repository.remove_document_from_folder(folder_id, document_id)

    def move_document_to_folder(self, document_id, folder_id):
        return self._repository.move_document_to_folder(document_id, folder_id)

    def list_recent(self, limit=50, offset=0):
        return self._repository.list_recent(limit, offset)

    def list_favorites(self, limit=50, offset=0):
        return self._repository.list_favorites(limit, offset)

    def document_markers(self, document_ids):
        return self._repository.document_markers(document_ids)

    def add_favorite(self, document_id):
        return self._repository.add_favorite(document_id)

    def remove_favorite(self, document_id):
        return self._repository.remove_favorite(document_id)
