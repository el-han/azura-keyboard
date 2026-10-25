"""Optical sensor module under the trackball: the PMW3610 breakout board from https://github.com/siderakb/pmw3610-pcb.

`resources/sensor/pmw3610_pcb.step` is exported from that KiCad project with a model of the sensor and its lens
added (see `scripts/build_sensor_step.py`).

All shapes are in the sensor's frame: the navigation surface (the bottom of the ball) is at Z=0, the board hangs
below it with its lens facing up (+Z), and the sensor's optical center is on the Z axis.
"""
from functools import cache
from os.path import abspath, dirname, join

from build123d import Box, Compound, Cylinder, Location, Part, Pos, Rot

from .step import import_step_colored, transformed

BOARD_STEP = join(dirname(dirname(dirname(abspath(__file__)))), "resources", "sensor", "pmw3610_pcb.step")

# Positions in the KiCad project (board coordinates; STEP Y = -KiCad Y)
OPTICAL_CENTER_KICAD = (150.0, 100.0)
"The board is laid out with the sensor's optical center in its middle."
MOUNTING_HOLES_KICAD = ((141.25, 87.25), (158.75, 87.25), (141.25, 112.75), (158.75, 112.75))
"Four M3 holes"

# PixArt PMW3610DM-SUDU datasheet, figure 4 (mouse orientation, turned upside down here)
LENS_REFERENCE_TO_SURFACE = 2.40
"Lens reference plane (its lowest plane, facing the ball) to the navigation surface (Z)"
LENS_BELOW_BOARD = 3.40
"From the board's lens side to the lens reference plane"
SCREW_PILOT_DIAMETER = 2.5
"Pilot hole for M3 screws cut straight into the plastic"


def board_face_z() -> float:
    """Height of the board face that points toward the ball (the side the lens sits on)."""
    return -(LENS_REFERENCE_TO_SURFACE + LENS_BELOW_BOARD)


def _from_kicad() -> Location:
    """From the board's STEP frame to the sensor frame: turned over so the lens faces up, optical center at the
    origin, and turned around so the solder pads for the wires face +X (toward the finger well)."""
    x, y = OPTICAL_CENTER_KICAD
    return Pos(0, 0, board_face_z()) * Rot(0, 0, 180) * Rot(180, 0, 0) * Pos(-x, y, 0)


def _hole_positions() -> list[tuple[float, float]]:
    """Mounting hole positions in the sensor frame."""
    positions = [(_from_kicad() * Pos(x, -y, 0)).position for x, y in MOUNTING_HOLES_KICAD]
    return [(p.X, p.Y) for p in positions]


@cache
def _board_step() -> Compound:
    return import_step_colored(BOARD_STEP, label="PMW3610 board")


def model() -> Compound:
    """The sensor board for collision checks (not printed): PCB, components, sensor and lens."""
    return transformed(_board_step(), _from_kicad())


def envelope() -> Compound:
    """A few boxes around the sensor board, for quick collision checks (not printed): the lens (the topmost
    part), the sensor package (the lowest) and everything else.
    """
    children = list(model().children)
    lens = max(children, key=lambda child: child.bounding_box().max.Z)
    package = min(children, key=lambda child: child.bounding_box().min.Z)
    rest = Compound(children=[child for child in children if child is not lens and child is not package])

    def box(shape) -> Part:
        bb = shape.bounding_box()
        return Pos(bb.center()) * Box(*bb.size)

    return Compound(label="PMW3610 board envelope", children=[box(lens), box(package), box(rest)])


def lens_opening(clearance: float = 0.3, depth: float = 20) -> Part:
    """The opening in the well for the lens (the board's topmost part), from the navigation surface downward."""
    lens = max(model().children, key=lambda child: child.bounding_box().max.Z).bounding_box()
    return Pos(lens.center().X, lens.center().Y, -depth / 2) * Box(
        lens.size.X + 2 * clearance, lens.size.Y + 2 * clearance, depth
    )


def hole_radius() -> float:
    """Distance of the mounting holes from the optical center (they are symmetric)."""
    x, y = _hole_positions()[0]
    return (x * x + y * y) ** 0.5


def standoffs(diameter: float = 6.0, height: float = 12) -> Part:
    """Screw posts reaching up from the board's ball-side face (to be trimmed to the well's outer shell)."""
    post = Pos(0, 0, board_face_z() + height / 2) * Cylinder(diameter / 2, height)
    posts = [Pos(x, y, 0) * post for x, y in _hole_positions()]
    return posts[0].fuse(*posts[1:])


def screw_holes(depth: float = 6) -> Part:
    """Pilot holes for the board's screws, from the board's face into the standoffs."""
    hole = Pos(0, 0, board_face_z() + depth / 2) * Cylinder(SCREW_PILOT_DIAMETER / 2, depth)
    holes = [Pos(x, y, 0) * hole for x, y in _hole_positions()]
    return holes[0].fuse(*holes[1:])
