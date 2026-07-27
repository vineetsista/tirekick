"""Prompts are product code. These are the tests that treat them that way."""

from __future__ import annotations

import pytest

from tirekick_engines import prompts
from tirekick_engines.engines import vision


def test_every_prompt_parses_and_declares_a_version() -> None:
    loaded = prompts.all_prompts()
    assert loaded, "no prompts found - the path is wrong, not the prompts"
    for prompt in loaded:
        assert prompt.version >= 1
        assert prompt.id == prompt.path.stem
        assert prompt.text


def test_every_pass_has_a_prompt_and_every_prompt_has_a_pass() -> None:
    """A pass with no prompt crashes at runtime; a prompt with no pass is dead
    copy that still gets edited and reviewed as though it shipped."""
    on_disk = {p.id for p in prompts.all_prompts()}
    expected = set(vision.PASS_FINDING_TYPES) | {"classify", "system"}
    assert on_disk == expected


def test_the_system_prompt_states_the_locked_systems() -> None:
    """LAW 2 as defence in depth. The clamp is the guarantee (D-004); this is the
    belt that goes with it, and it is worth failing loudly if someone edits it out."""
    text = prompts.system("vision").text.lower()
    for system in ("brakes", "airbags", "structural", "steering"):
        assert system in text
    assert "never" in text


def test_the_system_prompt_licenses_an_empty_answer() -> None:
    """The single most important instruction in the file.

    A model that believes it is being scored on how much it finds will find
    things. Every false positive this product ships starts here.
    """
    text = prompts.system("vision").text.lower()
    assert "empty list" in text
    assert "cannot determine" in text


def test_the_fingerprint_names_every_prompt_version() -> None:
    fingerprint = prompts.fingerprint()
    for prompt in prompts.all_prompts():
        assert prompt.ref in fingerprint


def test_a_prompt_without_a_header_is_refused(tmp_path, monkeypatch) -> None:
    """Silently defaulting a missing version is how a cached response ends up
    attributed to a prompt that never produced it."""
    bad = tmp_path / "vision"
    bad.mkdir()
    (bad / "broken.md").write_text("no header here", encoding="utf-8")
    monkeypatch.setattr(prompts, "PROMPT_ROOT", tmp_path)
    prompts.load.cache_clear()

    with pytest.raises(prompts.PromptError, match="version header"):
        prompts.load("vision", "broken")
    prompts.load.cache_clear()
