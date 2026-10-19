"""Check the actual launch interpreter without opening devices or capturing screens."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from supervision_environment import availability, bootstrap


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    bootstrap()
    state = availability()
    print(f"Python {state['pythonVersion']}\n{state['interpreter']}")
    print(state["cameraReason"] or "[OK] 摄像头识别组件就绪")
    print(state["screenReason"] or "[OK] 屏幕识别组件就绪")
    if not (state["camera"] and state["screen"]):
        print(state["repairHint"])
        print(state["repairCommand"])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
