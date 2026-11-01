"""Measurements of the trackball.
"""


class TrackBall:
    """A trackball and the room it needs to turn."""
    def __init__(self, diameter: float = 34.0):
        self.diameter = diameter
        self.wall_distance = 1.1
        "Gap between the ball and the shell that holds it"
        self.inner_diameter = self.diameter + 2*self.wall_distance
