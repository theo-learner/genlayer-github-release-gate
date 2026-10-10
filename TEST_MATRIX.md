# Studio test matrix

Use a separate deployment for each constructor policy (owner, repo, tag, expected SHA).

| Case | Setup | Expected result |
|---|---|---|
| Happy path | Published release, exact tag, non-prerelease, resolved SHA equals pinned SHA | `READY` |
| Wrong tag | Release metadata returns a different tag | `REJECTED_TAG_MISMATCH` |
| Draft | GitHub release has `draft=true` | `REJECTED_DRAFT` |
| Prerelease | GitHub release has `prerelease=true` | `REJECTED_PRERELEASE` |
| Wrong commit | Tag resolves to a different commit SHA | `REJECTED_COMMIT_MISMATCH` |
| Source failure | Either public endpoint returns non-200 | `SOURCE_UNAVAILABLE` |
| Bad constructor | malformed SHA or URL path characters | deployment reverts |

Do not mark a case as passing until the result is observed in Studio. The test matrix is a plan, not a claim of completed tests.
