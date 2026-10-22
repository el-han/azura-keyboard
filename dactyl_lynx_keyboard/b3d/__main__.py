"""Build the keyboard parts with build123d and export them to `things/b3d/`.

Run with `poetry run python -m dactyl_lynx_keyboard.b3d`.
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
    parts = {
        "finger": assembly.finger_part(),
        "thumb": assembly.thumb_part(),
        "trackball": assembly.trackball_part(),
    }
    labels = {"finger": "finger well", "thumb": "thumb well", "trackball": "trackball well"}
    # Three shades of slate blue for the printed parts
    colors = {"finger": Color(0.24, 0.33, 0.45), "thumb": Color(0.36, 0.47, 0.60), "trackball": Color(0.55, 0.64, 0.74)}
    for name, part in parts.items():
        part.label = labels[name]
        part.color = colors[name]
    parts["combined"] = Compound(label="combined", children=[copy.copy(part) for part in parts.values()])
    # Not printed: only for checking fit and collisions (switches, keycaps, PCBs, the ball). Assemblies store each model once.
    def not_printed():
        ball = assembly.trackball_ball()
        ball.label = "trackball"
        ball.color = Color(0.5, 0.05, 0.05)
        return [
            Compound(label="keycaps", children=assembly.keycap_models()),
            Compound(label="keyswitches", children=assembly.switch_models()),
            Compound(label="PCBs", children=assembly.pcb_models()),
            ball,
        ]

    printed = [copy.copy(parts[name]) for name in ("finger", "thumb", "trackball")]
    parts["switches"] = Compound(label="switches", children=not_printed())
    parts["combined-with-switches"] = Compound(label="combined-with-switches", children=printed + not_printed())

    for name, part in parts.items():
        path = join(out_dir, f"dactyl-lynx-6x5-right-{name}")
        print(f"Writing {path}.step . . .")
        export_step(part, f"{path}.step")
