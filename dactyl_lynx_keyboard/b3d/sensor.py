"""Optical sensor module under the trackball.

Dimensions are for the "PMW3389 Motion Sensor" breakout by Joe's Sensors and Sundry
(https://www.lectronz.com/products/592: 28 x 21 mm board, two 2-56 screw holes 24 mm apart, LM19-LSI lens included)
and for the sensor/lens stack from the PixArt PMW3389DM datasheet (figure 5 and 7).

All shapes are in the sensor's frame: the navigation surface (the bottom of the ball) is at Z=0, the module hangs
below it with its lens facing up (+Z), and the board's long side runs along X.
"""
from build123d import Box, Color, Compound, Cylinder, Part, Pos

# PixArt PMW3389DM datasheet, figure 5 (mouse orientation flipped upside down)
LENS_FLANGE_TO_SURFACE = 2.40
"Bottom of the lens flange to the navigation surface (Z)"
PCB_TO_SURFACE = 7.40
"Top of the PCB (the chip side) to the navigation surface"
PCB_THICKNESS = 1.60
CHIP_TO_SURFACE = 9.81
"Top of the chip package to the navigation surface"

# PixArt LM19-LSI lens outline (datasheet figure 7)
LENS_LENGTH = 21.15
LENS_WIDTH = 18.85

# The breakout board
BOARD_LENGTH = 28.0
BOARD_WIDTH = 21.0
HOLE_SPACING = 24.0
"Distance between the two screw holes, along the board's long side (assumed centered on the lens)"
SCREW_PILOT_DIAMETER = 1.8
"Pilot hole for 2-56 or M2 screws cut straight into the plastic"

CHIP_LENGTH = 12.0
CHIP_WIDTH = 10.0
"Approximate size of the chip package on the back of the board (for collision checks only)"


def board_face_z() -> float:
    """Height of the board face that points toward the ball (the side the lens sits on)."""
    return -(PCB_TO_SURFACE - PCB_THICKNESS)


def model() -> Compound:
    """The sensor module for collision checks (not printed): board, lens and chip package."""
    board_top = board_face_z()
    pcb = Pos(0, 0, board_top - PCB_THICKNESS / 2) * Box(BOARD_LENGTH, BOARD_WIDTH, PCB_THICKNESS)
    pcb.color = Color(0.0, 0.4, 0.15)
    pcb.label = "board"
    # From the board up to the flange
    lens_height = -LENS_FLANGE_TO_SURFACE - board_top
    lens = Pos(0, 0, board_top + lens_height / 2) * Box(LENS_LENGTH, LENS_WIDTH, lens_height)
    lens.color = Color(0.6, 0.75, 0.9, 0.6)
    lens.label = "lens"
    chip_height = CHIP_TO_SURFACE - PCB_TO_SURFACE
    chip = Pos(0, 0, -PCB_TO_SURFACE - chip_height / 2) * Box(CHIP_LENGTH, CHIP_WIDTH, chip_height)
    chip.color = Color(0.05, 0.05, 0.05)
    chip.label = "chip"
    return Compound(label="sensor", children=[pcb, lens, chip])


def lens_opening(clearance: float = 0.3, depth: float = 20) -> Part:
    """The opening in the well for the lens, from the navigation surface downward."""
    return Pos(0, 0, -depth / 2) * Box(LENS_LENGTH + 2 * clearance, LENS_WIDTH + 2 * clearance, depth)


def standoffs(diameter: float = 5.0, height: float = 12) -> Part:
    """Screw posts reaching up from the board's ball-side face (to be trimmed to the well's outer shell)."""
    z = board_face_z()
    post = Pos(0, 0, z + height / 2) * Cylinder(diameter / 2, height)
    return Pos(-HOLE_SPACING / 2, 0, 0) * post + Pos(HOLE_SPACING / 2, 0, 0) * post


def screw_holes(depth: float = 6) -> Part:
    """Pilot holes for the board's screws, from the board's face into the standoffs."""
    z = board_face_z()
    hole = Pos(0, 0, z + depth / 2) * Cylinder(SCREW_PILOT_DIAMETER / 2, depth)
    return Pos(-HOLE_SPACING / 2, 0, 0) * hole + Pos(HOLE_SPACING / 2, 0, 0) * hole
