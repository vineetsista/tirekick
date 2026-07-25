"""Coverage - what the media actually showed us.

LIABILITY section 9: the realistic way this product hurts someone is false
reassurance by omission. A report built on six photos of the good side must say so,
next to the verdict, in the same type size. Coverage is computed before conclusions
and rendered before them.
"""

from __future__ import annotations

from .models import Asset, Coverage, ViewClass

#: The views a complete capture provides. From the capture guide (P5).
REQUESTED_VIEWS: tuple[ViewClass, ...] = (
    "exterior_front",
    "exterior_rear",
    "exterior_side_left",
    "exterior_side_right",
    "exterior_three_quarter",
    "interior_front",
    "interior_rear",
    "engine_bay",
    "odometer",
    "dash",
    "tire",
    "vin_plate",
)


def compute_coverage(assets: list[Asset]) -> Coverage:
    received = {a.view_class for a in assets if a.view_class is not None}
    received_ordered = [v for v in REQUESTED_VIEWS if v in received]
    missing = [v for v in REQUESTED_VIEWS if v not in received]

    photo_count = sum(1 for a in assets if a.kind == "photo")
    has_video = any(a.kind == "video" for a in assets)
    has_audio = any(a.kind == "audio" for a in assets)

    score = round(len(received_ordered) / len(REQUESTED_VIEWS), 2)

    if missing:
        missing_text = ", ".join(m.replace("_", " ") for m in missing)
        statement = (
            f"{photo_count} photos covering {len(received_ordered)} of "
            f"{len(REQUESTED_VIEWS)} standard views. Not covered: {missing_text}. "
            f"Nothing in this report describes what those views would have shown."
        )
    else:
        statement = (
            f"{photo_count} photos covering all {len(REQUESTED_VIEWS)} standard "
            f"views. Full coverage of the standard views is not the same as full "
            f"coverage of the vehicle - the underside, the interior of any "
            f"assembly, and anything requiring a lift remain unassessed."
        )

    return Coverage(
        requested_views=list(REQUESTED_VIEWS),
        received_views=received_ordered,
        missing_views=missing,
        photo_count=photo_count,
        has_video=has_video,
        has_audio=has_audio,
        score=score,
        statement=statement,
    )
