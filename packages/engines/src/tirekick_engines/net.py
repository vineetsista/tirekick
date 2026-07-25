"""LAW 3 - no scrape.

Outbound HTTP is allowlisted. The list contains public APIs published by their
issuing body for programmatic use, and nothing else. No marketplace, no
classifieds site, no listing aggregator, ever - not behind a flag, not for
"just building the eval set."

Every request in this codebase goes through `get`. There is no second HTTP path.
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

#: Public federal APIs. Additions require a DECISIONS.md entry naming the terms of
#: use that permit programmatic access.
ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "vpic.nhtsa.dot.gov",  # VIN decode - NHTSA vPIC
        "api.nhtsa.gov",  # recalls, complaints
    }
)

#: Named so the refusal message can be specific about why.
_MARKETPLACE_HINTS = (
    "craigslist",
    "cargurus",
    "autotrader",
    "cars.com",
    "carvana",
    "facebook",
    "marketplace",
    "ebay",
    "offerup",
    "carmax",
)


class ScrapeLawViolation(RuntimeError):
    """Raised when code attempts a request LAW 3 forbids."""


def assert_allowed(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host in ALLOWED_HOSTS:
        return
    if any(hint in host for hint in _MARKETPLACE_HINTS):
        raise ScrapeLawViolation(
            f"LAW 3: {host!r} is a vehicle marketplace. TIREKICK does not fetch "
            f"listings. Comparable listings are pasted in by the user, one at a "
            f"time, deliberately."
        )
    raise ScrapeLawViolation(
        f"LAW 3: {host!r} is not in ALLOWED_HOSTS. Outbound requests are "
        f"allowlisted; add it in net.py with a DECISIONS.md entry naming the "
        f"terms of use that permit programmatic access."
    )


def get(
    url: str, *, params: dict[str, str] | None = None, timeout: float = 20.0
) -> httpx.Response:
    """The only HTTP entry point in the engines."""
    assert_allowed(url)
    response = httpx.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response
