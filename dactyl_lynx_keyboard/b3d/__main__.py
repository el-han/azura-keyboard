"""Build the keyboard parts with build123d and export them to `things/b3d/`.

Run with `uv run python -m dactyl_lynx_keyboard.b3d`.
"""
import copy
from os import makedirs
from os.path import abspath, dirname, join

from build123d import Color, Compound, export_step

from .assembly import KeyboardAssembly

if __name__ == "__main__":
    out_dir = join(dirname(dirname(dirname(abspath(__file__)))), "things", "b3d")
    makedirs(out_dir, exist_ok=True)

    assembly = KeyboardAssembly()
    case = assembly.case()
    # file name: (part, label, color); shades of slate blue for the printed parts
    printed = {
        "finger-top": (case["finger top"], "finger well top", Color(0.36, 0.47, 0.60)),
        "finger-bottom": (case["finger bottom"], "finger well bottom", Color(0.24, 0.33, 0.45)),
        "thumb-top": (case["thumb top"], "thumb well top", Color(0.45, 0.56, 0.68)),
        "thumb-bottom": (case["thumb bottom"], "thumb well bottom", Color(0.30, 0.40, 0.52)),
        "trackball": (assembly.trackball_part(), "trackball well", Color(0.55, 0.64, 0.74)),
    }
    parts = {}
    for name, (part, label, color) in printed.items():
        part.label, part.color = label, color
        parts[name] = part
    parts["combined"] = Compound(label="combined", children=[copy.copy(part) for part in parts.values()])

    def not_printed():
        """Only for checking fit and collisions. Assemblies store each model once."""
        ball = assembly.trackball_ball()
        ball.label, ball.color = "trackball", Color(0.5, 0.05, 0.05)
        return [
            Compound(label="keycaps", children=assembly.keycap_models()),
            Compound(label="keyswitches", children=assembly.switch_models()),
            Compound(label="PCBs", children=assembly.pcb_models()),
            assembly.sensor_model(),
            ball,
        ]

    parts["switches"] = Compound(label="switches", children=not_printed())
    parts["combined-with-switches"] = Compound(
        label="combined-with-switches", children=[copy.copy(parts[name]) for name in printed] + not_printed()
    )

    for name, part in parts.items():
        path = join(out_dir, f"dactyl-lynx-6x5-right-{name}")
        print(f"Writing {path}.step . . .")
        export_step(part, f"{path}.step")
