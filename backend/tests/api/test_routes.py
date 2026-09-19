"""Smoke tests: every route answers and matches its response model."""

from __future__ import annotations


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_sample_profile(client):
    response = client.get("/profile/sample")
    assert response.status_code == 200
    assert response.json()["cashflow"]["monthly_contribution"] == 15_000


def test_analyze_portfolio(client):
    profile = client.get("/profile/sample").json()
    response = client.post("/portfolio/analyze", json=profile)
    assert response.status_code == 200
    assert response.json()["total_value"] > 0


def test_run_scenario(client):
    profile = client.get("/profile/sample").json()
    response = client.post(
        "/scenario/run",
        json={
            "profile": profile,
            "scenario_type": "market_stress",
            "horizon_months": 60,
            "market_stress": {"shock_pct": -0.3, "shock_at_month": 0},
            "settings": {"n_paths": 200, "seed": 42},
        },
    )
    assert response.status_code == 200
    assert len(response.json()["terminal_percentiles"]) == 5


def test_agent_ask_routes_to_scenario_tool(client):
    profile = client.get("/profile/sample").json()
    response = client.post(
        "/agent/ask",
        json={"question": "What happens if markets fall 30%?", "profile": profile},
    )
    assert response.status_code == 200
    assert response.json()["tool_calls"][0]["tool"] == "run_scenario"
