"""Citation contract type + Copy.editorial_citations field."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from desk.publish import Citation, Copy


_NOW = datetime(2026, 5, 19, 10, 0, 0, tzinfo=timezone.utc)


def test_minimal_citation_only_needs_outlet_url_quote():
    c = Citation(outlet="BBC", url="https://bbc/x", quote="A sentence.")
    assert c.outlet == "BBC"
    assert c.quote_original is None
    assert c.quote_lang is None
    assert c.published_at is None


def test_translated_citation_carries_original_and_lang():
    c = Citation(
        outlet="Olé", url="https://ole/x",
        quote="Players were in good spirits at training.",
        quote_original="Los jugadores estaban de buen humor en el entrenamiento.",
        quote_lang="es",
        published_at=_NOW,
    )
    assert c.quote_lang == "es"
    assert c.quote_original.startswith("Los jugadores")


def test_citation_rejects_extra_fields():
    with pytest.raises(ValidationError):
        Citation(outlet="x", url="https://x", quote="y", confidence=0.9)


def test_citation_rejects_empty_quote():
    with pytest.raises(ValidationError):
        Citation(outlet="x", url="https://x", quote="")


def test_copy_editorial_citations_defaults_empty():
    c = Copy()
    assert c.editorial_citations == []


def test_copy_carries_editorial_citations():
    c = Copy(editorial_citations=[
        Citation(outlet="BBC", url="https://bbc/x", quote="A sentence."),
    ])
    assert len(c.editorial_citations) == 1
    assert c.editorial_citations[0].outlet == "BBC"


def test_copy_caps_editorial_citations_length():
    too_many = [
        Citation(outlet=f"o{i}", url=f"https://o{i}/x", quote="q")
        for i in range(11)
    ]
    with pytest.raises(ValidationError):
        Copy(editorial_citations=too_many)


def test_copy_legacy_string_citations_still_work():
    # Backwards compatibility: the legacy URL-only field is untouched.
    c = Copy(citations=["https://a/x", "https://b/y"])
    assert c.citations == ["https://a/x", "https://b/y"]
    assert c.editorial_citations == []
