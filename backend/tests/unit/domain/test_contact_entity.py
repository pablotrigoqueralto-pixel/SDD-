from datetime import UTC, datetime

import pytest

from app.domain.accounts.entities import PhoneEntry
from app.domain.accounts.errors import InvalidPhoneError
from app.domain.contacts.entities import (
    ConsentRecord,
    ConsentSource,
    ConsentStatus,
    Contact,
    PreferredChannel,
)
from app.domain.contacts.errors import (
    ConsentIncompleteError,
    ContactAnonymisedError,
    PreferredChannelMissingValueError,
)
from app.domain.reference.entities import JobTitle
from app.domain.shared.ids import new_id

ACCOUNT_ID = new_id()
NOW = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)


def test_minimum_contact() -> None:
    contact = Contact.create(account_id=ACCOUNT_ID, first_name=" Ana ", last_name="Pérez")

    assert contact.full_name == "Ana Pérez"
    assert contact.consent == ConsentRecord()
    assert contact.consent.status is ConsentStatus.UNKNOWN
    assert contact.is_primary is False
    assert contact.is_active is True
    assert not contact.is_anonymised


def test_details_are_normalised() -> None:
    contact = Contact.create(
        account_id=ACCOUNT_ID,
        first_name="Ana",
        last_name="Pérez",
        details={
            "email": "Ana@Clinica.ES",
            "phones": [PhoneEntry.create(label="Móvil", number="612 345 678")],
            "preferred_channel": "phone",
            "notes": "  ",
        },
    )

    assert contact.email == "ana@clinica.es"
    assert [p.number for p in contact.phones] == ["+34612345678"]
    assert contact.preferred_channel is PreferredChannel.PHONE
    assert contact.notes is None

    with pytest.raises(InvalidPhoneError) as info:
        contact.update_details({"phones": [PhoneEntry.create(label="Fijo", number="abc")]})
    assert info.value.errors[0]["field"] == "phones"


def test_preferred_channel_requires_its_value() -> None:
    with pytest.raises(PreferredChannelMissingValueError) as info:
        Contact.create(
            account_id=ACCOUNT_ID,
            first_name="Ana",
            last_name="Pérez",
            details={"preferred_channel": "email"},
        )

    assert info.value.errors[0]["code"] == "preferred_channel_missing_value"


def test_consent_requires_date_and_source_when_known() -> None:
    with pytest.raises(ConsentIncompleteError):
        ConsentRecord(status=ConsentStatus.GRANTED, at=NOW)

    recorder = new_id()
    consent = ConsentRecord(
        status=ConsentStatus.GRANTED, at=NOW, source=ConsentSource.VERBAL, recorded_by=recorder
    )
    contact = Contact.create(account_id=ACCOUNT_ID, first_name="A", last_name="B")
    contact.record_consent(consent)

    assert contact.consent.recorded_by == recorder
    assert contact.consent.as_dict()["status"] is ConsentStatus.GRANTED


def test_primary_flag() -> None:
    contact = Contact.create(account_id=ACCOUNT_ID, first_name="A", last_name="B")
    contact.make_primary()
    assert contact.is_primary
    contact.demote()
    assert not contact.is_primary


def test_anonymise_clears_personal_data_and_freezes_the_contact() -> None:
    contact = Contact.create(
        account_id=ACCOUNT_ID,
        first_name="Ana",
        last_name="Pérez",
        details={
            "email": "ana@x.es",
            "phones": [PhoneEntry.create(label="Móvil", number="612345678")],
            "notes": "VIP",
        },
        is_primary=True,
        consent=ConsentRecord(ConsentStatus.GRANTED, NOW, ConsentSource.EMAIL, new_id()),
    )

    cleared = contact.anonymise(now=NOW)

    assert cleared == ["first_name", "last_name", "email", "phones", "notes"]
    assert contact.first_name == "Contacto"
    assert contact.last_name == "anonimizado"
    assert contact.email is None and contact.phones == [] and contact.notes is None
    assert contact.is_primary is False
    assert contact.is_active is False
    assert contact.consent.status is ConsentStatus.DENIED
    assert contact.anonymised_at == NOW

    with pytest.raises(ContactAnonymisedError):
        contact.update_details({"first_name": "Otra"})
    with pytest.raises(ContactAnonymisedError):
        contact.anonymise(now=NOW)


def test_job_title_derives_code_and_toggles() -> None:
    title = JobTitle.create(name=" Farmacia hospitalaria ", sort_order=120)

    assert title.code == "farmacia_hospitalaria"
    assert title.name_es == "Farmacia hospitalaria"
    title.rename("Farmacia")
    title.deactivate()
    assert (title.name_es, title.is_active) == ("Farmacia", False)
    title.activate()
    assert title.is_active
