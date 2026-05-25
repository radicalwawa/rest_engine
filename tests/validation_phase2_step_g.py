"""
Phase 2 Step G — SDM Bookkeeping Validation.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

SDM_PATH = os.path.join(BASE, "sdm.json")

FROZEN_HASHES = {
    "db_manager.py": "66080761d7658cd49f5c2419be331d8b3349ac58856b86fdafa88591a0a3f053",
    "prompt_engine.py": "ef39a6c1df61cf13ec69c5fbd682201930954887e8abf139f3bbffffe5364866",
    "daily_pipeline.py": "de151348ffe2e5503cb3fcd8defdfb1355ccf335af322071f7cd3b9d90688c51",
    "tui.py": "b7c5c48ef101abb5ea5a19b216544f6f68360820283ba1631f26b083bedd038c",
    "sdm_tool.py": "5d0b9bd30d7c42d257cf353b4e1ee13bff26d5295d7086e6cf7e2f114e13a91b",
}

EXPECTED_SCOPES = [
    "phase2_step_a",
    "phase2_step_a2",
    "phase2_step_b_partial",
    "phase2_step_b_continuation",
    "phase2_step_c",
    "phase2_step_d",
    "phase2_step_e",
    "phase2_step_f",
]

passed = 0
failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {label}")
    else:
        failed += 1
        print(f"  FAIL: {label}")


def main():
    with open(SDM_PATH, encoding="utf-8") as f:
        sdm = json.load(f)

    # 1. Mission current
    print("\n[1] Mission current")
    m = sdm["mission"]["current"]
    check("mission.current.id == M6", m["id"] == "M6")
    check("mission.current.status == todo", m["status"] == "todo")

    # 2. Mission queue contains M5 done
    print("\n[2] Mission queue")
    queue = sdm["mission"]["queue"]
    m5_entries = [q for q in queue if q.get("id") == "M5"]
    check("queue contains M5", len(m5_entries) >= 1)
    if m5_entries:
        check("M5 status == done", m5_entries[-1]["status"] == "done")

    # 3. Delta events contain 8 Phase 2 scopes
    print("\n[3] Delta events")
    events = sdm["delta"]["events"]
    event_scopes = [e["scope"] for e in events]
    for scope in EXPECTED_SCOPES:
        check(f"event scope '{scope}' present", scope in event_scopes)

    # All 8 have result PASS
    p2_events = [e for e in events if e["scope"] in EXPECTED_SCOPES]
    check("all 8 Phase 2 events have result PASS",
          all(e["result"] == "PASS" for e in p2_events))

    # 4. Timestamps within last 10 minutes
    print("\n[4] Timestamps")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=10)

    for key in ["updated_at"]:
        ts_str = sdm.get(key, "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            check(f"root {key} recent", ts > cutoff)
        except Exception:
            check(f"root {key} parseable", False)

    for section in ["state", "delta", "mission"]:
        ts_str = sdm[section].get("updated_at", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            check(f"{section}.updated_at recent", ts > cutoff)
        except Exception:
            check(f"{section}.updated_at parseable", False)

    # 5. Invariants
    print("\n[5] Invariants")
    check("no_ui_tui == false",
          sdm["state"]["invariants"]["no_ui_tui"] is False)

    # 6. Contract fingerprint
    print("\n[6] Contract fingerprint")
    fp = sdm["contract"].get("fingerprint", "")
    check("fingerprint is 64-char hex",
          isinstance(fp, str) and len(fp) == 64 and all(c in "0123456789abcdef" for c in fp))

    # 7. Python module hashes
    print("\n[7] Python module hashes")
    for fname, expected in FROZEN_HASHES.items():
        fpath = os.path.join(BASE, fname)
        actual = hashlib.sha256(open(fpath, "rb").read()).hexdigest()
        check(f"{fname} hash unchanged", actual == expected)

    # Result
    total = passed + failed
    print(f"\n{'='*50}")
    print(f"SONUC: {passed}/{total} PASSED")
    if failed > 0:
        print(f"BASARISIZ: {failed} assertion(s)")
    else:
        print("Tum assertion'lar gecti!")
    print(f"{'='*50}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
