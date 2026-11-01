"""Build the keyboard parts with build123d and export them to `things/`.

Run with `uv run python -m azura_keyboard` for both halves (see `HALVES`) and a file with both side by side;
name one or more halves (e.g. `right`) to build only those.
"""
import copy
import sys
from pathlib import Path

from build123d import Color, Compound, Pos, export_step

from .assembly import HALVES
from .case.keyboard import Keyboard

GAP = 40
"Distance between the two halves' cases in the file with both (mm)"


def not_printed(keyboard: Keyboard) -> list[Compound]:
    """Only for checking fit and collisions. Assemblies store each model once."""
    models = [
        Compound(label="keycaps", children=keyboard.keycap_models()),
        Compound(label="keyswitches", children=keyboard.switch_models()),
        Compound(label="PCBs", children=keyboard.pcb_models()),
    ]
    if keyboard.with_trackball:
        ball = keyboard.trackball_ball()
        ball.label, ball.color = "trackball", Color(0.5, 0.05, 0.05)
        models += [keyboard.sensor_model(), ball]
    return models


def build(keyboard: Keyboard) -> dict[str, Compound]:
    """The printed parts and the files for checking them, by file name suffix."""
    case = keyboard.case()
    # file name: (part, label, color); two shades of slate blue for the printed parts
    printed = {
        "top": (case["top"], "case top", Color(0.36, 0.47, 0.60)),
        "bottom": (case["bottom"], "case bottom", Color(0.24, 0.33, 0.45)),
    }
    parts = {}
    for name, (part, label, color) in printed.items():
        part.label, part.color = label, color
        parts[name] = part
    parts["combined"] = Compound(label="combined", children=[copy.copy(part) for part in parts.values()])
    parts["switches"] = Compound(label="switches", children=not_printed(keyboard))
    parts["combined-with-switches"] = Compound(
        label="combined-with-switches",
        children=[copy.copy(parts[name]) for name in printed] + not_printed(keyboard),
    )
    return parts


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parents[1] / "things"
    out_dir.mkdir(parents=True, exist_ok=True)

    def write(part: Compound, name: str):
        path = out_dir / f"azura-6x5-{name}.step"
        print(f"Writing {path} . . .")
        export_step(part, path)

    sides = sys.argv[1:] or list(HALVES)
    halves = {}
    for side in sides:
        keyboard = HALVES[side]
        parts = build(keyboard)
        for name, part in parts.items():
            write(part, f"{side}-{name}")
        halves[side] = (keyboard, parts)

    if set(halves) == {"left", "right"}:
        # Side by side, GAP apart: the right half's case reaches furthest toward -X, the left's toward +X.
        shifts = {
            "right": GAP / 2 - halves["right"][1]["combined"].bounding_box().min.X,
            "left": -GAP / 2 - halves["left"][1]["combined"].bounding_box().max.X,
        }
        both = []
        for side, (keyboard, parts) in halves.items():
            # The models are placed there key by key: moving them afterwards would store each instance anew (and
            # takes OCCT's STEP writer more memory than there is for the switches).
            keyboard.offset = Pos(shifts[side], 0, 0)
            case = [Pos(shifts[side], 0, 0) * parts[name] for name in ("top", "bottom")]
            for moved, part in zip(case, (parts["top"], parts["bottom"])):
                moved.label, moved.color = part.label, part.color
            both.append(Compound(label=f"{side} half", children=case + not_printed(keyboard)))
        write(Compound(label="both halves", children=both), "both")
