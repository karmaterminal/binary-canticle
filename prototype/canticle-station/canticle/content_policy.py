"""Sender secret scan shared in behavior with openclaw-canticle/src/policy.ts.

RFC-0001 section 15.4 item 6: findings name a kind, never the matched content.
This scan does not supply source-use permission or attest that text is an elected summary.
"""

from collections import Counter
import math
import re


_PATTERNS = (
    ("github_token", r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    ("github_token", r"\bgithub_pat_[A-Za-z0-9_]{40,}"),
    ("api_key", r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}"),
    ("slack_token", r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    ("aws_key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("google_key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("private_key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("discord_token", r"\b[MNO][A-Za-z0-9_-]{23,27}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
)
_TOKEN = re.compile(r"[A-Za-z0-9+/=_-]{32,}")


def secret_findings(text: str) -> list[str]:
    found = {kind for kind, pattern in _PATTERNS if re.search(pattern, text, re.ASCII)}
    for match in _TOKEN.finditer(text):
        token = match.group()
        entropy = -sum((count / len(token)) * math.log2(count / len(token))
                       for count in Counter(token).values())
        if entropy > 4.2:
            found.add("high_entropy")
            break
    return sorted(found)


def derived_text_allowed(payload: bytes) -> bool:
    """A real secret/content-encoding check suitable for the proposal's callback."""
    if type(payload) is not bytes or not payload:
        return False
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return not secret_findings(text)
