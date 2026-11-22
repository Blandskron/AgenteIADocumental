from __future__ import annotations

from app.infrastructure.database.checkpointer import InMemoryCheckpointer


def test_checkpoint_metadata_listing_and_retention_pruning() -> None:
    cp = InMemoryCheckpointer()
    for i in range(1, 8):
        cp.save(
            thread_id="thr_keep",
            tenant_id="t1",
            owner_user_id="u1",
            node_name=f"step_{i}",
            state={"step": i},
        )

    meta = cp.list_metadata(thread_id="thr_keep", tenant_id="t1", owner_user_id="u1")
    assert len(meta) == 7
    assert cp.list_metadata(thread_id="thr_keep", tenant_id="t2", owner_user_id="u1") == []

    deleted = cp.prune_old_checkpoints(thread_id="thr_keep", tenant_id="t1", owner_user_id="u1", keep_last=3)
    assert deleted == 4

    remaining = cp.list_metadata(thread_id="thr_keep", tenant_id="t1", owner_user_id="u1")
    assert [m["checkpoint_seq"] for m in remaining] == [5, 6, 7]
    latest = cp.load_latest(thread_id="thr_keep", tenant_id="t1", owner_user_id="u1")
    assert latest is not None
    assert latest.checkpoint_seq == 7
