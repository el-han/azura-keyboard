"""Build the keyboard parts with build123d and export them to `things/b3d/`.

Run with `uv run python -m dactyl_lynx_keyboard.b3d` for both halves (see `HALVES`) and a file with both side by side;
name one or more halves (e.g. `right`) to build only those.
"""
import copy
import sys
from os import makedirs
from os.path import abspath, dirname, join

from build123d import Color, Compound, Pos, export_step

from .assembly import HALVES, KeyboardAssembly

GAP = 40
"Distance between the two halves' cases in the file with both (mm)"


def build(assembly: KeyboardAssembly) -> dict[str, Compound]:
    """The printed parts and the files for checking them, by file name suffix."""
    case = assembly.case()
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

    def not_printed():
        """Only for checking fit and collisions. Assemblies store each model once."""
        models = [
            Compound(label="keycaps", children=assembly.keycap_models()),
            Compound(label="keyswitches", children=assembly.switch_models()),
            Compound(label="PCBs", children=assembly.pcb_models()),
        ]
        if assembly.with_trackball:
            ball = assembly.trackball_ball()
            ball.label, ball.color = "trackball", Color(0.5, 0.05, 0.05)
            models += [assembly.sensor_model(), ball]
        return models

    parts["switches"] = Compound(label="switches", children=not_printed())
    parts["combined-with-switches"] = Compound(
        label="combined-with-switches", children=[copy.copy(parts[name]) for name in printed] + not_printed()
    )
    return parts


if __name__ == "__main__":
    out_dir = join(dirname(dirname(dirname(abspath(__file__)))), "things", "b3d")
    makedirs(out_dir, exist_ok=True)

    def write(part: Compound, name: str):
        path = join(out_dir, f"dactyl-lynx-6x5-{name}")
        print(f"Writing {path}.step . . .")
        export_step(part, f"{path}.step")

    sides = sys.argv[1:] or list(HALVES)
    halves = {}
    for side in sides:
        parts = build(KeyboardAssembly(**HALVES[side]))
        for name, part in parts.items():
            write(part, f"{side}-{name}")
        halves[side] = parts

    if set(halves) == {"left", "right"}:
        # Side by side, GAP apart: the right half's case reaches furthest toward -X, the left's toward +X.
        right_min_x = halves["right"]["combined"].bounding_box().min.X
        left_max_x = halves["left"]["combined"].bounding_box().max.X
        right = Pos(GAP / 2 - right_min_x, 0, 0) * halves["right"]["combined-with-switches"]
        left = Pos(-GAP / 2 - left_max_x, 0, 0) * halves["left"]["combined-with-switches"]
        right.label, left.label = "right half", "left half"
        write(Compound(label="both halves", children=[left, right]), "both")
