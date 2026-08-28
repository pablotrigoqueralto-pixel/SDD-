"""Stable machine codes derived from human names (brands, loss reasons)."""

import re
import unicodedata

DIGIT_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}


def slugify_code(name: str) -> str:
    """Lower-case snake_case ASCII code: accents stripped, leading digits spelled out.

    "Cook Medical" -> "cook_medical"; "3Gen" -> "three_gen"; "Cambio de proveedor"
    -> "cambio_de_proveedor". Two names differing only in punctuation or case map to the
    same code, which the unique constraint reports as a duplicate.
    """
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    tokens = [token for token in re.split(r"[^a-z0-9]+", ascii_name.lower()) if token]
    if not tokens:
        msg = "A code cannot be derived from an empty name"
        raise ValueError(msg)
    first = tokens[0]
    leading_digits = re.match(r"^\d+", first)
    if leading_digits:
        digits = leading_digits.group(0)
        rest = first[len(digits) :]
        words = [DIGIT_WORDS[digit] for digit in digits]
        tokens = [*words, *([rest] if rest else []), *tokens[1:]]
    return "_".join(tokens)
