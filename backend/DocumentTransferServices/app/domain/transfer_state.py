from app.shared.errors import ConflictError, ValidationError


TERMINAL_STATES = ("COMPLETED", "FAILED", "CANCELLED")


def validate_initial_state(payload: dict) -> None:
    if payload.get("status", "PENDING") == "COMPLETED" and payload.get("progress", 0) != 100:
        raise ValidationError("Completed transfers require progress 100.")


def validate_transition(current, changes: dict) -> None:
    status = changes.get("status", current.status)
    progress = changes.get("progress", current.progress)
    if current.status in TERMINAL_STATES and status != current.status:
        raise ConflictError("Transfer state transition is not allowed.")
    if current.status == "RUNNING" and status == "PENDING":
        raise ConflictError("Transfer state transition is not allowed.")
    if progress < current.progress or (current.status in TERMINAL_STATES and progress != current.progress):
        raise ConflictError("Transfer progress cannot change this way.")
    if {"status", "progress"} & changes.keys() and status == "COMPLETED" and progress != 100:
        raise ConflictError("Completed transfers require progress 100.")
