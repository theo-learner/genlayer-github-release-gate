# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Consensus-checked gate for a pinned public GitHub release."""
import json
from genlayer import *

_ALLOWED_SLUG = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._"
_ALLOWED_SHA = "0123456789abcdefABCDEF"


def _valid_segment(value: str) -> bool:
    return (
        1 <= len(value) <= 100
        and value[0] not in ".-"
        and all(char in _ALLOWED_SLUG for char in value)
    )


def _valid_sha(value: str) -> bool:
    return len(value) == 40 and all(char in _ALLOWED_SHA for char in value)


def _classify_release(
    release_tag: str,
    is_draft: bool,
    is_prerelease: bool,
    observed_sha: str,
    expected_tag: str,
    expected_sha: str,
) -> str:
    """Pure policy function: return a stable, auditable gate outcome."""
    if release_tag != expected_tag:
        return "REJECTED_TAG_MISMATCH"
    if is_draft:
        return "REJECTED_DRAFT"
    if is_prerelease:
        return "REJECTED_PRERELEASE"
    if observed_sha.lower() != expected_sha.lower():
        return "REJECTED_COMMIT_MISMATCH"
    return "READY"


class GitHubReleaseGate(gl.Contract):
    """One immutable policy instance per repo/tag/expected commit."""

    owner: str
    repo: str
    tag: str
    expected_sha: str
    status: str
    observed_sha: str
    check_count: u32

    def __init__(self, owner: str, repo: str, tag: str, expected_sha: str):
        if not _valid_segment(owner) or not _valid_segment(repo) or not _valid_segment(tag):
            raise gl.vm.UserError("Owner, repo, and tag must use URL-safe GitHub path characters")
        if not _valid_sha(expected_sha):
            raise gl.vm.UserError("expected_sha must be a 40-character Git commit SHA")
        self.owner = owner
        self.repo = repo
        self.tag = tag
        self.expected_sha = expected_sha.lower()
        self.status = "PENDING"
        self.observed_sha = ""
        self.check_count = u32(0)

    @gl.public.view
    def get_policy(self) -> dict[str, str]:
        return {
            "owner": self.owner,
            "repo": self.repo,
            "tag": self.tag,
            "expected_sha": self.expected_sha,
            "status": self.status,
            "observed_sha": self.observed_sha,
            "check_count": str(self.check_count),
        }

    @gl.public.write
    def verify_release(self) -> str:
        """Independently fetch and consensus-check stable release facts."""
        release_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/tags/{self.tag}"
        commit_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/commits/{self.tag}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        def fetch_facts():
            release_response = gl.nondet.web.get(release_url, headers=headers)
            if release_response.status != 200:
                return {"ok": False, "reason": "release_http_" + str(release_response.status)}
            commit_response = gl.nondet.web.get(commit_url, headers=headers)
            if commit_response.status != 200:
                return {"ok": False, "reason": "commit_http_" + str(commit_response.status)}
            release = json.loads(release_response.body.decode("utf-8"))
            commit = json.loads(commit_response.body.decode("utf-8"))
            return {
                "ok": True,
                "tag": str(release.get("tag_name", "")),
                "draft": release.get("draft") is not False,
                "prerelease": release.get("prerelease") is not False,
                "sha": str(commit.get("sha", "")).lower(),
            }

        # Validators independently fetch the same two public API records.
        # Strict equality is intentional: only normalized, stable facts are compared.
        facts = gl.eq_principle.strict_eq(fetch_facts)
        if not facts["ok"]:
            next_status = "SOURCE_UNAVAILABLE"
            observed_sha = ""
        else:
            next_status = _classify_release(
                facts["tag"], facts["draft"], facts["prerelease"], facts["sha"], self.tag, self.expected_sha
            )
            observed_sha = facts["sha"]

        self.status = next_status
        self.observed_sha = observed_sha
        self.check_count = u32(int(self.check_count) + 1)
        return self.status
