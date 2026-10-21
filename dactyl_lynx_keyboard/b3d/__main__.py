"""Build the keyboard parts with build123d and export them to `things/b3d/`.

Run with `poetry run python -m dactyl_lynx_keyboard.b3d`.
"""
from os import makedirs
from os.path import abspath, dirname, join

from build123d import export_step, export_stl

from .assembly import KeyboardAssembly

if __name__ == "__main__":
    out_dir = join(dirname(dirname(dirname(abspath(__file__)))), "things", "b3d")
    makedirs(out_dir, exist_ok=True)

    assembly = KeyboardAssembly()
    parts = {
        "switch-plates": assembly.switch_plates(),
        "finger": assembly.finger_part(),
        "thumb": assembly.thumb_part(),
    }

    for name, part in parts.items():
        path = join(out_dir, f"dactyl-lynx-6x5-right-{name}")
        print(f"Writing {path}.stl/.step . . .")
        export_stl(part, f"{path}.stl")
        export_step(part, f"{path}.step")
