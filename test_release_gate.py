"""Offline CPython tests, not GenLayer runtime or consensus verification.

The minimal genlayer stub provides an object base, identity decorators, a local
UserError, and int for u32. Mock strict_eq executes its callback exactly once.
No validator coordination, VM transaction rollback, or u32 overflow is emulated.
Run with: python3 -B -m unittest -v test_release_gate
"""
import itertools
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).with_name("github_release_gate.py")
SHA = "a" * 40
OTHER_SHA = "b" * 40


class StubUserError(Exception):
    pass


def identity(function):
    return function


def load_contract():
    """Compile/execute the actual source without installing GenLayer or pycache."""
    stub = types.ModuleType("genlayer")
    stub.gl = types.SimpleNamespace(
        Contract=object,
        public=types.SimpleNamespace(view=identity, write=identity),
        vm=types.SimpleNamespace(UserError=StubUserError),
        nondet=types.SimpleNamespace(web=types.SimpleNamespace(get=None)),
        eq_principle=types.SimpleNamespace(strict_eq=None),
    )
    stub.u32 = int
    stub.__all__ = ["gl", "u32"]
    module = types.ModuleType("release_gate_under_test")
    module.__file__ = str(SOURCE)
    with patch.dict(sys.modules, {"genlayer": stub}):
        exec(compile(SOURCE.read_text(encoding="utf-8"), str(SOURCE), "exec"), module.__dict__)
    return module


contract = load_contract()


def response(status=200, data=None, body=None):
    if body is None:
        body = json.dumps(data).encode("utf-8")
    # Match the SDK Response attribute; deliberately omit status_code.
    return types.SimpleNamespace(status=status, body=body)


def release(**updates):
    return {"tag_name": "v1.2.3", "draft": False, "prerelease": False, **updates}


class PolicyTests(unittest.TestCase):
    def test_segment_valid_characters_and_length_boundaries(self):
        for value in ("a", "A0", "owner_name", "v1.2.3-rc_1", "a" * 100,
                      "a" + contract._ALLOWED_SLUG):
            with self.subTest(value=value):
                self.assertTrue(contract._valid_segment(value))

    def test_segment_rejects_unsafe_characters_and_boundaries(self):
        for value in ("", "a" * 101, ".hidden", "-repo", "../repo", "a/b", "a\\b",
                      "a b", "a?b", "a#b", "a%b", "a:b", "a@b", "한글", "a\n", "a\x00"):
            with self.subTest(value=value):
                self.assertFalse(contract._valid_segment(value))

    def test_sha_valid_mixed_case(self):
        self.assertTrue(contract._valid_sha("0123456789abcdefABCDEF" + "0" * 18))

    def test_sha_rejects_wrong_length_or_non_hex(self):
        for value in ("", "a" * 39, "a" * 41, "g" * 40, "a" * 39 + " ", "0x" + "a" * 38):
            with self.subTest(value=value):
                self.assertFalse(contract._valid_sha(value))

    def test_policy_all_flag_combinations_and_priority(self):
        for tag_matches, draft, prerelease, sha_matches in itertools.product((False, True), repeat=4):
            with self.subTest(tag_matches=tag_matches, draft=draft, prerelease=prerelease,
                              sha_matches=sha_matches):
                expected = ("REJECTED_TAG_MISMATCH" if not tag_matches else
                            "REJECTED_DRAFT" if draft else
                            "REJECTED_PRERELEASE" if prerelease else
                            "REJECTED_COMMIT_MISMATCH" if not sha_matches else "READY")
                self.assertEqual(contract._classify_release(
                    "v1.2.3" if tag_matches else "v2", draft, prerelease,
                    SHA if sha_matches else OTHER_SHA, "v1.2.3", SHA), expected)

    def test_policy_sha_case_insensitive_but_tag_case_sensitive(self):
        self.assertEqual(contract._classify_release("v1", False, False, SHA.upper(), "v1", SHA), "READY")
        self.assertEqual(contract._classify_release("V1", False, False, SHA, "v1", SHA),
                         "REJECTED_TAG_MISMATCH")


class ConstructorTests(unittest.TestCase):
    def test_initial_policy_and_sha_normalization(self):
        gate = contract.GitHubReleaseGate("org", "repo", "v1.2.3", SHA.upper())
        self.assertEqual(gate.get_policy(), {
            "owner": "org", "repo": "repo", "tag": "v1.2.3", "expected_sha": SHA,
            "status": "PENDING", "observed_sha": "", "check_count": "0",
        })

    def test_each_path_parameter_validated(self):
        for index in range(3):
            for invalid in ("", "../unsafe", "a/b", "-first", "a" * 101):
                values = ["org", "repo", "v1.2.3", SHA]
                values[index] = invalid
                with self.subTest(index=index, invalid=invalid):
                    with self.assertRaisesRegex(StubUserError, "URL-safe"):
                        contract.GitHubReleaseGate(*values)

    def test_expected_sha_validated(self):
        for value in ("", "a" * 39, "a" * 41, "z" * 40):
            with self.subTest(value=value):
                with self.assertRaisesRegex(StubUserError, "40-character"):
                    contract.GitHubReleaseGate("org", "repo", "v1.2.3", value)

    def test_get_policy_returns_detached_dict(self):
        gate = contract.GitHubReleaseGate("org", "repo", "v1.2.3", SHA)
        exported = gate.get_policy()
        exported["status"] = "READY"
        self.assertEqual(gate.status, "PENDING")


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.gate = contract.GitHubReleaseGate("org", "repo", "v1.2.3", SHA)
        self.facts = []
        self.http = Mock()
        self.strict = Mock(side_effect=self.execute_callback)
        self.web_patch = patch.object(contract.gl.nondet.web, "get", self.http)
        self.strict_patch = patch.object(contract.gl.eq_principle, "strict_eq", self.strict)
        self.web_patch.start()
        self.strict_patch.start()
        self.addCleanup(self.web_patch.stop)
        self.addCleanup(self.strict_patch.stop)

    def execute_callback(self, callback):
        self.assertTrue(callable(callback))
        facts = callback()
        self.facts.append(facts)
        return facts

    def check(self, release_data=None, commit_data=None):
        self.http.side_effect = [response(data=release() if release_data is None else release_data),
                                 response(data={"sha": SHA} if commit_data is None else commit_data)]
        return self.gate.verify_release()

    def assert_unchanged_after_error(self, error):
        before = self.gate.get_policy()
        with self.assertRaises(error):
            self.gate.verify_release()
        self.assertEqual(self.gate.get_policy(), before)

    def test_success_callback_urls_headers_and_normalized_facts(self):
        self.assertEqual(self.check(commit_data={"sha": SHA.upper(), "ignored": 3}), "READY")
        self.strict.assert_called_once()
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        self.assertEqual(self.http.call_args_list, [
            unittest.mock.call("https://api.github.com/repos/org/repo/releases/tags/v1.2.3", headers=headers),
            unittest.mock.call("https://api.github.com/repos/org/repo/commits/v1.2.3", headers=headers),
        ])
        self.assertEqual(self.facts, [{"ok": True, "tag": "v1.2.3", "draft": False,
                                      "prerelease": False, "sha": SHA}])
        self.assertEqual(self.gate.observed_sha, SHA)
        self.assertEqual(self.gate.get_policy()["check_count"], "1")

    def test_release_http_failures_skip_commit_request(self):
        for status in (201, 301, 404, 429, 500):
            with self.subTest(status=status):
                self.http.reset_mock()
                self.http.side_effect = [response(status=status, body=b"not json")]
                self.assertEqual(self.gate.verify_release(), "SOURCE_UNAVAILABLE")
                self.http.assert_called_once()
                self.assertEqual(self.facts[-1], {"ok": False, "reason": f"release_http_{status}"})
                self.assertEqual(self.gate.observed_sha, "")
        self.assertEqual(self.gate.check_count, 5)

    def test_commit_http_failures_do_not_decode_bodies(self):
        for status in (404, 429, 503):
            with self.subTest(status=status):
                self.http.reset_mock()
                self.http.side_effect = [response(body=b"not json"), response(status=status, body=b"bad")]
                self.assertEqual(self.gate.verify_release(), "SOURCE_UNAVAILABLE")
                self.assertEqual(self.http.call_count, 2)
                self.assertEqual(self.facts[-1], {"ok": False, "reason": f"commit_http_{status}"})
        self.assertEqual(self.gate.check_count, 3)

    def test_missing_fields_fail_closed(self):
        cases = [({}, {"sha": SHA}, "REJECTED_TAG_MISMATCH"),
                 ({"tag_name": "v1.2.3"}, {"sha": SHA}, "REJECTED_DRAFT"),
                 ({"tag_name": "v1.2.3", "draft": False}, {"sha": SHA}, "REJECTED_PRERELEASE"),
                 (release(), {}, "REJECTED_COMMIT_MISMATCH")]
        for release_data, commit_data, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(self.check(release_data, commit_data), expected)

    def test_response_uses_status_without_status_code(self):
        release_response = response(data=release())
        commit_response = response(data={"sha": SHA})
        for reply in (release_response, commit_response):
            self.assertEqual(reply.status, 200)
            self.assertFalse(hasattr(reply, "status_code"))
        self.http.side_effect = [release_response, commit_response]
        self.assertEqual(self.gate.verify_release(), "READY")

    def test_null_release_flags_rejected(self):
        for field, expected in (("draft", "REJECTED_DRAFT"),
                                ("prerelease", "REJECTED_PRERELEASE")):
            with self.subTest(field=field):
                self.assertEqual(self.check(release(**{field: None})), expected)
                self.assertIs(self.facts[-1][field], True)
        self.assertEqual(self.check(release(draft=None, prerelease=None)), "REJECTED_DRAFT")

    def test_missing_each_release_flag_rejected(self):
        for field, expected in (("draft", "REJECTED_DRAFT"),
                                ("prerelease", "REJECTED_PRERELEASE")):
            with self.subTest(field=field):
                data = release()
                del data[field]
                self.assertEqual(self.check(data), expected)
                self.assertIs(self.facts[-1][field], True)

    def test_incorrect_type_release_flags_rejected(self):
        # Include false-like values: 0 == False, but 0 is not False.
        invalid = ("false", "true", "", 0, 0.0, 1, [], {}, [False], {"value": False})
        for field, expected in (("draft", "REJECTED_DRAFT"),
                                ("prerelease", "REJECTED_PRERELEASE")):
            for value in invalid:
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.check(release(**{field: value})), expected)
                    self.assertIs(self.facts[-1][field], True)

    def test_only_literal_false_flags_allow_ready(self):
        self.assertEqual(self.check(release(draft=False, prerelease=False)), "READY")
        self.assertIs(self.facts[-1]["draft"], False)
        self.assertIs(self.facts[-1]["prerelease"], False)

    def test_callback_converts_non_string_sha_to_string(self):
        self.assertEqual(self.check(commit_data={"sha": 123}), "REJECTED_COMMIT_MISMATCH")
        self.assertEqual(self.gate.observed_sha, "123")

    def test_repeated_state_transitions_and_immutable_policy(self):
        policy = {key: self.gate.get_policy()[key] for key in ("owner", "repo", "tag", "expected_sha")}
        cases = [(release(), {"sha": SHA}, "READY", SHA),
                 (release(tag_name="different"), {"sha": SHA}, "REJECTED_TAG_MISMATCH", SHA),
                 (release(draft=True), {"sha": SHA}, "REJECTED_DRAFT", SHA),
                 (release(prerelease=True), {"sha": SHA}, "REJECTED_PRERELEASE", SHA),
                 (release(), {"sha": OTHER_SHA}, "REJECTED_COMMIT_MISMATCH", OTHER_SHA),
                 (release(), {"sha": SHA}, "READY", SHA)]
        for count, (release_data, commit_data, status, observed) in enumerate(cases, 1):
            with self.subTest(count=count):
                self.assertEqual(self.check(release_data, commit_data), status)
                self.assertEqual(self.gate.observed_sha, observed)
                self.assertEqual(self.gate.check_count, count)
                self.assertEqual({key: self.gate.get_policy()[key] for key in policy}, policy)
        self.http.side_effect = [response(status=404)]
        self.assertEqual(self.gate.verify_release(), "SOURCE_UNAVAILABLE")
        self.assertEqual(self.gate.observed_sha, "")
        self.assertEqual(self.gate.check_count, 7)
        self.assertEqual(self.check(), "READY")
        self.assertEqual(self.gate.check_count, 8)

    def test_transport_exception_preserves_previous_state(self):
        self.check()
        self.http.side_effect = OSError("mock network failure")
        self.assert_unchanged_after_error(OSError)

    def test_commit_transport_exception_preserves_state(self):
        self.http.side_effect = [response(data=release()), OSError("mock commit failure")]
        self.assert_unchanged_after_error(OSError)

    def test_strict_eq_exception_preserves_state(self):
        self.check()
        self.strict.side_effect = RuntimeError("mock consensus failure")
        self.assert_unchanged_after_error(RuntimeError)
        self.assertEqual(self.http.call_count, 2)  # no further callback executed

    def test_malformed_json_preserves_state(self):
        for malformed_index in (0, 1):
            with self.subTest(index=malformed_index):
                replies = [response(data=release()), response(data={"sha": SHA})]
                replies[malformed_index] = response(body=b"{not json")
                self.http.side_effect = replies
                self.assert_unchanged_after_error(json.JSONDecodeError)

    def test_invalid_utf8_preserves_state(self):
        self.http.side_effect = [response(body=b"\xff"), response(data={"sha": SHA})]
        self.assert_unchanged_after_error(UnicodeDecodeError)

    def test_non_object_json_preserves_state(self):
        for index, data in itertools.product((0, 1), ([], None, "string", 123)):
            with self.subTest(index=index, data=data):
                replies = [response(data=release()), response(data={"sha": SHA})]
                replies[index] = response(data=data)
                self.http.side_effect = replies
                self.assert_unchanged_after_error(AttributeError)


if __name__ == "__main__":
    unittest.main(verbosity=2)
