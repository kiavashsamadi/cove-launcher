"""Validate one captured native app-registration command; never execute it.

For the inspected command/server implementation, the app-specific end/ok
callback follows the registration write. Require the matching start callback
and natural successful CLI exit as well. A timeout, missing callback or registry
snapshot is not completion evidence. The private adapter must separately bind
the capture to its owned process, exact tool build and sealed operation.

This is not a cancellation mechanism, dependency check or deployment approval.
Native deactivation can terminate the app before changing its registration.
"""
import re

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}\Z")
_CALLBACK = re.compile(
    r"__app_return_cb req_id\[([1-9][0-9]{0,9})\] pkg_type\[app\] "
    r"pkgid\[([^\[\]\r\n]+)\] appid\[([^\[\]\r\n]+)\] "
    r"key\[(start|end)\] val\[([^\[\]\r\n]+)\]"
)
_ELAPSED = re.compile(r"spend time for pkgcmd is \[[0-9]{1,10}\]ms")


def verify_success(call, *, app_id, package_id, operation):
    """Return correlated success evidence or reject an unproven outcome.

package_id is the expected callback identifier from the reviewed native path,
not an inferred prefix of app_id. Reject even an apparently successful callback
if the process timed out or the output contains an unrelated request.
"""
    if operation not in ("activate", "deactivate"):
        raise ValueError("One reviewed app operation required")
    if any(type(v) is not str or not _IDENTIFIER.fullmatch(v)
           for v in (app_id, package_id)):
        raise ValueError("Explicit app and callback package identifiers required")
    if not isinstance(call, dict) or call.get("role") != operation:
        raise ValueError("Captured operation differs")
    if (type(call.get("pid")) is not int or call["pid"] <= 1
            or type(call.get("exit_code")) is not int or call["exit_code"] != 0
            or call.get("timed_out") is not False or call.get("stderr") != ""):
        raise ValueError("Natural successful child exit required")
    output = call.get("stdout")
    if (type(output) is not str or len(output.encode("utf-8")) > 16384
            or "\r" in output or not output.endswith("\n")):
        raise ValueError("Complete bounded native output required")
    lines = output.splitlines()
    if len(lines) != 3 or not _ELAPSED.fullmatch(lines[2]):
        raise ValueError("Exactly one complete app callback sequence required")
    callbacks = [_CALLBACK.fullmatch(line) for line in lines[:2]]
    if any(match is None for match in callbacks):
        raise ValueError("Native app callback format differs")
    start, end = (match.groups() for match in callbacks)
    expected = "enable_app" if operation == "activate" else "disable_app"
    if (start[1:3] != (package_id, app_id) or end[:3] != start[:3]
            or start[3:] != ("start", expected) or end[3:] != ("end", "ok")):
        raise ValueError("Request identity, operation or terminal success differs")
    request_id = int(start[0])
    if request_id > 2147483647:
        raise ValueError("Native request ID exceeds its signed integer range")
    return {"terminal_success": True, "request_id": request_id,
            "operation": operation, "app_id": app_id,
            "deployment_qualified": False}
