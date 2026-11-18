import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../contracts/migration_manifest_guard.py', import.meta.url), 'utf8');

assert.match(source, /class MigrationManifestGuard\(genlayer\.contract\.Contract\)/);
assert.match(source, /@genlayer\.public\.write/);
assert.match(source, /py-genlayer:kzybg95x1gn21dw72m7hyg0maaap04n4nx55j9yt6fkdqxtz6bz0/);
assert.match(source, /"next_runner": V04_RUNNER/);
assert.match(source, /"salted_nonce_positive"/);
assert.match(source, /"named_payable_entrypoint"/);
assert.match(source, /_sha256\(_canonical_json\(receipt\)\)/);
assert.doesNotMatch(source, /genlayer\.gl/);

console.log('MigrationManifestGuard v0.4 source checks passed.');
