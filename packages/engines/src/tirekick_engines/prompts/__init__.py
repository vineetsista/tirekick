"""Prompts, as versioned files rather than as string literals.

Three reasons they live on disk instead of inside `vision.py`.

They are a buyer-facing surface. Whatever we tell the model shapes every sentence
the buyer reads, so the banned-language scan covers this directory exactly as it
covers the web copy - a prompt written in the vocabulary of official approval
teaches the model to hand that vocabulary back to us, where it arrives wearing a
confidence score (LIABILITY section 5).

They need to be reviewable. A prompt change alters every finding the product makes
and is invisible in a diff full of Python. As files, a change to the rust prompt is
a change to `rust.md`, and it shows up as one.

They need to be versioned. A cached model response was produced under some prompt,
and the two drift apart silently unless the response records which. Every live
response stamps the version of the prompt that produced it; see `client.py`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

PROMPT_ROOT = Path(__file__).resolve().parent

_HEADER = re.compile(
    r"\A---\s*\nid:\s*(?P<id>[a-z0-9_]+)\s*\nversion:\s*(?P<version>\d+)\s*\n---\s*\n",
    re.MULTILINE,
)


class PromptError(RuntimeError):
    """A prompt file is missing or malformed."""


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    text: str
    path: Path

    @property
    def ref(self) -> str:
        """What a cached response records, so a fixture names its own prompt."""
        return f"{self.id}@v{self.version}"


def _parse(path: Path) -> Prompt:
    raw = path.read_text(encoding="utf-8")
    match = _HEADER.match(raw)
    if match is None:
        raise PromptError(
            f"{path} has no version header. Every prompt declares 'id' and "
            f"'version' so a cached response can name the prompt that produced it."
        )
    if match.group("id") != path.stem:
        raise PromptError(
            f"{path} declares id {match.group('id')!r} but is named {path.stem!r}"
        )
    return Prompt(
        id=match.group("id"),
        version=int(match.group("version")),
        text=raw[match.end() :].strip(),
        path=path,
    )


@cache
def load(family: str, name: str) -> Prompt:
    path = PROMPT_ROOT / family / f"{name}.md"
    if not path.is_file():
        raise PromptError(f"no prompt at {path}")
    return _parse(path)


def system(family: str = "vision") -> Prompt:
    return load(family, "system")


def all_prompts() -> list[Prompt]:
    """Every prompt on disk. Used by the scan and the drift tests."""
    return [_parse(p) for p in sorted(PROMPT_ROOT.rglob("*.md"))]


def fingerprint() -> str:
    """One string naming every prompt version in this build.

    Stamped into the report so a finding can be traced to the instructions that
    produced it. When this changes, model output changes, and a cached response
    from before the change is no longer evidence of current behaviour.
    """
    return ",".join(p.ref for p in all_prompts())
