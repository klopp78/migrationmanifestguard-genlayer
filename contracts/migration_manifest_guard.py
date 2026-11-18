# { "Depends": "py-genlayer:kzybg95x1gn21dw72m7hyg0maaap04n4nx55j9yt6fkdqxtz6bz0" }
"""A GenVM v0.4-native migration readiness receipt.

The contract commits the exact migration fields that a release process must
review before moving a deployment to the v0.4 runner. It derives the manifest
and receipt commitments on chain, so a caller cannot substitute a different
runner, source hash, state plan, or payable-entrypoint after assessment.
"""

import genlayer
import hashlib
import json


V04_RUNNER = "py-genlayer:kzybg95x1gn21dw72m7hyg0maaap04n4nx55j9yt6fkdqxtz6bz0"


class MigrationManifestGuard(genlayer.contract.Contract):
    receipt_count: genlayer.u64
    latest_receipt_id: str
    latest_receipt: str

    def __init__(self):
        self.receipt_count = genlayer.u64(0)
        self.latest_receipt_id = ""
        self.latest_receipt = ""

    @genlayer.public.view
    def get_latest_receipt_id(self) -> str:
        return self.latest_receipt_id

    @genlayer.public.view
    def get_latest_receipt(self) -> str:
        return self.latest_receipt

    @genlayer.public.view
    def get_receipt_count(self) -> genlayer.u64:
        return self.receipt_count

    @genlayer.public.write
    def assess_migration(
        self,
        old_contract: str,
        source_commitment: str,
        old_runner: str,
        target_network: str,
        salted_nonce: genlayer.u64,
        payable_method: str,
        state_plan_hash: str,
        migration_steps_json: str,
    ) -> str:
        """Store a canonical v0.4 readiness receipt for the caller's manifest."""
        manifest = _manifest(
            old_contract,
            source_commitment,
            old_runner,
            target_network,
            int(salted_nonce),
            payable_method,
            state_plan_hash,
            migration_steps_json,
        )
        manifest_hash = _sha256(_canonical_json(manifest))
        self.receipt_count = genlayer.u64(int(self.receipt_count) + 1)
        sequence = int(self.receipt_count)
        receipt_id = "mmg_" + _sha256(manifest_hash + ":" + str(sequence))[:20]
        receipt = {
            "schema_version": "migrationmanifestguard.v0.4",
            "receipt_id": receipt_id,
            "sequence": sequence,
            "manifest": manifest,
            "manifest_hash": manifest_hash,
            "checks": {
                "runner_pinned": manifest["next_runner"] == V04_RUNNER,
                "salted_nonce_positive": manifest["salted_nonce"] > 0,
                "named_payable_entrypoint": manifest["payable_method"].startswith("receive_"),
                "source_commitment_valid": _is_digest(manifest["source_commitment"]),
                "state_plan_bound": _is_digest(manifest["state_plan_hash"]),
            },
        }
        receipt["receipt_hash"] = _sha256(_canonical_json(receipt))
        self.latest_receipt_id = receipt_id
        self.latest_receipt = _canonical_json(receipt)
        return receipt_id


def _manifest(old_contract, source_commitment, old_runner, target_network, salted_nonce, payable_method, state_plan_hash, migration_steps_json) -> dict:
    steps = _steps(migration_steps_json)
    if salted_nonce <= 0:
        raise Exception("salted_nonce_must_be_positive")
    return {
        "old_contract": _address(old_contract),
        "source_commitment": _digest(source_commitment, "source_commitment"),
        "old_runner": _runner(old_runner, "old_runner"),
        "next_runner": V04_RUNNER,
        "target_network": _network(target_network),
        "salted_nonce": salted_nonce,
        "payable_method": _identifier(payable_method, "payable_method"),
        "state_plan_hash": _digest(state_plan_hash, "state_plan_hash"),
        "migration_steps": steps,
    }


def _steps(raw: str) -> list:
    try:
        parsed = json.loads(raw)
    except Exception as error:
        raise Exception("invalid_migration_steps_json") from error
    if not isinstance(parsed, list) or not 3 <= len(parsed) <= 12:
        raise Exception("use_three_to_twelve_migration_steps")
    normalized, seen = [], set()
    for item in parsed:
        step = _text(item, "migration_step", 8, 280)
        if step.lower() in seen:
            raise Exception("duplicate_migration_step")
        seen.add(step.lower())
        normalized.append(step)
    return normalized


def _address(value) -> str:
    text = str(value).strip().lower()
    if len(text) != 42 or not text.startswith("0x") or any(char not in "0123456789abcdef" for char in text[2:]):
        raise Exception("invalid_old_contract_address")
    return text


def _digest(value, field) -> str:
    text = str(value).strip().lower()
    if not _is_digest(text):
        raise Exception("invalid_" + field)
    return text


def _runner(value, field) -> str:
    text = _text(value, field, 18, 180)
    if not text.startswith("py-genlayer:"):
        raise Exception("invalid_" + field)
    return text


def _network(value) -> str:
    text = _text(value, "target_network", 5, 60).lower()
    if text not in ("studio-next", "studio", "bradbury-phase-2"):
        raise Exception("unsupported_target_network")
    return text


def _identifier(value, field) -> str:
    text = _text(value, field, 8, 80)
    if not text[0].isalpha() or any(not (char.isalnum() or char == "_") for char in text):
        raise Exception("invalid_" + field)
    return text


def _text(value, field, minimum, maximum) -> str:
    text = str(value).strip()
    if text != str(value) or not minimum <= len(text) <= maximum:
        raise Exception("invalid_" + field)
    return text


def _is_digest(value) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
