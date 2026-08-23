from app.services.embeddings import cosine, embed


def test_local_embeddings_are_stable_and_normalized():
    first = embed("Java Spring Boot Docker")
    second = embed("Java Spring Boot Docker")
    assert first == second
    assert cosine(first, second) == 1.0


def test_related_text_scores_above_unrelated_text():
    profile = embed("Python FastAPI backend APIs")
    assert cosine(profile, embed("Python backend FastAPI service")) > cosine(profile, embed("graphic design sales"))
