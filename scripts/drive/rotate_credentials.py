"""Reviewed, offline credential rotation. Never calls Google or prints ciphertext."""
import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy import create_engine, text


def fingerprint(row):
    value = [row["owner_user_id"], row["version"], row["access_token_encrypted"], row["refresh_token_encrypted"]]
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def plan_rotation(connection, cipher):
    rows = connection.execute(text("SELECT owner_user_id,version,access_token_encrypted,refresh_token_encrypted,lease_token "
                                   "FROM google_drive_connections WHERE grant_status <> 'DISCONNECTED' ORDER BY owner_user_id LIMIT 1001")).mappings().all()
    if len(rows) > 1000:
        raise ValueError("Select a reviewed maintenance window with at most 1000 grants.")
    entries = []
    for row in rows:
        outcome = "ready"
        try:
            if row["lease_token"]:
                raise ValueError("busy")
            cipher.decrypt(row["access_token_encrypted"])
            cipher.decrypt(row["refresh_token_encrypted"])
        except Exception:
            outcome = "review_required"
        entries.append({"owner_user_id": row["owner_user_id"], "version": row["version"],
                        "fingerprint": fingerprint(row), "outcome": outcome})
    return {"format": 1, "target_key_id": cipher.key_id, "entries": entries}


def apply_rotation(connection, cipher, plan):
    if plan.get("format") != 1 or plan.get("target_key_id") != cipher.key_id:
        raise ValueError("Rotation configuration differs from the reviewed plan.")
    entries = plan.get("entries")
    if not isinstance(entries, list) or len(entries) > 1000:
        raise ValueError("Invalid rotation plan.")
    changed = 0
    for entry in sorted(entries, key=lambda item: item["owner_user_id"]):
        if entry["outcome"] != "ready":
            continue
        owner = entry["owner_user_id"]
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('blandskron.drive.credentials:'||:u,0))"), {"u": owner})
        row = connection.execute(text("SELECT owner_user_id,version,access_token_encrypted,refresh_token_encrypted,lease_token "
                                      "FROM google_drive_connections WHERE owner_user_id=:u FOR UPDATE"), {"u": owner}).mappings().one()
        if row["lease_token"] or row["version"] != entry["version"] or fingerprint(row) != entry["fingerprint"]:
            raise ValueError("A grant changed after review. Regenerate the complete plan.")
        values = {"u": owner, "access": cipher.encrypt(cipher.decrypt(row["access_token_encrypted"])),
                  "refresh": cipher.encrypt(cipher.decrypt(row["refresh_token_encrypted"]))}
        connection.execute(text("UPDATE google_drive_connections SET access_token_encrypted=:access,refresh_token_encrypted=:refresh,"
                                "version=version+1,updated_at=now() WHERE owner_user_id=:u"), values)
        changed += 1
    return changed


def main():
    from app.config.settings import Settings
    from app.infrastructure.google.token_cipher import TokenCipher
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--plan", type=Path)
    operation.add_argument("--apply", type=Path)
    args = parser.parse_args()
    settings = Settings()
    cipher = TokenCipher.from_settings(settings)
    engine = create_engine(settings.database_url, hide_parameters=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout='5s'"))
            connection.execute(text("SET LOCAL statement_timeout='30s'"))
            if args.plan:
                plan = plan_rotation(connection, cipher)
                with args.plan.open("x", encoding="utf-8") as output:
                    json.dump(plan, output, indent=2)
                print("Review the plan before applying; no credentials were modified.")
            else:
                count = apply_rotation(connection, cipher, json.loads(args.apply.read_text(encoding="utf-8")))
                print(f"Rotated {count} reviewed grants; statuses and account ownership preserved.")
    except Exception:
        raise SystemExit("Rotation stopped and SQL changes rolled back. Review configuration and regenerate the plan.") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
