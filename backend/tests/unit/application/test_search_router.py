from app.application.search.router import MIN_QUERY_LENGTH, parse_query


class TestMinLength:
    def test_short_queries_are_rejected(self) -> None:
        assert MIN_QUERY_LENGTH == 2
        assert parse_query("") is None
        assert parse_query(" a ") is None

    def test_two_characters_pass(self) -> None:
        parsed = parse_query("ab")
        assert parsed is not None
        assert parsed.text == "ab"


class TestQuoteNumbers:
    def test_full_number(self) -> None:
        parsed = parse_query("P-2026-0003")
        assert parsed is not None
        assert parsed.quote_number == (2026, 3)

    def test_version_suffix_ignored(self) -> None:
        parsed = parse_query("p-2026-0003-v2")
        assert parsed is not None
        assert parsed.quote_number == (2026, 3)

    def test_partial_year_only(self) -> None:
        parsed = parse_query("P-2026")
        assert parsed is not None
        assert parsed.quote_number == (2026, None)

    def test_plain_text_is_not_a_quote(self) -> None:
        parsed = parse_query("Tambre")
        assert parsed is not None
        assert parsed.quote_number is None


class TestEmails:
    def test_at_sign_routes_to_email(self) -> None:
        parsed = parse_query("Ana@Tambre.es")
        assert parsed is not None
        assert parsed.email == "ana@tambre.es"

    def test_no_at_no_email(self) -> None:
        parsed = parse_query("tambre.es")
        assert parsed is not None
        assert parsed.email is None


class TestTaxIds:
    def test_cif_with_separators(self) -> None:
        parsed = parse_query("b-12345678")
        assert parsed is not None
        assert parsed.tax_id == "B12345678"

    def test_nif_shape(self) -> None:
        parsed = parse_query("12345678Z")
        assert parsed is not None
        assert parsed.tax_id == "12345678Z"

    def test_word_is_not_a_tax_id(self) -> None:
        parsed = parse_query("Tambre28")
        assert parsed is not None
        assert parsed.tax_id is None


class TestPhones:
    def test_digits_with_separators(self) -> None:
        parsed = parse_query("612 34 56 78")
        assert parsed is not None
        assert parsed.phone_digits == "612345678"

    def test_international_prefix(self) -> None:
        parsed = parse_query("+34-612.345.678")
        assert parsed is not None
        assert parsed.phone_digits == "34612345678"

    def test_short_numbers_are_not_phones(self) -> None:
        parsed = parse_query("2026")
        assert parsed is not None
        assert parsed.phone_digits is None


class TestTextAlwaysPresent:
    def test_identifier_queries_keep_the_text(self) -> None:
        parsed = parse_query("P-2026-0003")
        assert parsed is not None
        assert parsed.text == "P-2026-0003"
