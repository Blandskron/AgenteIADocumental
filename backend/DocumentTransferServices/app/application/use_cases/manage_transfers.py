class ManageTransfers:
    def __init__(self, repository) -> None:
        self._repository = repository

    def list(self, limit):
        return self._repository.list(limit)

    def create(self, payload):
        return self._repository.create(payload.model_dump(exclude_none=True))

    def update(self, transfer_id, payload):
        return self._repository.update(transfer_id, payload.model_dump(exclude_none=True))

    def clear_history(self):
        return self._repository.clear_history()
