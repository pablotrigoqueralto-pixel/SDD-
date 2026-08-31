"""Labelled phone entries shared by accounts and contacts."""

import pytest

from app.domain.accounts.entities import PhoneEntry, normalise_phone_list
from app.domain.accounts.errors import DuplicatePhoneError
from app.domain.shared.errors import ValidationFailedError


class TestCreate:
    def test_normalises_number_to_e164(self) -> None:
        phone = PhoneEntry.create(label="Secretaría", number="915 550 001")

        assert phone.number == "+34915550001"
        assert phone.label == "Secretaría"
        assert phone.extension is None and phone.note is None

    def test_keeps_explicit_country_prefix(self) -> None:
        assert PhoneEntry.create(label="Móvil", number="+351912345678").number == "+351912345678"

    def test_trims_label_and_note(self) -> None:
        phone = PhoneEntry.create(label="  Despacho  ", number="915550003", note="  Solo mañanas ")

        assert phone.label == "Despacho" and phone.note == "Solo mañanas"

    def test_free_label_is_accepted_verbatim(self) -> None:
        assert (
            PhoneEntry.create(label="Planta 3 · box 2", number="915550004").label
            == "Planta 3 · box 2"
        )

    def test_empty_label_is_rejected(self) -> None:
        with pytest.raises(ValidationFailedError):
            PhoneEntry.create(label="   ", number="915550005")

    def test_number_with_extension_text_is_rejected(self) -> None:
        with pytest.raises(ValidationFailedError):
            PhoneEntry.create(label="Centralita", number="915550001 ext 4021")

    def test_extension_must_be_digits(self) -> None:
        with pytest.raises(ValidationFailedError):
            PhoneEntry.create(label="Despacho", number="915550001", extension="4021-A")

    def test_extension_kept_apart_from_the_number(self) -> None:
        phone = PhoneEntry.create(label="Despacho", number="915550001", extension=" 4021 ")

        assert phone.number == "+34915550001" and phone.extension == "4021"


class TestList:
    def test_keeps_order_and_first_is_primary(self) -> None:
        phones = normalise_phone_list(
            [
                PhoneEntry.create(label="Centralita", number="915550000"),
                PhoneEntry.create(label="Secretaría", number="915550001"),
            ]
        )

        assert [p.label for p in phones] == ["Centralita", "Secretaría"]
        assert phones[0].number == "+34915550000"

    def test_rejects_duplicate_label_and_number(self) -> None:
        entry = PhoneEntry.create(label="Centralita", number="915550000")

        with pytest.raises(DuplicatePhoneError):
            normalise_phone_list(
                [entry, PhoneEntry.create(label="Centralita", number="915 55 00 00")]
            )

    def test_same_number_under_a_different_label_is_allowed(self) -> None:
        phones = normalise_phone_list(
            [
                PhoneEntry.create(label="Centralita", number="915550000"),
                PhoneEntry.create(label="Urgencias", number="915550000"),
            ]
        )

        assert len(phones) == 2

    def test_empty_list_is_valid(self) -> None:
        assert normalise_phone_list([]) == []
