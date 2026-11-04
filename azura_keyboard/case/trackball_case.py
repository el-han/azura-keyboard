"""The trackball's holder: a cup standing on the table with a spherical shell for the ball in its top, enclosing the
sensor.
"""
import copy
import math

from build123d import Box, Cylinder, Location, Part, Plane, Pos, Solid, Sphere, Vector

from ..components import trackball_sensor
from ..components.trackball import TrackBall
from .dimensions import Dimensions
from .screws import Screws


class TrackballCase:
    def __init__(self, trackball: TrackBall, dimensions: Dimensions):
        self.trackball = trackball
        self.dimensions = dimensions

    def center(self) -> Location:
        return Pos(*self.dimensions.trackball_position)

    def sensor_location(self) -> Location:
        """The sensor frame: the bottom of the ball, with the board's long side along X."""
        return self.center() * Pos(0, 0, -self.trackball.diameter / 2)

    def radius(self) -> float:
        """Outer radius of the cup (and the shell): the smallest that leaves the sensor board `clearance` of room
        inside a wall of `wall`, and the ball's clearance a wall of `wall`."""
        d = self.dimensions
        board = trackball_sensor.model().bounding_box()
        reach = max(math.hypot(x, y) for x in (board.min.X, board.max.X) for y in (board.min.Y, board.max.Y))
        return max(reach + d.clearance, self.trackball.inner_diameter / 2) + d.wall

    def shell(self) -> Part:
        """The lower half of a spherical shell around the ball, with an opening for the sensor's lens, screw posts for
        its board and pockets for the ball transfer units the ball rests on. Its outside is flush with the cup below it.
        """
        ball = self.trackball
        inner_radius, outer_radius = ball.inner_diameter / 2, self.radius()
        shell = Sphere(outer_radius) - Sphere(inner_radius)
        lower_half = Pos(0, 0, -outer_radius) * Box(*(2 * outer_radius,) * 3)
        shape = shell & lower_half
        # Room for the sensor board, which the thick shell would reach into
        board = trackball_sensor.model().bounding_box()
        c = self.dimensions.clearance
        face_z = trackball_sensor.board_face_z()
        board_room = Pos(board.center().X, board.center().Y, (face_z + c - outer_radius) / 2) * Box(
            board.size.X + 2 * c, board.size.Y + 2 * c, face_z + c + outer_radius
        )
        shape -= Pos(0, 0, -ball.diameter / 2) * board_room

        # Screw posts from the sensor board up into the middle of the shell wall above the screw holes.
        r = trackball_sensor.hole_radius()
        shell_middle = -(math.sqrt(inner_radius**2 - r**2) + math.sqrt(outer_radius**2 - r**2)) / 2
        post_height = shell_middle + ball.diameter / 2 - face_z
        to_sensor = Pos(0, 0, -ball.diameter / 2)
        shape += to_sensor * trackball_sensor.standoffs(height=post_height)
        shape -= to_sensor * trackball_sensor.lens_opening()
        shape -= to_sensor * trackball_sensor.screw_holes()
        shape -= Sphere(inner_radius)
        # Pockets for the bearings, from the inside of the shell outward, their axes through the ball's center
        diameter, depth = self.dimensions.bearing_pocket
        tilt = math.radians(self.dimensions.bearing_tilt)
        for azimuth in map(math.radians, self.dimensions.bearing_azimuths):
            axis = Vector(math.sin(tilt) * math.cos(azimuth), math.sin(tilt) * math.sin(azimuth), -math.cos(tilt))
            shape -= Solid.make_cylinder(diameter / 2, depth + 1, Plane(origin=axis * (inner_radius - 1), z_dir=axis))
        return self.center() * shape

    def cup(self) -> tuple[Part, Part, Part]:
        """The cup, enclosing the sensor module, as (wall, foot, inside): a cylinder from the shell's equator down to the
        table, flush with the shell's outside, with a flat floor of `wall`. The foot is the floor and the wall's lowest
        bit, so the seam stays clear of the floor's top.
        """
        d = self.dimensions
        center_height = self.center().position.Z - d.table_z
        radius = self.radius()

        def column(r: float, bottom: float, top: float) -> Part:
            """A cylinder between two heights relative to the ball's center."""
            return Pos(0, 0, (bottom + top) / 2) * Cylinder(r, top - bottom)

        inside = column(radius - d.wall, d.wall - center_height, 0)
        seam = 2 * d.wall - center_height
        wall = column(radius, seam, 0) - copy.deepcopy(inside) - Sphere(self.trackball.inner_diameter / 2)
        foot = column(radius, -center_height, seam) - copy.deepcopy(inside)
        return tuple(self.center() * shape for shape in (wall, foot, inside))

    def shaft(self) -> Part:
        """The room above the shell that the rest of the case gives way to, all the way up."""
        center, max_height = self.center().position, self.dimensions.max_height
        return Pos(center.X, center.Y, center.Z + max_height / 2) * Cylinder(
            self.trackball.inner_diameter / 2, max_height
        )

    def passage(self) -> tuple[Part, Part]:
        """The sensor's wires: from the room under the sensor, low enough to pass below the ball's shell, straight
        through the cup's wall into the pocket under the finger case's floor, then up through that floor, below the PCB
        there."""
        d = self.dimensions
        width, height = d.trackball_passage
        center = self.center().position
        wall_x = center.X + self.radius()
        low = d.table_z + d.wall + 0.5
        return (
            Pos(wall_x + 3, center.Y, low + height / 2) * Box(16, width, height),
            Pos(wall_x + 9, center.Y, (low + 21) / 2) * Box(7, width, 21 - low),
        )

    def screws(self) -> list[tuple[Part, Part, Part]]:
        """The cup's screws, one on each side of the sensor."""
        return [self.screw(-1), self.screw(1)]

    def screw(self, side: int = -1) -> tuple[Part, Part, Part]:
        """A screw from below at the cup's -X (side -1) or +X (side 1) edge, between its wall and the sensor, into the
        shell, as (lower part of its boss, upper part, holes). It is vertical, unlike the others: the cup stands on the
        table."""
        d = self.dimensions
        center = self.center().position
        frame = Pos(center.X + side * d.trackball_screw_inset, center.Y, d.table_z)
        split = d.wall + 6
        boss, column = d.screw_boss / 2, Screws.column
        return (
            frame * column(1, split, boss),
            frame * column(split, split + d.insert_hole[1] + 4, boss),
            frame * (
                column(-1, d.screw_head[1], d.screw_head[0] / 2)
                + column(-1, split, d.screw_hole / 2)
                + column(split, split + d.insert_hole[1], d.insert_hole[0] / 2)
            ),
        )
