"""Measure retrieval and answer quality.

1. Upload your test PDFs through the app (or `python cli.py ingest file.pdf`).
2. Copy evals/dataset.example.json to evals/dataset.json and write 30-50 questions.
3. Run from the backend folder:

    python -m evals.run_evals                 # retrieval + answers + LLM judge
    python -m evals.run_evals --retrieval-only

Retrieval metrics compare three configurations so the README can show what each
technique buys you: dense only, hybrid (dense + BM25), hybrid + rerank.
"""

import argparse
import json
from pathlib import Path

from docchat.config import settings
from docchat.llm import get_llm
from docchat.prompts import NOT_FOUND_TOKEN, format_sources, judge_messages
from docchat.rag import answer
from docchat.retriever import retrieve

HERE = Path(__file__).parent
CONFIGS = {
    "dense": {"use_bm25": False, "use_reranker": False},
    "hybrid": {"use_bm25": True, "use_reranker": False},
    "hybrid+rerank": {"use_bm25": True, "use_reranker": True},
}


def is_hit(chunk: dict, case: dict) -> bool:
    return chunk["filename"] == case["filename"] and chunk["page_start"] <= case["page"] <= chunk["page_end"]


def retrieval_metrics(cases: list[dict], k: int) -> dict[str, dict]:
    answerable = [c for c in cases if c.get("filename")]
    results = {}
    for name, cfg in CONFIGS.items():
        hits, rr = 0, 0.0
        for case in answerable:
            chunks, _ = retrieve(case["question"], top_k=k, **cfg)
            rank = next((i for i, ch in enumerate(chunks, 1) if is_hit(ch, case)), None)
            hits += rank is not None
            rr += 1 / rank if rank else 0
        n = max(len(answerable), 1)
        results[name] = {"hit@k": hits / n, "mrr": rr / n}
    return results


def answer_metrics(cases: list[dict]) -> dict:
    llm = get_llm()
    correct = faithful = cited_ok = not_found_ok = answerable = unanswerable = 0
    rows = []
    for case in cases:
        result = answer(case["question"])
        if case["expected_answer"] == NOT_FOUND_TOKEN:
            unanswerable += 1
            not_found_ok += result["not_found"]
            rows.append((case["question"], "not found" if result["not_found"] else "ANSWERED"))
            continue
        answerable += 1
        cited = [s for s in result["sources"] if s["cited"]]
        cited_ok += any(is_hit(s, case) for s in cited)
        raw = llm.complete(judge_messages(case["question"], case["expected_answer"],
                                          result["answer"], format_sources(cited)))
        try:
            verdict = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        except ValueError:
            verdict = {"correct": False, "faithful": False, "reason": "unparseable judge output"}
        correct += bool(verdict.get("correct"))
        faithful += bool(verdict.get("faithful"))
        rows.append((case["question"], verdict.get("reason", "")))
    a, u = max(answerable, 1), max(unanswerable, 1)
    return {
        "correct": correct / a,
        "faithful": faithful / a,
        "citation_hits_expected_page": cited_ok / a,
        "not_found_accuracy": not_found_ok / u if unanswerable else None,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(HERE / "dataset.json"))
    parser.add_argument("--k", type=int, default=settings.top_k)
    parser.add_argument("--retrieval-only", action="store_true")
    args = parser.parse_args()

    cases = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    lines = [f"# DocChat eval ({len(cases)} questions, k={args.k}, model={settings.llm_model})", "",
             "## Retrieval", "", "| config | hit@k | MRR |", "|---|---|---|"]
    for name, m in retrieval_metrics(cases, args.k).items():
        lines.append(f"| {name} | {m['hit@k']:.2f} | {m['mrr']:.2f} |")

    if not args.retrieval_only:
        m = answer_metrics(cases)
        lines += ["", "## Answers", "", "| metric | score |", "|---|---|",
                  f"| correct (LLM judge) | {m['correct']:.2f} |",
                  f"| faithful to sources (LLM judge) | {m['faithful']:.2f} |",
                  f"| cites expected page | {m['citation_hits_expected_page']:.2f} |"]
        if m["not_found_accuracy"] is not None:
            lines.append(f"| says 'not found' when it should | {m['not_found_accuracy']:.2f} |")
        lines += ["", "## Per question", ""] + [f"- **{q}**: {r}" for q, r in m["rows"]]

    report = "\n".join(lines)
    print(report)
    (HERE / "results.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
