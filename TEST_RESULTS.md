# Release gate local test results

- Executed: 2026-10-10T14:25:48.238089+00:00
- Interpreter: 3.13.12 (main, Mar 20 2026, 00:20:47) [Clang 22.1.1 ]
- Result: **27 tests passed**, exit code `0`.
- Syntax: the updated contract and test source compile successfully with CPython `compile(..., "exec")` in memory. No `.pyc` / `__pycache__` files are created. This is not GenLayer runtime compilation.
- This revision modifies only `test_release_gate.py` and `TEST_RESULTS.md`.
- Contract source inspected after parent revision; unchanged by this test work, SHA-256: `84e5bf7cb2c7553e827e1860811884fd776dce33ffc1aeddcdab135fc6b883aa`.

## Method and coverage

Standard-library `unittest` and `unittest.mock`, with no third-party test dependencies and no live HTTP calls. The actual `github_release_gate.py` source is compiled and executed under a temporary minimal `genlayer` module stub. This is **not the real GenLayer runtime**.

The stub supplies `Contract=object`, identity `public.view` / `public.write` decorators, a local `UserError` exception, and `u32=int`. HTTP `get` and `strict_eq` are mocks. The strict equality mock executes the provided callback once and returns its facts; it does not compare independent validators or prove consensus.

Covered:

- Slug character/length boundaries, unsafe path inputs, SHA format, constructor rejection and normalization, initial PENDING state, detached policy output.
- All 16 policy combinations and rejection precedence; case-sensitive tags and case-insensitive SHAs.
- Mock HTTP Response uses `.status`, with **no `.status_code` attribute**. Successful callback invocation checks this regression explicitly. Release/commit failure paths exercise `.status` for rejection reason strings as well.
- Mock HTTP URLs, headers, normalized callback facts, release failure short-circuit, commit HTTP failures, missing field defaults.
- Each draft/prerelease flag independently rejects null, missing values, strings, integers, floats, lists, and objects. This includes false-like incorrect types (`0`, `0.0`, empty string/list/object). Both null flags are rejected with draft precedence. Literal boolean false for both flags allows READY when tag/SHA match.
- READY and each rejection state, repeated verification/count increments, SOURCE_UNAVAILABLE clearing observed SHA, recovery to READY, unchanged configured policy fields.
- Transport/strict_eq exceptions, malformed JSON, invalid UTF-8, and non-object JSON leave the local object's recorded state unchanged because failure occurs before assignments.
- Non-string commit SHA is normalized to a string and rejected when mismatched.

## Observed behavior and limitations

- The revised callback uses `release.get("draft") is not False` and `release.get("prerelease") is not False`. Only literal boolean false passes each flag; null/missing/incorrect types are rejected. This replaces the previous permissive null coercion behavior.
- Mock responses now expose `.status`, matching the updated contract. These offline tests do not independently establish the real SDK Response implementation or validate the parent-reported Studio behavior.
- HTTP non-200 responses become SOURCE_UNAVAILABLE. **Transport, decoding, malformed JSON, and non-object JSON exceptions still propagate**; they do not increment the local check count. No contract changes were made by this test work.
- These tests do **not** verify validator agreement, nondeterministic execution isolation, leader/validator divergence, distributed consensus, full runtime SDK compatibility, ABI/type serialization, deployment, on-chain persistence, permissions, network access, or live GitHub responses.
- `u32=int` does not model fixed-width overflow or runtime numeric semantics. Identity decorators do not model view/write enforcement. Local pre-assignment exception behavior does not prove VM transaction rollback.
- Constructor tests cover its declared string inputs. Runtime handling of non-string call arguments is not established.
- Real runtime compilation/deployment remains with the parent task. Mock success must not be interpreted as deployment or consensus success.

## Reproduce

```sh
cd /Users/theo/.aside/u/0/sessions/2026-10-10_3lQgECIazcsMmqSU/tmp/release-gate
python3 -B -m unittest -v test_release_gate
python3 -B - <<'PYCODE'
from pathlib import Path
for filename in ('github_release_gate.py', 'test_release_gate.py'):
    compile(Path(filename).read_text(encoding='utf-8'), filename, 'exec')
    print('SYNTAX PASS:', filename)
PYCODE
```

## Captured execution output

```text
SYNTAX PASS: github_release_gate.py
SYNTAX PASS: test_release_gate.py
test_each_path_parameter_validated (test_release_gate.ConstructorTests.test_each_path_parameter_validated) ... ok
test_expected_sha_validated (test_release_gate.ConstructorTests.test_expected_sha_validated) ... ok
test_get_policy_returns_detached_dict (test_release_gate.ConstructorTests.test_get_policy_returns_detached_dict) ... ok
test_initial_policy_and_sha_normalization (test_release_gate.ConstructorTests.test_initial_policy_and_sha_normalization) ... ok
test_policy_all_flag_combinations_and_priority (test_release_gate.PolicyTests.test_policy_all_flag_combinations_and_priority) ... ok
test_policy_sha_case_insensitive_but_tag_case_sensitive (test_release_gate.PolicyTests.test_policy_sha_case_insensitive_but_tag_case_sensitive) ... ok
test_segment_rejects_unsafe_characters_and_boundaries (test_release_gate.PolicyTests.test_segment_rejects_unsafe_characters_and_boundaries) ... ok
test_segment_valid_characters_and_length_boundaries (test_release_gate.PolicyTests.test_segment_valid_characters_and_length_boundaries) ... ok
test_sha_rejects_wrong_length_or_non_hex (test_release_gate.PolicyTests.test_sha_rejects_wrong_length_or_non_hex) ... ok
test_sha_valid_mixed_case (test_release_gate.PolicyTests.test_sha_valid_mixed_case) ... ok
test_callback_converts_non_string_sha_to_string (test_release_gate.VerificationTests.test_callback_converts_non_string_sha_to_string) ... ok
test_commit_http_failures_do_not_decode_bodies (test_release_gate.VerificationTests.test_commit_http_failures_do_not_decode_bodies) ... ok
test_commit_transport_exception_preserves_state (test_release_gate.VerificationTests.test_commit_transport_exception_preserves_state) ... ok
test_incorrect_type_release_flags_rejected (test_release_gate.VerificationTests.test_incorrect_type_release_flags_rejected) ... ok
test_invalid_utf8_preserves_state (test_release_gate.VerificationTests.test_invalid_utf8_preserves_state) ... ok
test_malformed_json_preserves_state (test_release_gate.VerificationTests.test_malformed_json_preserves_state) ... ok
test_missing_each_release_flag_rejected (test_release_gate.VerificationTests.test_missing_each_release_flag_rejected) ... ok
test_missing_fields_fail_closed (test_release_gate.VerificationTests.test_missing_fields_fail_closed) ... ok
test_non_object_json_preserves_state (test_release_gate.VerificationTests.test_non_object_json_preserves_state) ... ok
test_null_release_flags_rejected (test_release_gate.VerificationTests.test_null_release_flags_rejected) ... ok
test_only_literal_false_flags_allow_ready (test_release_gate.VerificationTests.test_only_literal_false_flags_allow_ready) ... ok
test_release_http_failures_skip_commit_request (test_release_gate.VerificationTests.test_release_http_failures_skip_commit_request) ... ok
test_repeated_state_transitions_and_immutable_policy (test_release_gate.VerificationTests.test_repeated_state_transitions_and_immutable_policy) ... ok
test_response_uses_status_without_status_code (test_release_gate.VerificationTests.test_response_uses_status_without_status_code) ... ok
test_strict_eq_exception_preserves_state (test_release_gate.VerificationTests.test_strict_eq_exception_preserves_state) ... ok
test_success_callback_urls_headers_and_normalized_facts (test_release_gate.VerificationTests.test_success_callback_urls_headers_and_normalized_facts) ... ok
test_transport_exception_preserves_previous_state (test_release_gate.VerificationTests.test_transport_exception_preserves_previous_state) ... ok

----------------------------------------------------------------------
Ran 27 tests in 0.004s

OK
```
