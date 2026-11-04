"""All measurements of the case, with their defaults. To change one: `Keyboard(dimensions=Dimensions(wall=4))`.
"""
from dataclasses import dataclass

from build123d import Face, Part, extrude


@dataclass(frozen=True)
class Dimensions:
    # All of the case
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
    join_margin: float = 15
    "How far past the finger case the thumb case's bottom half is joined to the top (see `Keyboard.case()`)"

    # Finger case
    finger_placement: tuple[float, float, float] = (0, 0, 12.05)
    "Where the finger keys are placed: low enough that the finger case's bottom half rests on the table"

    # Thumb case
    thumb_passage: tuple[float, float] = (12, 5)
    "Width and height of the passage for the thumb keys' wires"

    # Trackball case
    trackball_position: tuple[float, float, float] = (-76.5, -25, 31)
    "Center of the ball: as close to the finger case as the PCB under finger c0 r3 allows"
    bearing_pocket: tuple[float, float] = (7.5, 4)
    "Diameter and depth of the pockets for the ball transfer units (QB310 7.5) that hold the ball"
    bearing_tilt: float = 60
    "Angle of the bearings' axes from the vertical (degrees)"
    bearing_azimuths: tuple[float, ...] = (90, 210, 330)
    "Directions of the bearings around the ball in top view (degrees from +X), clear of the sensor's screw posts"
    trackball_passage: tuple[float, float] = (12, 5)
    "Width and height of the passage for the sensor's wires (one per pin of its 7-pin header)"
    trackball_screw_inset: float = 17.5
    "How far from the ball's axis the screw in the cup's floor sits, toward -X"

    # Skirt
    skirt_inset: float = 10
    "How far the skirt stays inside the outline of the finger case's underside"

    # Screws
    finger_screw_corners: tuple[tuple[float, float], ...] = ((-0.5, -0.75), (5.5, -0.75), (2.5, 4.75), (5.5, 4.75))
    "Corners of the finger case's outline (column, row) with a screw"
    screw_hole: float = 2.9
    "Diameter of the screws' clearance holes"
    screw_head: tuple[float, float] = (5.0, 2.6)
    "Diameter and depth of the counterbores for the screw heads (DIN 912: 4.5 × 2.5 mm)"
    insert_hole: tuple[float, float] = (3.5, 5)
    "Diameter and depth of the holes for the heat-set inserts"
    screw_boss: float = 7
    "Diameter of the bosses around the screws and inserts"
    screw_margin: float = 1.5
    "Smallest thickness of the case's outside around a boss"

    def prism(self, face: Face) -> Part:
        """Everything above and below a face in top view."""
        return extrude(face, 2 * self.max_height, both=True)
