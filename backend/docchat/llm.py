"""LLM interface. The default implementation is a free local model via Ollama.
To use another provider later, implement the same three methods."""

from collections.abc import Iterator
from typing import Protocol

import ollama

from .config import settings


class LLM(Protocol):
    def complete(self, messages: list[dict]) -> str: ...
    def stream(self, messages: list[dict]) -> Iterator[str]: ...
    def health(self) -> tuple[bool, str]: ...


class OllamaLLM:
    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        temperature: float | None = None,
    ) -> None:
        self.model = model or settings.llm_model
        self.temperature = settings.llm_temperature if temperature is None else temperature
        self.client = ollama.Client(host=host or settings.ollama_host)

    def _options(self) -> dict:
        return {"temperature": self.temperature, "num_ctx": 8192}

    def complete(self, messages: list[dict]) -> str:
        res = self.client.chat(model=self.model, messages=messages, options=self._options())
        return res["message"]["content"]

    def stream(self, messages: list[dict]) -> Iterator[str]:
        for part in self.client.chat(
            model=self.model, messages=messages, options=self._options(), stream=True
        ):
            text = part["message"]["content"]
            if text:
                yield text

    def health(self) -> tuple[bool, str]:
        try:
            listed = self.client.list()
        except Exception as exc:  # connection refused etc.
            return False, f"Ollama is not reachable at {settings.ollama_host}: {exc}"
        names = {getattr(m, "model", None) or m["model"] for m in listed["models"]}
        wanted = {self.model, f"{self.model}:latest"}
        if names & wanted:
            return True, f"Ollama OK, model '{self.model}' available"
        return False, f"Model '{self.model}' not pulled. Run: ollama pull {self.model}"


_default: OllamaLLM | None = None


def get_llm() -> OllamaLLM:
    global _default
    if _default is None:
        _default = OllamaLLM()
    return _default
