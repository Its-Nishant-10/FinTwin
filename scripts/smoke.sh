#!/usr/bin/env bash
# End-to-end smoke test against a running backend.
# Usage: make backend   (in another terminal)   then   ./scripts/smoke.sh
set -euo pipefail

BASE="${1:-http://localhost:8000}"

echo "→ health"
curl -sf "$BASE/health" | python3 -m json.tool

echo "→ sample profile"
curl -sf "$BASE/profile/sample" -o /tmp/fintwin_profile.json
python3 -c "import json;p=json.load(open('/tmp/fintwin_profile.json'));print('  holdings:',len(p['holdings']),'| SIP:',p['cashflow']['monthly_contribution'])"

echo "→ portfolio analysis"
curl -sf -X POST "$BASE/portfolio/analyze" -H 'Content-Type: application/json' \
  -d @/tmp/fintwin_profile.json |
  python3 -c "import json,sys;m=json.load(sys.stdin);print('  total:',m['total_value'],'| effective holdings:',round(m['concentration']['effective_holdings'],2))"

echo "→ 30% crash scenario"
python3 - <<'PY' > /tmp/fintwin_scenario.json
import json
profile = json.load(open("/tmp/fintwin_profile.json"))
json.dump({
    "profile": profile,
    "scenario_type": "market_stress",
    "horizon_months": 60,
    "market_stress": {"shock_pct": -0.30, "shock_at_month": 0},
    "settings": {"n_paths": 2000, "seed": 42},
}, open("/tmp/fintwin_scenario.json", "w"))
PY
curl -sf -X POST "$BASE/scenario/run" -H 'Content-Type: application/json' \
  -d @/tmp/fintwin_scenario.json |
  python3 -c "import json,sys;r=json.load(sys.stdin);print('  ',r['label']);[print(f\"   p{p['p']:.0f}: {p['value']:,.0f}\") for p in r['terminal_percentiles']]"

echo "→ agent"
python3 -c "
import json
p = json.load(open('/tmp/fintwin_profile.json'))
json.dump({'question': 'What happens if markets fall 30%?', 'profile': p}, open('/tmp/fintwin_ask.json','w'))
"
curl -sf -X POST "$BASE/agent/ask" -H 'Content-Type: application/json' -d @/tmp/fintwin_ask.json |
  python3 -c "import json,sys;r=json.load(sys.stdin);print('  selected tool:',r['tool_calls'][0]['tool'])"

echo
echo "All smoke checks passed."
