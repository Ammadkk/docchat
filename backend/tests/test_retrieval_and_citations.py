from docchat import citations
from docchat.retriever import reciprocal_rank_fusion


def item(i):
    return {"id": i, "text": f"text {i}"}


def test_rrf_rewards_items_found_by_both_retrievers():
    dense = [item("a"), item("b"), item("c")]
    keyword = [item("c"), item("d")]
    fused = [x["id"] for x in reciprocal_rank_fusion([dense, keyword])]
    assert fused[0] == "c"  # rank 3 + rank 1 beats a single rank 1
    assert set(fused) == {"a", "b", "c", "d"}


def test_rrf_merges_fields_from_both_lists():
    fused = reciprocal_rank_fusion([[{"id": "x", "similarity": 0.8}], [{"id": "x", "bm25": 3.2}]])
    assert fused[0]["similarity"] == 0.8 and fused[0]["bm25"] == 3.2


def test_cited_numbers_in_order_and_in_range():
    answer = "Fact one [2]. Fact two [1][2]. Bogus [9]."
    assert citations.cited_numbers(answer, 3) == [2, 1]


def test_strip_invalid_removes_out_of_range_markers():
    assert citations.strip_invalid("A [1]. B [7].", 3) == "A [1]. B ."


def test_sentences_grouped_by_source():
    grouped = citations.sentences_by_source("Cats purr [1]. Dogs bark [2]. Both are pets [1][2].", 2)
    assert grouped[1] == ["Cats purr .", "Both are pets ."]
    assert grouped[2] == ["Dogs bark .", "Both are pets ."]
