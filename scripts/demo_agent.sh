#!/usr/bin/env bash
# Demo: admin login + conversational question (no MCMC) + design command (MCMC).
# Requires backend on http://localhost:8000 (see PROGRESS.md).
# IMPORTANT: restart uvicorn after code changes so this hits the latest agent.py.
set -euo pipefail
API="${PROTEUS_API:-http://localhost:8000/api/v1}"

echo "=== 1) Login (admin@proteus.dev) ==="
TOK_JSON=$(curl -sS -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@proteus.dev","password":"password123"}')
ACCESS=$(echo "$TOK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Got access token (${#ACCESS} chars)."

PATIENT='{"full_name":"Demo","age":55,"cancer_type":"EGFRvIII","cancer_stage":"IV","tumor_markers":"EGFRvIII","previous_treatments":"","brain_metastasis":false,"notes":"","modality":""}'

echo ""
echo "=== 2) Agent: conversational question (expect text-only reply, no round_complete) ==="
Q_BODY=$(python3 - <<PY
import json
patient = {
  "full_name": "Demo", "age": 55, "cancer_type": "EGFRvIII", "cancer_stage": "IV",
  "tumor_markers": "EGFRvIII", "previous_treatments": "", "brain_metastasis": False,
  "notes": "", "modality": "",
}
print(json.dumps({"patient": patient, "message": "how does this treatment work?"}))
PY
)
curl -sS -X POST "$API/agent/design" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS" \
  -d "$Q_BODY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
msgs = d.get('messages', [])
roles = [m['role'] for m in msgs]
statuses = [m.get('data',{}).get('status') for m in msgs if m.get('data')]
print('roles:', roles)
print('data.status values:', [s for s in statuses if s])
bad = [s for s in statuses if s in ('running','round_complete','complete')]
print('MCMC-like statuses present:', bool(bad))
print('last agent preview:', msgs[-1]['content'][:220].replace(chr(10),' ') if msgs else '')
if bad:
    raise SystemExit('FAIL: expected no MCMC for conversational question')
print('OK: conversational path')
"

echo ""
echo "=== 3) Agent: explicit design (expect MCMC / rounds) ==="
D_BODY=$(python3 - <<PY
import json
patient = {
  "full_name": "Demo", "age": 55, "cancer_type": "EGFRvIII", "cancer_stage": "IV",
  "tumor_markers": "EGFRvIII", "previous_treatments": "", "brain_metastasis": False,
  "notes": "", "modality": "",
}
print(json.dumps({"patient": patient, "message": "design a peptide"}))
PY
)
curl -sS -X POST "$API/agent/design" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS" \
  -d "$D_BODY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
msgs = d.get('messages', [])
statuses = [m.get('data',{}).get('status') for m in msgs if m.get('data')]
print('data.status sample:', statuses[:8], '... total', len(statuses))
if 'round_complete' not in statuses and 'complete' not in statuses:
    raise SystemExit('FAIL: expected MCMC for design command')
print('OK: design path')
"

echo ""
echo "Done. Open http://localhost:5173/agent — log in as admin@proteus.dev / password123"
