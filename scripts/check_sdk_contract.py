"""Does the installed Anthropic SDK still define what client.py reads off it? D-064.

`client._retryable_errors` resolves two attributes at call time:

    return (anthropic.APIStatusError, anthropic.APIConnectionError)

and returns `()` when the import fails. An empty tuple is a legal `except` clause
that catches nothing, so a rename on the SDK's side does not raise here - it
quietly turns the retry loop into a single attempt, and the symptom is a paid run
dying on the first 429 that a retry would have absorbed.

Nothing in `packages/engines/tests/` can check this, and that is deliberate rather
than an oversight. Those tests must pass with no SDK installed, because running
without one is the product's documented default (D-009) and CI's
`no-key-required` job exists to prove it. The one line that would close the gap
inside pytest - `pytest.importorskip("anthropic")` - is the line that took the
retry tests out of CI for a full phase while still reporting a pass, and
`test_no_test_in_this_package_is_conditional_on_the_live_extra` now forbids it.

So the check lives here, outside pytest, and is run by a CI job that installs the
`live` extra on purpose. The difference that matters: this script FAILS when the
SDK is absent. It has no skip. A gate that goes green because nothing ran is the
failure this project has now found seven times.

    python scripts/check_sdk_contract.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "packages" / "engines" / "src"))

#: Every attribute `client.py` reads off the SDK, and why it reads it.
REQUIRED = {
    "APIStatusError": "the base class of every HTTP error, including the 429 the retry loop is for",
    "APIConnectionError": "a transport failure with no response, which is the other retryable case",
}


def main() -> int:
    try:
        import anthropic
    except ImportError as missing:
        print(
            "error: the anthropic SDK is not installed, so the retry contract is\n"
            "  unverified. This script does not skip - install the live extra:\n"
            "    packages/engines/.venv/bin/pip install -e 'packages/engines[live]'\n"
            f"  ({missing})",
            file=sys.stderr,
        )
        return 1

    version = getattr(anthropic, "__version__", "unknown")
    missing_names = [name for name in REQUIRED if not hasattr(anthropic, name)]
    if missing_names:
        for name in missing_names:
            print(
                f"error: anthropic {version} does not define {name} - {REQUIRED[name]}",
                file=sys.stderr,
            )
        print(
            "\n  client._retryable_errors would raise AttributeError on the first send,\n"
            "  or - if that resolution is ever made forgiving - return a shorter tuple\n"
            "  and retry nothing. Update client.py to the SDK's current names.",
            file=sys.stderr,
        )
        return 1

    from tirekick_engines.client import _retryable_errors

    _retryable_errors.cache_clear()
    try:
        resolved = _retryable_errors()
    finally:
        _retryable_errors.cache_clear()

    expected = tuple(getattr(anthropic, name) for name in REQUIRED)
    if resolved != expected:
        print(
            f"error: client._retryable_errors() returned {resolved!r};\n"
            f"  the SDK's own attributes are {expected!r}",
            file=sys.stderr,
        )
        return 1

    names = ", ".join(REQUIRED)
    print(f"  anthropic {version}: {names} present, and the retry loop resolves to them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
