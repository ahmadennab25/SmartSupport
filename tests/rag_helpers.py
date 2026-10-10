"""Shared helpers for RAG tests: a deterministic fake embedding model (no OpenAI needed).

The fake turns text into a normalised bag-of-words vector, so texts that share words get a high
cosine similarity. Good enough to test the whole pipeline (chunk -> store -> search -> tool).
"""
import math
import re
import zlib
from types import SimpleNamespace as NS

from apps.knowledge.models import EMBEDDING_DIMENSIONS


def fake_vector(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for word in re.findall(r"\w+", text.lower()):
        vector[zlib.crc32(word.encode("utf-8")) % EMBEDDING_DIMENSIONS] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class FakeEmbeddingClient:
    def __init__(self, fail_with: Exception | None = None):
        self.calls: list[list[str]] = []
        self._fail_with = fail_with
        self.embeddings = NS(create=self._create)

    def _create(self, model, input, **kwargs):
        if self._fail_with:
            raise self._fail_with
        self.calls.append(list(input))
        data = [NS(index=i, embedding=fake_vector(text)) for i, text in enumerate(input)]
        return NS(data=list(reversed(data)))  # reversed on purpose: the service must sort by index


SAMPLE_DOCS = {
    "returns.en.md": "# Returns\n\n## Window\nYou can return an unopened item within 14 days for a full refund.\n",
    "shipping.en.md": "# Shipping\n\n## Courier\nDelivery by courier takes two days and every parcel has a tracking number.\n",
    "payment.en.md": "# Payment\n\n## Methods\nPay by card or cash on delivery.\n",
    "returns.ar.md": "# سياسة الاسترجاع\n\n## المدة\nيمكنك الاسترجاع خلال أربعة عشر يوماً من الاستلام.\n",
}


def write_docs(directory, docs=None):
    from pathlib import Path

    for name, text in (docs or SAMPLE_DOCS).items():
        (Path(directory) / name).write_text(text, encoding="utf-8")
