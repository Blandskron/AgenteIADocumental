class ManageTransfers:
    def __init__(self, repository) -> None:
        self._repository = repository

    def list(self, limit, offset=0):
        return self._repository.list(limit, offset)

    def create(self, payload):
        return self._repository.create(_orm_payload(payload.model_dump()))

    def update(self, transfer_id, payload):
        return self._repository.update(transfer_id, _orm_payload(payload.model_dump(exclude_unset=True)))

    def clear_history(self):
        return self._repository.clear_history()


def _orm_payload(payload):
    if "metadata" in payload:
        payload["metadata_"] = payload.pop("metadata")
    return payload
