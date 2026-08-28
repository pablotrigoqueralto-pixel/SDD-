import pytest

from app.domain.reference.codes import slugify_code


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Cook Medical", "cook_medical"),
        ("3Gen", "three_gen"),
        ("Cambio de proveedor", "cambio_de_proveedor"),
        ("Northern  Meditec ", "northern_meditec"),
        ("Fertipro®", "fertipro"),
        ("Neurología - Dolphin/IQ", "neurologia_dolphin_iq"),
        ("10 Med", "one_zero_med"),
    ],
)
def test_slugify_code(name: str, expected: str) -> None:
    assert slugify_code(name) == expected


def test_names_differing_only_in_case_or_punctuation_collide() -> None:
    assert slugify_code("Cook-Medical") == slugify_code("cook medical")


def test_empty_name_rejected() -> None:
    with pytest.raises(ValueError, match="empty name"):
        slugify_code("®®")
