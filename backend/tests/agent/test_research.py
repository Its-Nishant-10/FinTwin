"""OWNER: Member 4."""

from __future__ import annotations

from app.agent import research


def test_every_knowledge_passage_has_provenance():
    passages = research.load_passages()
    assert len(passages) >= 15
    assert all(p.provenance and p.provenance != "FinTwin knowledge note" for p in passages)


def test_relevant_query_returns_sourced_evidence():
    evidence = research.research("what is rupee cost averaging")
    assert evidence[0].source.startswith("knowledge/sip.md#rupee-cost-averaging")
    assert evidence[0].snippet and evidence[0].confidence > research.MIN_RELEVANCE


def test_unrelated_query_returns_nothing_rather_than_a_weak_match():
    assert research.research("quantum chromodynamics lattice gauge theory") == []


def test_empty_query_returns_nothing():
    assert research.research("   ") == []
