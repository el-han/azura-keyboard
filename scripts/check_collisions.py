"""Check the exported printed parts for collisions with the parts that are not printed.

Checks switches, keycaps (at rest and pressed), PCBs and the trackball sensor against the printed parts in
`things/b3d/` and the space the ball needs, and switches, keycaps and PCBs against each other.

Run with `uv run python scripts/check_collisions.py [left|right]` (default right) after `uv run python -m
dactyl_lynx_keyboard.b3d`. With `--simple`, switches and the sensor are checked as a few boxes around them, which is
quicker but coarser (and shows no press fits).

An MX switch's housing ribs press into its 14 mm hole by about 1 mm³; those press fits are counted but not listed.
"""
import re
import sys
from itertools import combinations
from os.path import abspath, dirname, join

from build123d import Shape, import_step

ROOT = dirname(dirname(abspath(__file__)))
sys.path.insert(0, ROOT)

from dactyl_lynx_keyboard.b3d.assembly import HALVES, KeyboardAssembly  # noqa: E402

PRINTED = ("top", "bottom")


def overlap(a: Shape, b: Shape, boxes: dict, tol: float = 0.01) -> float:
    """Volume of the intersection of two shapes, skipping the boolean if their bounding boxes don't overlap."""
    (a_min, a_max), (b_min, b_max) = (boxes.setdefault(id(s), _box(s)) for s in (a, b))
    if not all(a_min[i] < b_max[i] - tol and b_min[i] < a_max[i] - tol for i in range(3)):
        return 0
    intersection = a & b
    return intersection.volume if intersection is not None else 0


def _box(shape: Shape):
    box = shape.bounding_box()
    return tuple(box.min), tuple(box.max)


def key_of(shape: Shape) -> str:
    """"finger keycap 1.25u pressed c2 r0" -> "finger c2 r0"."""
    match = re.match(r"(\w+) .* (c\S+ r\S+)$", shape.label)
    return f"{match.group(1)} {match.group(2)}"


if __name__ == "__main__":
    args = sys.argv[1:]
    simple = "--simple" in args
    variant = next((arg for arg in args if arg in HALVES), "right")
    assembly = KeyboardAssembly(**HALVES[variant])
    with_trackball = assembly.with_trackball
    kinds = {
        "switch": assembly.switch_models(simple=simple),
        "keycap": assembly.keycap_models(),
        "keycap pressed": assembly.keycap_models(pressed=True),
        "pcb": assembly.pcb_models(),
    }
    keyed = [(key_of(shape), kind, shape) for kind, shapes in kinds.items() for shape in shapes]
    printed = {
        name: import_step(join(ROOT, "things", "b3d", f"dactyl-lynx-6x5-{variant}-{name}.step")) for name in PRINTED
    }
    obstacles = dict(printed, **({"ball clearance": assembly.trackball_clearance()} if with_trackball else {}))
    boxes: dict = {}

    collisions = press_fits = 0
    for key, kind, shape in keyed:
        for name, part in obstacles.items():
            volume = overlap(shape, part, boxes)
            if volume <= 0.01:
                continue
            if kind == "switch" and name == "top" and abs(volume - 1.0) < 0.02:
                press_fits += 1
                continue
            collisions += 1
            print(f"{key} {kind} ∩ {name}: {volume:.2f} mm³", flush=True)
    if with_trackball:
        sensor = assembly.sensor_model(simple=simple)
        for name, part in obstacles.items():
            volume = overlap(sensor, part, boxes)
            if volume > 0.01:
                collisions += 1
                print(f"sensor ∩ {name}: {volume:.2f} mm³", flush=True)
    for (key_a, kind_a, a), (key_b, kind_b, b) in combinations(keyed, 2):
        if key_a == key_b or {kind_a, kind_b} == {"keycap", "keycap pressed"}:
            continue
        volume = overlap(a, b, boxes)
        if volume > 0.01:
            collisions += 1
            print(f"{key_a} {kind_a} ∩ {key_b} {kind_b}: {volume:.2f} mm³", flush=True)
    print(f"{collisions} collisions, {press_fits} of {len(kinds['switch'])} switches press-fitted")
    sys.exit(1 if collisions else 0)
