"""What a manifest may name on disk, and what it may not.

A manifest is user-provided (LAW 3), and the paths inside it are data. The
boundary pinned here: every asset resolves inside the media root, or the run
dies at input time - before anything is opened, hashed, or published into a
report. pathlib makes both escape routes quiet ones: joining an absolute right
operand replaces the root entirely, and `../` walks out of the inspection
directory.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from tirekick_engines.inputs import InspectionInput, image_size, materialize_assets


def _inspection(file: str) -> InspectionInput:
    return InspectionInput.model_validate(
        {
            "id": "t-01",
            "assets": [{"id": "a1", "kind": "document", "file": file}],
        }
    )


def _media_root(tmp_path: Path) -> Path:
    root = tmp_path / "media"
    root.mkdir()
    return root


def test_a_relative_path_inside_the_root_materializes(tmp_path: Path) -> None:
    root = _media_root(tmp_path)
    (root / "title.pdf").write_bytes(b"paperwork")
    assets = materialize_assets(_inspection("title.pdf"), root)
    assert assets[0].path == "title.pdf"
    assert assets[0].bytes == len(b"paperwork")


def test_a_nested_path_that_stays_inside_is_allowed(tmp_path: Path) -> None:
    root = _media_root(tmp_path)
    (root / "docs").mkdir()
    (root / "docs" / "title.pdf").write_bytes(b"x")
    assets = materialize_assets(_inspection("docs/title.pdf"), root)
    assert assets[0].path == "docs/title.pdf"


def test_a_parent_traversal_fails_loudly_at_input_time(tmp_path: Path) -> None:
    """A manifest naming ../report.json must not open, hash, or stat it.

    The file deliberately exists: the failure has to come from the boundary
    check, not from the file happening to be absent.
    """
    root = _media_root(tmp_path)
    (tmp_path / "report.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="media root"):
        materialize_assets(_inspection("../report.json"), root)


def test_an_absolute_path_is_rejected_outright(tmp_path: Path) -> None:
    """`media_root / '/etc/hostname'` is `/etc/hostname` - the join keeps
    nothing of the root. An absolute manifest path is never legitimate."""
    root = _media_root(tmp_path)
    with pytest.raises(ValueError, match="absolute"):
        materialize_assets(_inspection("/etc/hostname"), root)


def _bomb_jpeg() -> bytes:
    """A few-KB JPEG whose header declares 25000x25000 pixels.

    Trivial to craft, exactly what an upload flow will eventually receive, and
    enough to trip Pillow's decompression-bomb guard on the header read alone.
    """
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("L", (8, 8)).save(buffer, format="JPEG")
    data = bytearray(buffer.getvalue())
    marker = data.find(b"\xff\xc0")
    assert marker != -1, "the encoder stopped emitting baseline SOF0"
    # SOF0 layout: marker(2) length(2) precision(1) height(2) width(2).
    data[marker + 5 : marker + 9] = (25000).to_bytes(2, "big") + (25000).to_bytes(2, "big")
    return bytes(data)


def test_a_decompression_bomb_reads_as_no_dimensions(tmp_path: Path) -> None:
    """The docstring promises an asset with no recorded dimensions rather than
    a dead pipeline. Pillow's DecompressionBombError subclasses Exception
    directly - not OSError - so it does not arrive dressed as anything the
    original except clause was written for."""
    bomb = tmp_path / "bomb.jpg"
    bomb.write_bytes(_bomb_jpeg())
    assert image_size(bomb) == (None, None)
