import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from native_app_completion import verify_success


def capture(operation="deactivate"):
    action = "disable_app" if operation == "deactivate" else "enable_app"
    prefix = "__app_return_cb req_id[7] pkg_type[app] pkgid[example.ad] appid[example.ad.Player] "
    return {"role": operation, "pid": 123, "exit_code": 0, "timed_out": False,
            "stdout": prefix + f"key[start] val[{action}]\n" + prefix
            + "key[end] val[ok]\nspend time for pkgcmd is [83]ms\n", "stderr": ""}


def verify(call, operation="deactivate"):
    return verify_success(call, app_id="example.ad.Player",
                          package_id="example.ad", operation=operation)


class NativeAppCompletionTests(unittest.TestCase):
    def test_forward_and_inverse_are_correlated(self):
        for operation in ("activate", "deactivate"):
            result = verify(capture(operation), operation)
            self.assertTrue(result["terminal_success"])
            self.assertEqual(result["request_id"], 7)
            self.assertFalse(result["deployment_qualified"])

    def test_natural_exit_without_terminal_callback_is_insufficient(self):
        call = capture()
        call["stdout"] = call["stdout"].splitlines()[0] + "\n"
        with self.assertRaises(ValueError):
            verify(call)

    def test_timeout_or_abnormal_exit_cannot_authorize_inverse(self):
        for field, value in (("timed_out", True), ("timed_out", 0),
                             ("timed_out", None), ("exit_code", 124),
                             ("exit_code", False), ("pid", True), ("pid", 1),
                             ("stderr", "unexpected failure")):
            with self.subTest(field=field, value=value):
                call = capture(); call[field] = value
                with self.assertRaises(ValueError):
                    verify(call)

    def test_mixed_requests_targets_or_operations_are_rejected(self):
        for old, new in (("req_id[7]", "req_id[8]"),
                         ("appid[example.ad.Player]", "appid[example.other]"),
                         ("pkgid[example.ad]", "pkgid[example.other]")):
            call = capture()
            lines = call["stdout"].splitlines()
            lines[1] = lines[1].replace(old, new)
            call["stdout"] = "\n".join(lines) + "\n"
            with self.assertRaises(ValueError):
                verify(call)
        call = capture("activate"); call["role"] = "deactivate"
        with self.assertRaises(ValueError):
            verify(call)

    def test_failure_duplicates_and_reordered_events_are_not_success(self):
        original = capture()
        lines = original["stdout"].splitlines()
        variants = [original["stdout"].replace("val[ok]", "val[fail]"),
                    "\n".join([lines[1], lines[0], lines[2]]) + "\n",
                    original["stdout"] + lines[1] + "\n",
                    original["stdout"].replace("req_id[7]", "req_id[2147483648]")]
        for output in variants:
            call = copy.deepcopy(original); call["stdout"] = output
            with self.assertRaises(ValueError):
                verify(call)

    def test_partial_or_unbounded_output_is_rejected(self):
        for output in (None, "x" * 16385, capture()["stdout"].rstrip("\n"),
                       capture()["stdout"].replace("\n", "\r\n")):
            call = capture(); call["stdout"] = output
            with self.assertRaises(ValueError):
                verify(call)

    def test_explicit_expected_identity_and_operation_required(self):
        for kwargs in ({"app_id": "bad\nname"}, {"package_id": ""},
                       {"operation": "uninstall"}):
            args = dict(app_id="example.ad.Player", package_id="example.ad",
                        operation="deactivate"); args.update(kwargs)
            with self.assertRaises(ValueError):
                verify_success(capture(), **args)


if __name__ == "__main__":
    unittest.main()
