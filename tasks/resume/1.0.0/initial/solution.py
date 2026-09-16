import json
from pathlib import Path


def resume(root, session, steps, stop_after=None):
    state_file = root / (session + ".json")
    effects_file = root / (session + ".log")
    completed = []
    executed = 0
    for step in steps:
        if step in completed:
            continue
        with effects_file.open("a") as handle:
            handle.write(step + "\n")
        completed.append(step)
        state_file.write_text(json.dumps(completed))
        executed += 1
        if executed == stop_after:
            break
    return completed


def scenario(data):
    root = Path("/tmp/state")
    root.mkdir(exist_ok=True)
    for call in data["calls"]:
        resume(root, call["session"], data["steps"], call.get("stop_after"))
    return {name: (root / (name + ".log")).read_text().splitlines()
            for name in {call["session"] for call in data["calls"]}}
