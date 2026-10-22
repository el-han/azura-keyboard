"""Measurements of the trackball and its well.
"""


class TrackBall:
    """A trackball and the spherical well that holds it."""
    def __init__(self, diameter: float = 34.0):
        self.diameter = diameter
        self.wall_thickness = 3
        self.wall_distance = 1.1

        self.outer_diameter = self.diameter + 2*self.wall_distance + 2*self.wall_thickness
        self.inner_diameter = self.diameter + 2*self.wall_distance

        self.z_offset = self.outer_diameter / 2 + 10 - self.wall_distance - self.wall_thickness
        "Height of the ball's center above the well's origin"
