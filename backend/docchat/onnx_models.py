"""Torch-free model runtime: Hugging Face ONNX exports + onnxruntime + tokenizers.

Why: PyTorch is a ~2 GB dependency, and some locked-down Windows machines (Smart App
Control / WDAC) refuse to load its unsigned DLLs. The BAAI repos ship official ONNX
exports (`onnx/model.onnx`), and onnxruntime is Microsoft-signed, so this works anywhere.

- `OnnxEncoder`      bi-encoder (bge): CLS pooling + L2 normalize (same as sentence-transformers)
- `OnnxCrossEncoder` reranker (bge-reranker): one relevance logit per (query, passage) pair
"""

from __future__ import annotations

import os

import numpy as np

# HF cache falls back to copying files when Windows symlinks aren't allowed; the warning is noise.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

MAX_TOKENS = 512


def _load(repo_id: str):
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer

    model_path = hf_hub_download(repo_id, "onnx/model.onnx")
    tokenizer = Tokenizer.from_file(hf_hub_download(repo_id, "tokenizer.json"))
    tokenizer.enable_truncation(max_length=MAX_TOKENS)
    tokenizer.enable_padding()  # pad to the longest item in each batch

    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])
    return tokenizer, session


class _OnnxModel:
    def __init__(self, repo_id: str):
        self.tokenizer, self.session = _load(repo_id)
        self.input_names = {i.name for i in self.session.get_inputs()}

    def _run(self, encodings) -> np.ndarray:
        feeds = {
            "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
        }
        if "token_type_ids" in self.input_names:
            feeds["token_type_ids"] = np.array([e.type_ids for e in encodings], dtype=np.int64)
        return self.session.run(None, {k: v for k, v in feeds.items() if k in self.input_names})[0]


class OnnxEncoder(_OnnxModel):
    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        out = []
        for i in range(0, len(texts), batch_size):
            hidden = self._run(self.tokenizer.encode_batch(texts[i : i + batch_size]))
            cls = hidden[:, 0]  # bge uses the [CLS] token as the sentence embedding
            out.append(cls / np.linalg.norm(cls, axis=1, keepdims=True).clip(min=1e-12))
        return np.vstack(out) if out else np.zeros((0, 0), dtype=np.float32)


class OnnxCrossEncoder(_OnnxModel):
    def predict(self, pairs: list[tuple[str, str]], batch_size: int = 16) -> np.ndarray:
        scores = []
        for i in range(0, len(pairs), batch_size):
            logits = self._run(self.tokenizer.encode_batch(pairs[i : i + batch_size]))
            scores.append(logits.reshape(len(logits), -1)[:, 0])
        return np.concatenate(scores) if scores else np.zeros(0, dtype=np.float32)
