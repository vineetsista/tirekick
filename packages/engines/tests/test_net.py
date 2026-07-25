"""LAW 3 - the outbound allowlist."""

from __future__ import annotations

import pytest

from tirekick_engines.net import ALLOWED_HOSTS, ScrapeLawViolation, assert_allowed


def test_federal_apis_are_allowed() -> None:
    assert_allowed("https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/TEST")
    assert_allowed("https://api.nhtsa.gov/recalls/recallsByVehicle?make=x")


@pytest.mark.parametrize(
    "url",
    [
        "https://www.craigslist.org/search/cta",
        "https://www.cargurus.com/Cars/listing",
        "https://www.autotrader.com/cars-for-sale",
        "https://www.facebook.com/marketplace/category/vehicles",
        "https://www.carmax.com/cars",
    ],
)
def test_marketplaces_are_refused_by_name(url: str) -> None:
    with pytest.raises(ScrapeLawViolation, match="marketplace"):
        assert_allowed(url)


def test_unknown_hosts_are_refused() -> None:
    with pytest.raises(ScrapeLawViolation, match="ALLOWED_HOSTS"):
        assert_allowed("https://example.com/anything")


def test_the_allowlist_stays_small() -> None:
    """A growing allowlist is how LAW 3 would erode. Changing this is deliberate."""
    assert frozenset({"vpic.nhtsa.dot.gov", "api.nhtsa.gov"}) == ALLOWED_HOSTS
