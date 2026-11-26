"""Resolve optional k6 probes; an explicitly required probe must not skip."""
import os
import shutil


def k6_binary(test):
    requested = os.environ.get("CANTICLE_K6") or "k6"
    binary = shutil.which(requested)
    if binary is not None:
        return binary
    message = f"k6 executable not found: {requested}"
    if os.environ.get("CANTICLE_REQUIRE_K6") == "1":
        test.fail(message)
    test.skipTest(message + " (optional; set CANTICLE_REQUIRE_K6=1 to require)")
