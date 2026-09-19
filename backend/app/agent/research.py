"""Retrieval + evidence tracking — OWNER: Member 4.

A claim without a source does not ship. Every passage returned here carries
its file, section and provenance line so the UI can show where it came from.

Retrieval is TF-IDF over the section-sized passages in knowledge/. That is
lexical, not semantic: it matches words, not meaning. It is honest about that
by returning nothing below a relevance floor rather than the least-bad match.
Swapping in embeddings later only means replacing `_Index`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.schemas.common import Evidence

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

# Below this cosine similarity a passage is not returned at all.
MIN_RELEVANCE = 0.12


@dataclass(frozen=True)
class Passage:
    file: str
    heading: str
    text: str
    provenance: str

    @property
    def source(self) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", self.heading.lower()).strip("-")
        return f"knowledge/{self.file}#{slug} ({self.provenance})"


def load_passages(directory: Path = KNOWLEDGE_DIR) -> list[Passage]:
    """One passage per '## ' section. The first 'source:' line is the provenance."""
    passages = []
    for path in sorted(directory.glob("*.md")):
        if path.name == "README.md":
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        provenance = "FinTwin knowledge note"
        if lines and lines[0].lower().startswith("source:"):
            provenance = lines[0].split(":", 1)[1].strip()
        heading, body = None, []
        for line in [*lines, "## "]:
            if line.startswith("## "):
                if heading and "".join(body).strip():
                    passages.append(Passage(path.name, heading, " ".join(body).strip(), provenance))
                heading, body = line[3:].strip(), []
            elif heading is not None and line.strip():
                body.append(line.strip())
    return passages


class _Index:
    def __init__(self, passages: list[Passage]) -> None:
        self.passages = passages
        self.vectorizer = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), sublinear_tf=True
        )
        documents = [f"{p.heading}. {p.heading}. {p.text}" for p in passages]
        self.matrix = self.vectorizer.fit_transform(documents)

    def search(self, query: str, k: int) -> list[tuple[Passage, float]]:
        scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix)[0]
        ranked = sorted(zip(self.passages, scores, strict=True), key=lambda ps: -ps[1])
        return [(p, float(s)) for p, s in ranked[:k] if s >= MIN_RELEVANCE]


@lru_cache
def _index() -> _Index:
    return _Index(load_passages())


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]


def research(query: str, k: int = 3) -> list[Evidence]:
    """Sourced passages relevant to `query`, most relevant first. May be empty."""
    if not query.strip():
        return []
    now = datetime.now(UTC)
    return [
        Evidence(
            claim=_first_sentence(passage.text),
            source=passage.source,
            snippet=passage.text,
            retrieved_at=now,
            confidence=round(score, 3),
        )
        for passage, score in _index().search(query, k)
    ]
