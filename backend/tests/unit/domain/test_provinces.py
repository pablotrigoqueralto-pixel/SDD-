from app.domain.territories.provinces import (
    PROVINCE_CODE_PATTERN,
    PROVINCES,
    PROVINCES_BY_CODE,
    is_valid_province_code,
)


def test_there_are_exactly_52_provinces_with_unique_codes() -> None:
    assert len(PROVINCES) == 52
    assert len(PROVINCES_BY_CODE) == 52


def test_every_code_matches_the_ine_pattern_and_is_sequential() -> None:
    codes = [province.code for province in PROVINCES]

    assert codes == [f"{number:02d}" for number in range(1, 53)]
    assert all(PROVINCE_CODE_PATTERN.fullmatch(code) for code in codes)


def test_every_province_has_a_name_and_community() -> None:
    assert all(province.name and province.community for province in PROVINCES)


def test_is_valid_province_code() -> None:
    assert is_valid_province_code("28")
    assert not is_valid_province_code("00")
    assert not is_valid_province_code("53")
    assert not is_valid_province_code("8")
