"""M5 -> done, M6 -> todo. Uses sdm_tool helpers exclusively."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sdm_tool as sd

path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sdm.json")
sdm = sd.load(path)
sd.validate(sdm)

# Close M5
if sdm["mission"]["current"]["id"] != "M5":
    raise SystemExit(f"unexpected current mission: {sdm['mission']['current']['id']}")
sdm["mission"]["current"]["status"] = "done"

# Move closed M5 into queue (history)
closed_m5 = dict(sdm["mission"]["current"])
sdm["mission"]["queue"].append(closed_m5)

# Open M6 placeholder
sd.set_mission_current(
    sdm,
    mid="M6",
    title="Phase 3 — rating-aware prompt evolution (scope TBD)",
    steps=[
        "operator collects rating data via Phase 2 TUI",
        "planning layer reviews rating distribution",
        "design rating-aware prompt_engine extension",
    ],
    expected_outputs=[
        "prompt_engine adaptive mode",
        "tests/validation_phase3.py",
    ],
    done_definition="prompt_engine reads rating history and adjusts variation strategy; validated by operator session",
)

sd.touch_all(sdm)
sd.save(path, sdm)
print("M5 closed, M6 opened, sdm.json saved")
