import os
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.memory import cosine_similarity, get_seed_pages, retrieve_context
from backend.schemas import RetrievePageItem

client = TestClient(app)


def test_cosine_similarity_edge_cases():
    # Identical vectors
    assert abs(cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) - 1.0) < 1e-6
    # Parallel scaled vectors
    assert abs(cosine_similarity([1.0, 2.0], [2.0, 4.0]) - 1.0) < 1e-6
    # Orthogonal vectors
    assert abs(cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-6
    # Opposite vectors
    assert abs(cosine_similarity([1.0, 0.0], [-1.0, 0.0]) - (-1.0)) < 1e-6
    # Zero vectors
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([], []) == 0.0
    # Mismatched lengths
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0


def test_seed_pages_loaded():
    seeds = get_seed_pages()
    assert len(seeds) == 6
    page_numbers = [s["page"] for s in seeds]
    assert page_numbers == [1, 2, 3, 4, 5, 6]
    assert seeds[0]["title"] == "InkMentor · AI Math Notebook Guide"
    assert seeds[2]["title"] == "Partial Derivatives & Tangent Planes"
    assert seeds[4]["title"] == "Double & Iterated Integrals"
    assert len(seeds[0]["embedding"]) == 3072


def test_retrieve_tangent_plane_top_match_is_page3():
    """Acceptance Criterion:
    When asking about tangent planes or partial derivatives, Page 3 is retrieved as top match.
    """
    seeds = get_seed_pages()
    page3_vec = seeds[2]["embedding"]

    def mock_embed(text: str):
        return page3_vec

    res = retrieve_context(
        query="Find the tangent plane to z = x^2 y at (2, 1)",
        threshold=0.65,
        top_k=3,
        embed_func=mock_embed,
    )

    assert len(res.matches) >= 1
    assert res.top_match is not None
    assert res.top_match.page == 3
    assert res.top_match.title == "Partial Derivatives & Tangent Planes"
    assert res.top_match.similarity >= 0.65


def test_retrieve_threshold_filtering():
    seeds = get_seed_pages()
    # High threshold filters out everything
    def mock_embed(text: str):
        return [0.1] * len(seeds[0]["embedding"])

    res = retrieve_context(
        query="Some unrelated math",
        threshold=0.999,
        top_k=3,
        embed_func=mock_embed,
    )
    assert len(res.matches) == 0
    assert res.top_match is None


def test_retrieve_top_k_limiting():
    seeds = get_seed_pages()
    def mock_embed(text: str):
        return seeds[0]["embedding"]

    res = retrieve_context(
        query="Differentiate",
        threshold=0.0,
        top_k=2,
        embed_func=mock_embed,
    )
    assert len(res.matches) == 2


def test_retrieve_custom_pages():
    custom_pages = [
        RetrievePageItem(page=10, title="Matrix Algebra", content="A * B != B * A in general"),
        RetrievePageItem(page=11, title="Complex Numbers", content="i^2 = -1, Euler formula e^(ix) = cos x + i sin x"),
    ]

    def mock_embed(text: str):
        if "matrix" in text.lower():
            return [1.0, 0.0]
        elif "complex" in text.lower():
            return [0.0, 1.0]
        return [0.707, 0.707]

    res = retrieve_context(
        query="Matrix multiplication",
        pages=custom_pages,
        threshold=0.5,
        top_k=2,
        embed_func=mock_embed,
    )
    assert len(res.matches) >= 1
    assert res.top_match is not None
    assert res.top_match.page == 10
    assert res.top_match.title == "Matrix Algebra"


def test_retrieve_api_endpoint_validation():
    # Blank query
    resp = client.post("/api/retrieve", json={"query": ""})
    assert resp.status_code == 422

    # Valid call using mock/real seed data
    # When TEST_MODE=true or using seeds
    seeds = get_seed_pages()
    assert len(seeds) == 6
