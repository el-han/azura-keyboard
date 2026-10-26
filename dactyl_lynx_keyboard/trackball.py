"""Measurements of the trackball and its well.
"""


class TrackBall:
    """A trackball and the spherical well that holds it."""
    def __init__(self, diameter: float = 34.0):
        self.diameter = diameter
        self.wall_distance = 1.1
        "Gap between the ball and the well"
        self.inner_diameter = self.diameter + 2*self.wall_distance
