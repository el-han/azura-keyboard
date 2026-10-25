"""Build the keyboard parts with build123d and export them to `things/b3d/`.

Run with `uv run python -m dactyl_lynx_keyboard.b3d`; add `--no-trackball` for the half without a trackball.
"""
import copy
import sys
from os import makedirs
from os.path import abspath, dirname, join

from build123d import Color, Compound, export_step

from .assembly import KeyboardAssembly

if __name__ == "__main__":
    out_dir = join(dirname(dirname(dirname(abspath(__file__)))), "things", "b3d")
    makedirs(out_dir, exist_ok=True)

    with_trackball = "--no-trackball" not in sys.argv[1:]
    assembly = KeyboardAssembly(with_trackball=with_trackball)
    variant = "right" if with_trackball else "right-no-trackball"
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
        if with_trackball:
            ball = assembly.trackball_ball()
            ball.label, ball.color = "trackball", Color(0.5, 0.05, 0.05)
            models += [assembly.sensor_model(), ball]
        return models

    parts["switches"] = Compound(label="switches", children=not_printed())
    parts["combined-with-switches"] = Compound(
        label="combined-with-switches", children=[copy.copy(parts[name]) for name in printed] + not_printed()
    )

    for name, part in parts.items():
        path = join(out_dir, f"dactyl-lynx-6x5-{variant}-{name}")
        print(f"Writing {path}.step . . .")
        export_step(part, f"{path}.step")
