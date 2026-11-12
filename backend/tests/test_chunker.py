from docchat.chunker import chunk_pages, count_tokens


def make_pages():
    return [
        {"page": 1, "text": "Alpha intro paragraph. " * 30 + "\n\n" + "Second para on page one. " * 20},
        {"page": 2, "text": "Beta content about embeddings and vectors. " * 40},
        {"page": 3, "text": "Gamma final notes. " * 10},
    ]


def test_chunks_respect_token_limit():
    chunks = chunk_pages(make_pages(), chunk_tokens=120, overlap_tokens=20)
    assert len(chunks) > 3
    for c in chunks:
        assert count_tokens(c.text) <= 120 + 5  # joining spaces may add a token or two


def test_page_numbers_are_tracked():
    chunks = chunk_pages(make_pages(), chunk_tokens=120, overlap_tokens=20)
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 3
    for c in chunks:
        assert c.page_start <= c.page_end
    beta_chunks = [c for c in chunks if "Beta content" in c.text]
    assert beta_chunks and all(c.page_start <= 2 <= c.page_end for c in beta_chunks)


def test_overlap_repeats_trailing_text():
    pages = [{"page": 1, "text": " ".join(f"Sentence number {i} is here." for i in range(200))}]
    chunks = chunk_pages(pages, chunk_tokens=100, overlap_tokens=30)
    for prev, nxt in zip(chunks, chunks[1:]):
        last_sentence = prev.text.split(". ")[-1]
        assert last_sentence.rstrip(".") in nxt.text


def test_indexes_are_sequential_and_empty_pages_skipped():
    pages = [{"page": 1, "text": "   \n\n  "}, {"page": 2, "text": "Only real text."}]
    chunks = chunk_pages(pages, chunk_tokens=50, overlap_tokens=10)
    assert [c.index for c in chunks] == [0]
    assert chunks[0].page_start == 2


def test_hyphenated_line_breaks_are_joined():
    chunks = chunk_pages([{"page": 1, "text": "dense embed-\nding vectors"}], 50, 10)
    assert "embedding" in chunks[0].text
