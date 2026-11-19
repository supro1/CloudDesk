import pytest

from rag.embeddings import FakeEmbeddings


def test_fake_embeddings_are_deterministic_normalized_and_configurable() -> None:
    embeddings = FakeEmbeddings(dimensions=64)

    first = embeddings.embed_query("Login fails for a team")
    repeated = embeddings.embed_query("Login fails for a team")

    assert first == repeated
    assert len(first) == 64
    assert sum(value * value for value in first) == pytest.approx(1.0)
    assert embeddings.embed_documents(["Login fails for a team"])[0] == first


def test_fake_embeddings_return_zero_vector_for_empty_text() -> None:
    assert FakeEmbeddings(dimensions=4).embed_query(" !!! ") == [0.0] * 4


def test_fake_embeddings_reject_non_positive_dimensions() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        FakeEmbeddings(dimensions=0)
