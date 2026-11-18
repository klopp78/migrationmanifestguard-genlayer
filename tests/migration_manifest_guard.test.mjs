import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";

const source = readFileSync(new URL("../contracts/migration_manifest_guard.py", import.meta.url), "utf8");
const runner = "py-genlayer:kzybg95x1gn21dw72m7hyg0maaap04n4nx55j9yt6fkdqxtz6bz0";

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function sha(value) {
  return createHash("sha256").update(value).digest("hex");
}

const manifest = {
  old_contract: "0x1111111111111111111111111111111111111111",
  source_commitment: sha("old-source"),
  old_runner: "py-genlayer:legacy-runner",
  next_runner: runner,
  target_network: "studio-next",
  salted_nonce: 7,
  payable_method: "receive_migration_fee",
  state_plan_hash: sha("export-state-v1"),
  migration_steps: [
    "Export immutable state with a source-matched script.",
    "Replace salt_nonce with gl.contract.Salted(7).",
    "Redeploy against the v0.4 runner and verify reads.",
  ],
};

assert.equal(sha(canonical(manifest)).length, 64, "manifest must have a stable SHA-256 commitment");
assert.match(source, /py-genlayer:kzybg95x1gn21dw72m7hyg0maaap04n4nx55j9yt6fkdqxtz6bz0/);
assert.match(source, /from genlayer import gl/);
assert.match(source, /gl\.vm\.run_nondet_unsafe/);
assert.match(source, /source_commitment/);
assert.match(source, /state_plan_hash/);
assert.match(source, /salted_nonce_must_be_positive/);
assert.match(source, /payable_method/);
assert.match(source, /runner_ready.*salted_ready.*payable_ready/s);

const unsafe = { ...manifest, salted_nonce: 0 };
assert.equal(unsafe.salted_nonce > 0, false, "zero salted nonces are rejected before consensus");
const changed = { ...manifest, source_commitment: sha("tampered-source") };
assert.notEqual(sha(canonical(manifest)), sha(canonical(changed)), "source changes must produce a distinct receipt commitment");
console.log("MigrationManifestGuard v0.4 readiness checks passed.");
