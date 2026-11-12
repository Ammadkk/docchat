NOT_FOUND_TOKEN = "NOT_FOUND"
NOT_FOUND_MESSAGE = "I couldn't find that in your documents."

ANSWER_SYSTEM = f"""You are DocChat, an assistant that answers questions using ONLY the numbered sources the user provides.

Rules:
- Use only facts stated in the sources. Never use outside knowledge.
- After every sentence that states a fact, cite the supporting source number in square brackets, e.g. [2]. Use [1][3] for multiple sources.
- Only cite numbers that appear in the sources list.
- If the sources do not contain the answer, reply with exactly: {NOT_FOUND_TOKEN}
- Be concise. Use Markdown: short paragraphs or bullet lists."""


def format_sources(chunks: list[dict]) -> str:
    blocks = []
    for n, c in enumerate(chunks, start=1):
        pages = (
            f"p. {c['page_start']}"
            if c["page_start"] == c["page_end"]
            else f"pp. {c['page_start']}-{c['page_end']}"
        )
        blocks.append(f"[{n}] ({c['filename']}, {pages})\n{c['text']}")
    return "\n\n".join(blocks)


def answer_messages(question: str, chunks: list[dict]) -> list[dict]:
    user = (
        f"Sources:\n\n{format_sources(chunks)}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the sources above, with [n] citations:"
    )
    return [
        {"role": "system", "content": ANSWER_SYSTEM},
        {"role": "user", "content": user},
    ]


REWRITE_SYSTEM = """Rewrite the user's latest question so it can be understood without the conversation.
Resolve pronouns and references ("it", "that section", "the second one") using the conversation.
If it is already standalone, return it unchanged. Output ONLY the rewritten question, nothing else."""


def rewrite_messages(question: str, history: list[dict]) -> list[dict]:
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    return [
        {"role": "system", "content": REWRITE_SYSTEM},
        {
            "role": "user",
            "content": f"Conversation:\n{convo}\n\nLatest question: {question}\n\nRewritten question:",
        },
    ]


JUDGE_SYSTEM = """You grade answers from a document Q&A system. Reply with a JSON object only:
{"correct": true|false, "faithful": true|false, "reason": "<one sentence>"}
- correct: the answer conveys the same key facts as the expected answer.
- faithful: every claim in the answer is supported by the provided sources."""


def judge_messages(question: str, expected: str, answer: str, sources: str) -> list[dict]:
    return [
        {"role": "system", "content": JUDGE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\nExpected answer: {expected}\n\n"
                f"System answer: {answer}\n\nSources:\n{sources}"
            ),
        },
    ]
