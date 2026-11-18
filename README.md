# MigrationManifestGuard for GenLayer

`MigrationManifestGuard` is a reusable GenVM v0.4 migration-readiness primitive. It records a canonical plan for moving an existing contract to Studio Next, Studio, or Bradbury Phase 2, then uses GenLayer validator consensus to issue an immutable receipt.

## What it binds

Each receipt binds:

- the previous contract address and prior runner;
- a SHA-256 source commitment and separately committed state-export plan;
- the official GenVM v0.4 runner hash;
- a positive `gl.contract.Salted(...)` migration nonce;
- a named payable replacement for the removed `__receive__` special method;
- three to twelve ordered migration steps; and
- every validator-assessed readiness flag, advisory, manifest hash, and receipt hash.

The contract does not accept a caller-provided "ready" status. It derives the manifest hash itself and validators independently rerun the review, comparing all consequential fields before a receipt is stored.

## Main method

`assess_migration(old_contract, source_commitment, old_runner, target_network, salted_nonce, payable_method, state_plan_hash, migration_steps)` returns an `mmg_...` receipt ID.

Supported target networks are `studio-next`, `studio`, and `bradbury-phase-2`.

## Run focused checks

```bash
node tests/migration_manifest_guard.test.mjs
```

## GenVM v0.4 migration checklist

1. Replace the old `Depends` runner with the v0.4 runner shown at the top of the contract.
2. Replace `salt_nonce=N` with `salted=gl.contract.Salted(N)` in child-address creation.
3. Replace `__receive__` with a named `@gl.public.write.payable` method.
4. Re-deploy, verify read methods, and retain both source and state-plan commitments.

This repository intentionally includes only the full matching contract and focused tests so reviewers can reproduce its behavior from one source of truth.
