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
    """Within the tolerance, not to the pixel.

    The fixture photos are 1600px, which is 2% over the limit. Resampling them
    to 1568 costs a full-quality pass over two million pixels and saves about 4%
    of the image tokens, so RESIZE_TOLERANCE deliberately leaves them alone.
    """
    from tirekick_engines.client import MAX_IMAGE_EDGE, RESIZE_TOLERANCE

    data, media_type, width, height = encode_image(FIXTURE_MEDIA / "photo_01.jpg")
    assert max(width, height) <= MAX_IMAGE_EDGE * RESIZE_TOLERANCE
    assert media_type == "image/jpeg"
    assert data

    # Anything genuinely oversized is still brought down to the limit exactly.
    from PIL import Image

    big = Path("/tmp") / "tirekick-oversize-probe.jpg"
    Image.new("RGB", (3000, 2000), (60, 60, 60)).save(big, quality=85)
    try:
        _, _, w, h = encode_image(big)
        assert max(w, h) == MAX_IMAGE_EDGE
    finally:
        big.unlink(missing_ok=True)


def test_image_tokens_follow_the_published_formula() -> None:
    assert image_tokens(1000, 750) == 1000
    assert image_tokens(1568, 1568) == round(1568 * 1568 / 750)


class _FakeResponse:
    """Minimal stand-in for an httpx response inside an APIStatusError."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self.request = None


def test_the_live_path_does_not_need_the_sdk_to_be_importable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LAW 7, as a regression test.

    An earlier version of `_send` imported `anthropic` at the top of the retry
    loop. That runs even when the client is a test double, so this whole file
    passed on a laptop where the `live` extra happens to be installed, and every
    test in it failed in CI, where it deliberately is not.

    Simulating absence rather than trusting the environment is the point: the
    machine writing this code is the one machine that cannot reproduce the bug.
    """
    import sys

    from tirekick_engines.client import _retryable_errors

    monkeypatch.setitem(sys.modules, "anthropic", None)
    _retryable_errors.cache_clear()
    try:
        assert _retryable_errors() == ()
    finally:
        _retryable_errors.cache_clear()


def test_the_whole_send_loop_runs_with_the_sdk_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fixture-mode promise, end to end: no key, no extra, still works."""
    import sys

    from tirekick_engines.client import _retryable_errors

    monkeypatch.setitem(sys.modules, "anthropic", None)
    _retryable_errors.cache_clear()
    try:
        result, _, _ = _classify_call(tmp_path)
        assert result["view_class"] == "exterior_front"
    finally:
        _retryable_errors.cache_clear()


def test_a_large_photo_is_decoded_at_reduced_resolution(tmp_path: Path) -> None:
    """Pixels decoded, not wall clock.

    A phone photo is 12 megapixels and we send 1.8. Letting libjpeg do the first
    reduction in the DCT domain means decoding a quarter of the pixels; the
    naive version decodes all twelve million and then throws most away.

    Asserted as a pixel count because it is deterministic. Timings on this
    hardware are not - a 2000x2000 matmul takes six seconds here, and the
    drafted decode has measured *slower* than the full one purely on noise.
    """
    from PIL import Image

    from tirekick_engines.client import _target_size

    photo = tmp_path / "big.jpg"
    Image.new("RGB", (4032, 3024), (90, 110, 130)).save(photo, quality=90)

    target = _target_size((4032, 3024), 1568)
    assert target == (1568, 1176)

    with Image.open(photo) as image:
        image.draft("RGB", target)
        decoded = image.size

    assert decoded == (2016, 1512), "libjpeg should decode at half scale"
    assert decoded[0] * decoded[1] < 4032 * 3024 / 3


def test_the_draft_target_must_be_the_real_box_not_a_square() -> None:
    """The bug this replaced, pinned so it cannot come back.

    Pillow picks its DCT scale with integer division on both axes and takes the
    minimum. Passing a square (1568, 1568) for a 4032x3024 photo computes
    min(4032//1568, 3024//1568) = min(2, 1) = 1 - no reduction, silently.
    """
    from PIL import Image

    from tirekick_engines.client import _target_size

    photo = Path("/tmp") / "tirekick-draft-probe.jpg"
    Image.new("RGB", (4032, 3024), (10, 20, 30)).save(photo, quality=85)
    try:
        with Image.open(photo) as square:
            square.draft("RGB", (1568, 1568))
            assert square.size == (4032, 3024), "a square target scales nothing"

        with Image.open(photo) as box:
            box.draft("RGB", _target_size((4032, 3024), 1568))
            assert box.size == (2016, 1512)
    finally:
        photo.unlink(missing_ok=True)


def test_an_image_already_within_the_limit_is_not_resampled() -> None:
    """Shrinking 1600px to 1568px resamples two million pixels to save 4% of the
    tokens. The tolerance exists so that trade is not made."""
    from tirekick_engines.client import _target_size

    assert _target_size((1600, 1200), 1568) is None
    assert _target_size((1568, 1176), 1568) is None
    assert _target_size((2400, 1800), 1568) == (1568, 1176)


def test_the_same_photo_is_encoded_once_per_report() -> None:
    """An exterior photo goes to the classifier and three stage-2 passes.

    Without the cache that is four full decodes of the same bytes, and a report
    does twenty-two image calls over eight photographs.
    """
    from tirekick_engines.client import _encoded, encode_image

    _encoded.cache_clear()
    photo = FIXTURE_MEDIA / "photo_01.jpg"
    for _ in range(4):
        encode_image(photo)

    info = _encoded.cache_info()
    assert info.misses == 1
    assert info.hits == 3
