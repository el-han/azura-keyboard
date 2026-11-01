"""Measurements shared by all parts of the case.
"""
from dataclasses import dataclass

from build123d import Face, Part, extrude


@dataclass(frozen=True)
class CaseDimensions:
    plate_thickness: float = 3
    "Thickness of the key plates"
    cavity_depth: float = 12
    "Depth of the case's inside below the key plane (switch pins end 8.3 mm below it)"
    wall: float = 3
    "Thickness of the case's walls and floor"
    clearance: float = 0.5
    "Gap between the case's walls and the PCBs under the switches"
    max_height: float = 120
    "Upper bound for the height of any part (must stay below the far side of the key surface torus)"
    table_z: float = 0
    "Height of the table: the thumb case touches it with the flat strip in its middle"

    def prism(self, face: Face) -> Part:
        """Everything above and below a face in top view."""
        return extrude(face, 2 * self.max_height, both=True)
