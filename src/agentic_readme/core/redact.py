"""Credential redaction shared by grounding (facts.json, README) and trace masking."""

from __future__ import annotations

import re

# Userinfo in an HTTP(S) URL, e.g. https://x-access-token:<token>@github.com/owner/repo.git.
# A bare username counts too: https://<token>@github.com is a common CI form.
# SSH remotes (git@github.com:owner/repo.git, ssh://git@...) are left alone.
_HTTP_URL_CREDENTIALS = re.compile(r"(?i)(?<=\bhttps://)[^/\s@]+@|(?<=\bhttp://)[^/\s@]+@")


def strip_url_credentials(text: str) -> str:
    """Remove the `user[:pass]@` part from any HTTP(S) URLs in text."""
    return _HTTP_URL_CREDENTIALS.sub("", text)
