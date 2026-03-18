import json, sys, hashlib
from datetime import datetime, timezone

REQUIRED_TOP = ["proto","contract","state","delta","mission","updated_at"]

def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def load(p):
    with open(p,"r",encoding="utf-8-sig") as f:
        return json.load(f)

def save(p, obj):
    with open(p,"w",encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",",":"))
        f.write("\n")

def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def validate(sdm):
    for k in REQUIRED_TOP:
        if k not in sdm:
            raise SystemExit(f"SDM invalid: missing top key '{k}'")
    if sdm["proto"] != "SDM/1":
        raise SystemExit("SDM invalid: proto mismatch")
    # hard guard: roots must exist
    for k in ["contract","state","delta","mission"]:
        if not isinstance(sdm.get(k), dict):
            raise SystemExit(f"SDM invalid: '{k}' must be object")

def touch_all(sdm):
    ts = now()
    sdm["updated_at"] = ts
    sdm["state"]["updated_at"] = ts
    sdm["delta"]["updated_at"] = ts
    sdm["mission"]["updated_at"] = ts
    if sdm["contract"].get("fingerprint") is None:
        sdm["contract"]["fingerprint"] = fingerprint(sdm["contract"]["text"])

def add_event(sdm, scope, files, commit=None, result="PASS", note=None):
    ts = now()
    ev = {
        "ts": ts,
        "commit": commit,
        "scope": scope,
        "files": files,
        "result": result,
        "note": note
    }
    sdm["delta"]["events"].append(ev)
    # enforce window
    mode = sdm["delta"]["window"]["mode"]
    n = int(sdm["delta"]["window"]["n"])
    if mode == "last_n" and len(sdm["delta"]["events"]) > n:
        sdm["delta"]["events"] = sdm["delta"]["events"][-n:]

def set_mission_current(sdm, mid, title, steps, expected_outputs, done_definition):
    sdm["mission"]["current"] = {
        "id": mid,
        "title": title,
        "scope_guard": "single-scope",
        "steps": steps,
        "expected_outputs": expected_outputs,
        "done_definition": done_definition,
        "status": "todo"
    }

def usage():
    print("Usage:")
    print("  python sdm_tool.py touch <sdm.json>")
    print("  python sdm_tool.py event <sdm.json> <scope> <files_csv> [commit] [PASS|FAIL] [note]")
    print("  python sdm_tool.py mission <sdm.json> <id> <title> <steps_pipe> <outputs_pipe> <done_definition>")
    sys.exit(2)

def main():
    if len(sys.argv) < 3: usage()
    cmd, path = sys.argv[1], sys.argv[2]
    sdm = load(path)
    validate(sdm)

    if cmd == "touch":
        touch_all(sdm)
        save(path, sdm)
        return

    if cmd == "event":
        if len(sys.argv) < 5: usage()
        scope = sys.argv[3]
        files = [x for x in sys.argv[4].split(",") if x]
        commit = sys.argv[5] if len(sys.argv) > 5 else None
        result = sys.argv[6] if len(sys.argv) > 6 else "PASS"
        note = sys.argv[7] if len(sys.argv) > 7 else None
        add_event(sdm, scope, files, commit=commit, result=result, note=note)
        touch_all(sdm)
        save(path, sdm)
        return

    if cmd == "mission":
        if len(sys.argv) < 8: usage()
        mid = sys.argv[3]
        title = sys.argv[4]
        steps = [x for x in sys.argv[5].split("|") if x]
        outs = [x for x in sys.argv[6].split("|") if x]
        done = sys.argv[7]
        set_mission_current(sdm, mid, title, steps, outs, done)
        touch_all(sdm)
        save(path, sdm)
        return

    usage()

if __name__ == "__main__":
    main()
