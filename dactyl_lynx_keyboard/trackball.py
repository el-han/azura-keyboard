"""The layout of a thumb well.
"""

from solid2 import hull, sphere, difference, cube, cylinder


class TrackBall():
    """The layout of a thumb well.
    """
    def __init__(self, diameter: float = 34.0):

        self.diameter = diameter
        self.wall_thickness = 3
        self.wall_distance = 1.1

        self.outer_diameter = self.diameter + 2*self.wall_distance + 2*self.wall_thickness
        self.inner_diameter = self.diameter + 2*self.wall_distance

        self.z_offset = self.outer_diameter / 2 + 10 - self.wall_distance - self.wall_thickness

    def trackball(self):
        shape = sphere(d=self.diameter)
        shape = shape.translate((0, 0, self.z_offset))
        return shape

    def trackball_well(self):
        shape = sphere(d=self.outer_diameter)
        hole = sphere(d=self.inner_diameter)
        upper_half = cube((self.outer_diameter, self.outer_diameter, self.outer_diameter), center=True)
        upper_half = upper_half.translate((0, 0, self.outer_diameter/2))

        shape = difference()(shape, hole)
        shape = difference()(shape, upper_half)

        shape = shape.translate((0, 0, self.z_offset))

        case_wall = cylinder(h=self.z_offset, d=self.outer_diameter, center=True)
        case_wall = difference()(case_wall, cylinder(h=self.z_offset+2, d=self.inner_diameter, center=True))
        case_wall = case_wall.translate((0, 0, self.z_offset/2))

        shape = shape + case_wall

        return shape
