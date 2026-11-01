"""The single-key PCB under each switch.
"""
from build123d import Box, Color, Pos

PCB_THICKNESS = 1.57
PCB_SIZE = 19
PCB_TOP_BELOW_PLATE = 5.08
"Depth of the PCB's top below the plate's top: an MX switch housing ends 5 mm below the plate."


def single_key_board() -> Box:
    """Simplified single-key PCB (a rectangular prism)."""
    pcb = Pos(0, 0, -(PCB_THICKNESS / 2 + PCB_TOP_BELOW_PLATE)) * Box(PCB_SIZE, PCB_SIZE, PCB_THICKNESS)
    pcb.color = Color(0.0, 0.4, 0.15)
    return pcb
