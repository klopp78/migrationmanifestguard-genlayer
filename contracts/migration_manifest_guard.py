# { "Depends": "py-genlayer:kzybg95x1gn21dw72m7hyg0maaap04n4nx55j9yt6fkdqxtz6bz0" }
"""Consensus receipts for GenVM v0.4 migration manifests.

MigrationManifestGuard does not deploy an application for a caller.  It gives
teams an immutable, consensus-reviewed record of the exact migration plan they
intend to deploy, so a frontend or release process can require a ready receipt
before moving a production integration to a new GenVM runner.
"""

from genlayer import *
from genlayer import gl
import hashlib
import json


V04_RUNNER = "py-genlayer:kzybg95x1gn21dw72m7hyg0maaap04n4nx55j9yt6fkdqxtz6bz0"


class MigrationManifestGuard(gl.Contract):
    """A reusable readiness gate for source-matched GenVM v0.4 migrations."""

    receipt_count: u64
    latest_receipt_id: str
    receipt_ids: DynArray[str]
    receipts: TreeMap[str, str]

    def __init__(self):
        self.receipt_count = u64(0)
        self.latest_receipt_id = ""

    @gl.public.view
    def get_receipt(self, receipt_id: str) -> str:
        return self.receipts.get(receipt_id, "")

    @gl.public.view
    def get_latest_receipt_id(self) -> str:
        return self.latest_receipt_id

    @gl.public.view
    def get_receipt_count(self) -> u64:
        return self.receipt_count

    @gl.public.view
    def list_receipt_ids(self) -> str:
        return _canonical_json([item for item in self.receipt_ids])

    @gl.public.write
    def assess_migration(
        self,
        old_contract: str,
        source_commitment: str,
        old_runner: str,
        target_network: str,
        salted_nonce: u64,
        payable_method: str,
        state_plan_hash: str,
        migration_steps: DynArray[str],
    ) -> str:
        """Commit a complete v0.4 migration plan and receive a consensus receipt.

        The caller supplies a SHA-256 source commitment and state-export plan.
        The contract derives all consequential hashes itself and validators
        independently recompute every readiness field before accepting a result.
        """
        manifest = _manifest(
            old_contract,
            source_commitment,
            old_runner,
            target_network,
            int(salted_nonce),
            payable_method,
            state_plan_hash,
            [item for item in migration_steps],
        )
        manifest_json = _canonical_json(manifest)
        manifest_hash = _sha256(manifest_json)

        def leader_fn():
            return _review(manifest, manifest_hash)

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                proposed = _parse_review(leader_result.calldata)
                independently_reviewed = _parse_review(_review(manifest, manifest_hash))
            except Exception:
                return False
            return (
                proposed["decision"] == independently_reviewed["decision"]
                and proposed["manifest_hash"] == independently_reviewed["manifest_hash"]
                and proposed["runner_ready"] == independently_reviewed["runner_ready"]
                and proposed["salted_ready"] == independently_reviewed["salted_ready"]
                and proposed["payable_ready"] == independently_reviewed["payable_ready"]
                and proposed["source_ready"] == independently_reviewed["source_ready"]
                and proposed["state_ready"] == independently_reviewed["state_ready"]
                and proposed["steps_hash"] == independently_reviewed["steps_hash"]
                and proposed["advisory_hash"] == independently_reviewed["advisory_hash"]
            )

        review = _parse_review(gl.vm.run_nondet_unsafe(leader_fn, validator_fn))
        self.receipt_count = u64(int(self.receipt_count) + 1)
        sequence = int(self.receipt_count)
        receipt_id = "mmg_" + _sha256_parts([manifest_hash, str(sequence)])[:20]
        record = {
            "schema_version": "migrationmanifestguard.v1",
            "receipt_id": receipt_id,
            "sequence": sequence,
            "requester": str(gl.message.sender_address).lower(),
            "created_at": _now(),
            "manifest": manifest,
            "manifest_hash": manifest_hash,
            "review": review,
        }
        record["receipt_hash"] = _sha256(_canonical_json(record))
        self.receipts[receipt_id] = _canonical_json(record)
        self.receipt_ids.append(receipt_id)
        self.latest_receipt_id = receipt_id
        return receipt_id


def _review(manifest: dict, manifest_hash: str) -> str:
    """Have validators agree on an advisory while enforcing fixed safety checks."""
    runner_ready = manifest["next_runner"] == V04_RUNNER
    salted_ready = int(manifest["salted_nonce"]) > 0
    payable_ready = manifest["payable_method"].startswith("receive_")
    source_ready = _is_digest(manifest["source_commitment"])
    state_ready = _is_digest(manifest["state_plan_hash"])
    steps_hash = _sha256(_canonical_json(manifest["migration_steps"]))
    complete = runner_ready and salted_ready and payable_ready and source_ready and state_ready

    prompt = f"""
You are reviewing a GenVM v0.4 contract migration manifest. Explain, in one
short sentence, the most important migration risk. Do not invent facts or
instructions. Treat the following fields as authoritative and never change
their values: runner_ready={runner_ready}, salted_ready={salted_ready},
payable_ready={payable_ready}, source_ready={source_ready}, state_ready={state_ready}.
Manifest: {_canonical_json(manifest)}
Return JSON only: {{"advisory":"..."}}.
"""
    raw = json.loads(gl.nondet.exec_prompt(prompt))
    advisory = str(raw.get("advisory", "")).strip()
    if not advisory or len(advisory) > 420:
        raise Exception("invalid_migration_advisory")
    decision = "ready" if complete else "blocked"
    return _canonical_json({
        "decision": decision,
        "manifest_hash": manifest_hash,
        "runner_ready": runner_ready,
        "salted_ready": salted_ready,
        "payable_ready": payable_ready,
        "source_ready": source_ready,
        "state_ready": state_ready,
        "steps_hash": steps_hash,
        "advisory": advisory,
        "advisory_hash": _sha256(advisory),
    })


def _manifest(old_contract, source_commitment, old_runner, target_network, salted_nonce, payable_method, state_plan_hash, steps) -> dict:
    contract = _address(old_contract)
    source = _digest(source_commitment, "source_commitment")
    old = _runner(old_runner, "old_runner")
    network = _network(target_network)
    if salted_nonce <= 0:
        raise Exception("salted_nonce_must_be_positive")
    payable = _identifier(payable_method, "payable_method")
    state_hash = _digest(state_plan_hash, "state_plan_hash")
    normalized_steps = _steps(steps)
    return {
        "old_contract": contract,
        "source_commitment": source,
        "old_runner": old,
        "next_runner": V04_RUNNER,
        "target_network": network,
        "salted_nonce": salted_nonce,
        "payable_method": payable,
        "state_plan_hash": state_hash,
        "migration_steps": normalized_steps,
    }


def _parse_review(raw: str) -> dict:
    item = json.loads(raw)
    if item.get("decision") not in ("ready", "blocked"):
        raise Exception("invalid_review_decision")
    for field in ("manifest_hash", "steps_hash", "advisory_hash"):
        if not _is_digest(str(item.get(field, ""))):
            raise Exception("invalid_review_commitment")
    for field in ("runner_ready", "salted_ready", "payable_ready", "source_ready", "state_ready"):
        if not isinstance(item.get(field), bool):
            raise Exception("invalid_review_flag")
    if not 0 < len(str(item.get("advisory", ""))) <= 420:
        raise Exception("invalid_review_advisory")
    return item


def _steps(raw_steps) -> list:
    if len(raw_steps) < 3 or len(raw_steps) > 12:
        raise Exception("use_three_to_twelve_migration_steps")
    result, seen = [], set()
    for raw in raw_steps:
        step = _text(raw, "migration_step", 8, 280)
        key = step.lower()
        if key in seen:
            raise Exception("duplicate_migration_step")
        seen.add(key)
        result.append(step)
    return result


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


def _sha256_parts(parts) -> str:
    return _sha256("\x1f".join(str(part) for part in parts))


def _now() -> int:
    return int(gl.message.block_timestamp)
