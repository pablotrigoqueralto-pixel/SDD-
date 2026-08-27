import pytest

from app.domain.territories.entities import Territory
from app.domain.territories.errors import InvalidProvinceError, TerritoryInUseError


def test_create_trims_name_and_keeps_valid_provinces() -> None:
    territory = Territory.create(name="  Centro ", provinces=frozenset({"28", "45", "19"}))

    assert territory.name == "Centro"
    assert territory.provinces == frozenset({"28", "45", "19"})
    assert territory.is_active


def test_create_rejects_invalid_province_codes() -> None:
    with pytest.raises(InvalidProvinceError) as exc_info:
        Territory.create(name="Centro", provinces=frozenset({"28", "99", "8"}))

    error = exc_info.value.errors[0]
    assert error["field"] == "provinces"
    assert error["code"] == "invalid_province"
    assert "8, 99" in error["message"]


def test_set_provinces_validates() -> None:
    territory = Territory.create(name="Centro", provinces=frozenset({"28"}))

    with pytest.raises(InvalidProvinceError):
        territory.set_provinces(frozenset({"53"}))


def test_deactivate_with_active_users_raises_territory_in_use() -> None:
    territory = Territory.create(name="Centro", provinces=frozenset({"28"}))

    with pytest.raises(TerritoryInUseError) as exc_info:
        territory.deactivate(active_user_count=3)

    assert exc_info.value.active_user_count == 3
    assert exc_info.value.code == "territory_in_use"


def test_deactivate_without_users_succeeds() -> None:
    territory = Territory.create(name="Centro", provinces=frozenset({"28"}))

    territory.deactivate(active_user_count=0)

    assert territory.is_active is False
