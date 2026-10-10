# GitHub Release Gate for GenLayer

A reusable Intelligent Contract that checks whether a **specific public GitHub release** is eligible for promotion under a pinned release policy. Each contract instance pins one repository, release tag, and expected commit SHA. Validators independently fetch GitHub's release-by-tag and commit endpoints; the contract compares only normalized facts using GenLayer's strict equivalence principle, then records a deterministic gate outcome.

## Why this is more than a demo

- It couples two independent GitHub API records: release metadata and the commit resolved by the requested tag.
- It has an explicit immutable policy, clear status machine, and audit fields.
- It rejects non-200 sources, draft/prerelease releases, tag mismatches, and commit mismatches. Only literal false flags permit READY; missing/null/malformed flag types are rejected.
- The non-deterministic part is limited to public evidence retrieval; policy evaluation is deterministic Python.
- No LLM is asked to make an unbounded “is this safe?” decision.

## Policy outcomes

- `PENDING`: no check has been run
- `READY`: exact tag, published release, not a prerelease, resolved commit matches the pinned SHA
- `REJECTED_TAG_MISMATCH`, `REJECTED_DRAFT`, `REJECTED_PRERELEASE`, `REJECTED_COMMIT_MISMATCH`
- `SOURCE_UNAVAILABLE`: GitHub did not return both public records with HTTP 200

## Deploy and use

1. Open `github_release_gate.py` in GenLayer Studio.
2. Deploy with the GitHub owner, repository name, release tag, and exact 40-character expected commit SHA.
3. Call `verify_release()`. The returned state is also persisted.
4. Read `get_policy()` to inspect the pinned policy, last outcome, observed SHA, and check count.
5. A deployment pipeline should proceed only when the result is exactly `READY`. For production use, verify finality and independently confirm the source organization's security model.

The tag must be a simple URL-safe GitHub path segment. The repository must be public and have a published GitHub Release for the tag. GitHub's unauthenticated API rate limits and availability can cause `SOURCE_UNAVAILABLE`; a retry runs a new observation. Network/JSON exceptions abort the transaction and do not update state. A caller must require a newly successful finalized verification, not reuse an old stored READY result.

## Test vectors

| Release tag matches | Draft | Prerelease | Resolved SHA matches | Expected status |
|---|---:|---:|---:|---|
| yes | no | no | yes | READY |
| no | no | no | yes | REJECTED_TAG_MISMATCH |
| yes | yes | no | yes | REJECTED_DRAFT |
| yes | no | yes | yes | REJECTED_PRERELEASE |
| yes | no | no | no | REJECTED_COMMIT_MISMATCH |
| unavailable | n/a | n/a | n/a | SOURCE_UNAVAILABLE |

## Security and scope limits

This contract proves that a public GitHub release record currently resolves to a pinned commit under this policy. It does **not** prove that a container image was built from that commit, that CI passed, that the code is safe, or that Kubernetes actually deployed it. A production gate should additionally bind a signed build attestation or immutable image digest to the same commit. GitHub is an external dependency; validator consensus checks the fetched facts, not GitHub's honesty or uptime.

## Validation

Run `python3 -B -m unittest -v test_release_gate` for the dependency-free unit suite. See TEST_RESULTS.md for 27 passing tests and mock limitations, TEST_MATRIX.md for additional planned integration cases, and STUDIO_VALIDATION.md for the observed hosted Studio full-consensus deployment and finalized READY state. This is simulator evidence, not production/testnet deployment evidence.

The code was developed with AI assistance for this contribution.
