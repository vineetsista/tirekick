"""The live vision path, exercised against a fake API.

There is no API key in this environment and CI must never need one (LAW 7), so
none of this calls Anthropic. What it does is pin the request we would send: the
system prompt, the forced tool, the image block, the schema, and the accounting
that comes back. A live path that is never exercised is a live path that breaks
silently between the phase that wrote it and the phase that first runs it.

The test worth reading is `test_no_banned_language_reaches_the_model`. Every other
banned-language check in this repository scans source files; this one scans the
bytes actually assembled for the wire.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tirekick_engines import prompts
from tirekick_engines.client import (
    LiveModeUnavailable,
    ModelClient,
    encode_image,
    image_tokens,
)
from tirekick_engines.cogs import CostMeter
from tirekick_engines.copy_rules import scan_text
from tirekick_engines.engines import vision

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_MEDIA = REPO_ROOT / "fixtures" / "demo-01" / "media"


@dataclass
class _Usage:
    input_tokens: int = 1200
    output_tokens: int = 300


@dataclass
class _ToolUse:
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class _Message:
    content: list[Any]
    usage: _Usage


class FakeAnthropic:
    """Records what it was asked to send, and returns a canned tool call."""

    def __init__(self, payload: dict[str, Any], *, raise_first: Exception | None = None):
        self.payload = payload
        self.raise_first = raise_first
        self.calls: list[dict[str, Any]] = []
        self.messages = self

    def create(self, **kwargs: Any) -> _Message:
        self.calls.append(kwargs)
        if self.raise_first is not None and len(self.calls) == 1:
            error, self.raise_first = self.raise_first, None
            raise error
        return _Message(content=[_ToolUse(input=dict(self.payload))], usage=_Usage())


def _client(
    tmp_path: Path, payload: dict[str, Any], **kwargs: Any
) -> tuple[ModelClient, FakeAnthropic, CostMeter]:
    fake = FakeAnthropic(payload, **kwargs)
    meter = CostMeter(mode="live", model="claude-sonnet-5")
    client = ModelClient(mode="live", cache_dir=tmp_path, meter=meter, model="claude-sonnet-5")
    client._anthropic = lambda: fake  # type: ignore[method-assign]
    return client, fake, meter


def _classify_call(tmp_path: Path) -> tuple[dict[str, Any], FakeAnthropic, CostMeter]:
    client, fake, meter = _client(
        tmp_path, {"view_class": "exterior_front", "confidence": 0.9, "basis": "grille"}
    )
    prompt = prompts.load("vision", "classify")
    result = client.call(
        engine="vision",
        task="classify",
        subject="photo_02",
        prompt=prompt.text,
        system=prompts.system("vision").text,
        schema=vision.CLASSIFY_SCHEMA,
        image_paths=[FIXTURE_MEDIA / "photo_02.jpg"],
        prompt_ref=prompt.ref,
    )
    return result, fake, meter


def test_the_request_carries_the_system_prompt_and_the_image(tmp_path: Path) -> None:
    _, fake, _ = _classify_call(tmp_path)
    sent = fake.calls[0]

    assert "never assessed from a photograph" in sent["system"]
    blocks = sent["messages"][0]["content"]
    assert blocks[0]["type"] == "image"
    assert blocks[0]["source"]["media_type"] == "image/jpeg"
    assert blocks[0]["source"]["data"]
    assert blocks[-1]["type"] == "text"


def test_structured_output_is_forced_rather_than_requested(tmp_path: Path) -> None:
    """A prompt that asks nicely for JSON gets JSON most of the time."""
    _, fake, _ = _classify_call(tmp_path)
    sent = fake.calls[0]

    assert sent["tool_choice"] == {"type": "tool", "name": "report_observations"}
    assert sent["tools"][0]["input_schema"] == vision.CLASSIFY_SCHEMA


def test_usage_is_recorded_against_the_meter(tmp_path: Path) -> None:
    _, _, meter = _classify_call(tmp_path)
    assert meter.input_tokens == 1200
    assert meter.output_tokens == 300
    assert meter.images_analyzed == 1
    # Priced, not free: this is the first path in the codebase that costs money.
    assert meter.usd_total > 0


def test_the_response_records_which_prompt_produced_it(tmp_path: Path) -> None:
    result, _, _ = _classify_call(tmp_path)
    assert result["_prompt_ref"] == prompts.load("vision", "classify").ref
    assert result["_model"] == "claude-sonnet-5"


def test_a_live_response_is_cached_for_the_next_run(tmp_path: Path) -> None:
    _classify_call(tmp_path)
    assert (tmp_path / "vision.classify.photo_02.json").is_file()


def test_no_banned_language_reaches_the_model(tmp_path: Path) -> None:
    """LIABILITY section 5, checked on the wire rather than in the source.

    A banned phrase in a prompt does not reach the buyer directly. It teaches the
    model to write it back, and then it arrives carrying a confidence score.
    """
    client, fake, _ = _client(tmp_path, {"findings": []})
    system_prompt = prompts.system("vision").text

    for pass_name in vision.PASS_FINDING_TYPES:
        prompt = prompts.load("vision", pass_name)
        client.call(
            engine="vision",
            task=pass_name,
            subject="photo_01",
            prompt=prompt.text,
            system=system_prompt,
            schema=vision.findings_schema(pass_name),
            image_paths=[FIXTURE_MEDIA / "photo_01.jpg"],
            prompt_ref=prompt.ref,
        )

    for sent in fake.calls:
        outgoing = sent["system"] + "\n"
        outgoing += "\n".join(
            block["text"] for block in sent["messages"][0]["content"] if block["type"] == "text"
        )
        outgoing += "\n" + sent["tools"][0]["description"]
        violations = scan_text(outgoing, path="<wire>")
        assert not violations, "banned language on the wire:\n" + "\n".join(
            str(v) for v in violations
        )


def test_the_model_is_never_asked_for_a_repair_cost(tmp_path: Path) -> None:
    """D-024. There is no source behind a cost band the model invents, and a
    dollar figure is the line a buyer acts on."""
    for pass_name in vision.PASS_FINDING_TYPES:
        schema = vision.findings_schema(pass_name)
        item = schema["properties"]["findings"]["items"]
        assert "estimated_cost_usd" not in item["properties"]
        assert "cost" not in str(item["properties"]).lower()


def test_each_pass_may_only_emit_its_own_finding_types(tmp_path: Path) -> None:
    """A rust pass returning a dash lamp has misunderstood the question, and the
    cheapest place to refuse that is the tool boundary."""
    rust = vision.findings_schema("rust")
    allowed = rust["properties"]["findings"]["items"]["properties"]["type"]["enum"]
    assert allowed == ["rust_corrosion"]


def test_the_schema_still_permits_a_locked_system(tmp_path: Path) -> None:
    """D-005. The model must stay able to report fluid behind a wheel.

    Blocking locked systems here would suppress the warning as well as the
    all-clear. The clamp downstream is what tells those two apart.
    """
    schema = vision.findings_schema("engine_bay")
    systems = schema["properties"]["findings"]["items"]["properties"]["system"]["enum"]
    assert "brakes" in systems
    assert "structure" in systems


def test_a_client_error_is_not_retried(tmp_path: Path) -> None:
    """Retrying a 400 spends money slower without changing the outcome."""
    anthropic = pytest.importorskip("anthropic")
    error = anthropic.APIStatusError("bad request", response=_FakeResponse(400), body=None)
    client, fake, _ = _client(tmp_path, {"findings": []}, raise_first=error)

    with pytest.raises(anthropic.APIStatusError):
        client.call(
            engine="vision",
            task="rust",
            subject="photo_01",
            prompt="x",
            schema=vision.findings_schema("rust"),
        )
    assert len(fake.calls) == 1


def test_a_rate_limit_is_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    anthropic = pytest.importorskip("anthropic")
    monkeypatch.setattr("tirekick_engines.client.time.sleep", lambda _: None)
    error = anthropic.APIStatusError("slow down", response=_FakeResponse(429), body=None)
    client, fake, _ = _client(tmp_path, {"findings": []}, raise_first=error)

    result = client.call(
        engine="vision",
        task="rust",
        subject="photo_01",
        prompt="x",
        schema=vision.findings_schema("rust"),
    )
    assert result["findings"] == []
    assert len(fake.calls) == 2


def test_live_mode_refuses_a_call_with_no_schema(tmp_path: Path) -> None:
    client, _, _ = _client(tmp_path, {})
    with pytest.raises(LiveModeUnavailable, match="no output schema"):
        client.call(engine="vision", task="rust", subject="photo_01", prompt="x")


def test_images_are_downscaled_to_the_documented_limit() -> None:
    data, media_type, width, height = encode_image(FIXTURE_MEDIA / "photo_01.jpg")
    assert max(width, height) <= 1568
    assert media_type == "image/jpeg"
    assert data


def test_image_tokens_follow_the_published_formula() -> None:
    assert image_tokens(1000, 750) == 1000
    assert image_tokens(1568, 1568) == round(1568 * 1568 / 750)


class _FakeResponse:
    """Minimal stand-in for an httpx response inside an APIStatusError."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self.request = None
