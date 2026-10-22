"""Assembly of the keyboard parts with build123d.
"""
import copy
import math
from collections.abc import Iterable
from typing import Optional

from build123d import (
    Box, Compound, Cylinder, Face, GeomType, Kind, Location, Part, Plane, Polygon, Pos, Rot, Shape, Solid, Sphere,
    extrude, offset,
)

from ..layouts.finger_well import FingerWellLayout
from ..layouts.keys import Kailh
from ..layouts.layout import Layout
from ..layouts.thumb_well import ThumbWellLayout
from . import keyswitch, sensor, surface
from ..layouts.transform import Transform
from ..trackball import TrackBall
from .placement import key_location, to_location


def _instance(shape: Shape, location: Location) -> Shape:
    """A copy of `shape` at `location`, sharing its geometry; models with children get copies of each child."""
    if shape.children:
        return Compound(label=shape.label, children=[_instance(child, location) for child in shape.children])
    instance = copy.copy(shape)
    instance.location = location * shape.location
    return instance


def place_instances(
    layout: Layout, shape: Shape, name: str, positions: Optional[Iterable[tuple[float, float]]] = None
) -> list[Shape]:
    """Place an instance of `shape` at every key position (or the given ones), sharing its geometry.

    Exported as children of an assembly, the geometry is written to STEP only once. Each instance is labelled
    "<name> c<column> r<row>".
    """
    instances = []
    for (column, row) in layout.generate_positions() if positions is None else positions:
        instance = _instance(shape, key_location(layout, column, row))
        instance.label = f"{name} c{column:g} r{row:g}"
        instances.append(instance)
    return instances


def _convex_hull_2d(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Counter-clockwise convex hull of 2D points (Andrew's monotone chain)."""
    points = sorted(set(points))

    def half(pts):
        chain: list[tuple[float, float]] = []
        for p in pts:
            while len(chain) >= 2 and (
                (chain[-1][0] - chain[-2][0]) * (p[1] - chain[-2][1])
                - (chain[-1][1] - chain[-2][1]) * (p[0] - chain[-2][0])
            ) <= 0:
                chain.pop()
            chain.append(p)
        return chain[:-1]

    return half(points) + half(points[::-1])


def place_all(layout: Layout, shape: Part) -> list[Part]:
    """Place a copy of `shape` at every key position of the layout."""
    return [key_location(layout, column, row) * shape for (column, row) in layout.generate_positions()]


class KeyboardAssembly:
    def __init__(self, columns: int = 6, rows: int = 5):
        k = Kailh()
        self.finger_layout = FingerWellLayout(columns=columns, rows=rows, use_1_5u_keys=False, keyswitch=k)
        self.thumb_layout = ThumbWellLayout(keyswitch=k)
        self.trackball = TrackBall()
        self.trackball_position = (-74, -25, 5)

        self.plate_thickness = self.finger_layout.web_thickness
        self.max_height = 120
        "Upper bound for the height of any part (must stay below the far side of the key surface torus)"
        self.finger_straight_columns = (-0.5,)

        self.cavity_depth = 12
        "Depth of the case's inside below the key plane (switch pins end 8.3 mm below it)"
        self.case_wall = 3
        "Thickness of the case's walls and floor"
        self.case_clearance = 0.5
        "Gap between the case's walls and the PCBs under the switches"
        "Edges of the finger well that should be straight in top view (see `surface.outline()`)"
        "Upper bound for the height of any part (must stay below the far side of the key surface torus)"

    def _surface_face(self, layout: Layout, footprint: Face, depth: float) -> Face:
        """The key surface at `depth` below the key plane, trimmed by a vertical prism over `footprint`."""
        slab = extrude(footprint, self.max_height) & (
            surface.torus(layout, depth=depth + 1) - surface.torus(layout, depth=depth)
        )
        # Drop slivers from where the torus turns over beyond the footprint; keep the key surface itself.
        slab = max(slab.solids(), key=lambda solid: solid.volume)
        minor_radius = layout.row_radius + depth
        return next(
            face for face in slab.faces()
            if face.geom_type == GeomType.TORUS
            and abs(face.geom_adaptor().Torus().MinorRadius() - minor_radius) < 1e-6
        )

    def _thicken_down(self, face: Face, amount: float) -> Solid:
        """Thicken a key surface face by `amount` along its normals, away from the keycaps."""
        solid = Solid.thicken(face, amount)
        upward = Solid.thicken(face, -amount)
        return solid if solid.center().Z < upward.center().Z else upward

    def _case_inner_footprint(self, layout: Layout) -> Face:
        """The inside of the case in top view: the plate outline, grown to hold every key's PCB.

        The PCBs hang below the keys along the surface normals, just like the case walls, so their squares projected
        from the key plane are what has to fit.
        """
        half = keyswitch.PCB_SIZE / 2 + self.case_clearance
        corners = [(sx * half, sy * half, 0) for sx in (-1, 1) for sy in (-1, 1)]
        # Convex hulls give every square the same (counter-clockwise) orientation, so they fuse into one face.
        squares = [
            Polygon(*_convex_hull_2d([layout.key_transform(column, row).apply(c)[:2] for c in corners]), align=None)
            for (column, row) in layout.generate_positions()
        ]
        footprint = surface.outline(layout, straight_columns=self.finger_straight_columns).fuse(*squares).clean()
        # Fill the small notches between neighbouring squares
        smoothing = 3
        return offset(offset(footprint, smoothing, kind=Kind.ARC), -smoothing, kind=Kind.ARC)

    def finger_case(self) -> tuple[Part, Part]:
        """The finger well's case as (top, bottom).

        The top half is the key plate. The bottom half is a copy of it moved down along the surface normals,
        joined to the plate's rim by walls that also run along the normals, so the whole case follows the key
        surface. Screws will go into the rim later.
        """
        layout = self.finger_layout
        k = layout.keyswitch
        inner_footprint = self._case_inner_footprint(layout)
        footprint = offset(inner_footprint, self.case_wall, kind=Kind.ARC)

        # Everything is trimmed on the key plane and then thickened along the surface normals, so all edges follow
        # the normals and the two halves meet flush.
        plate = self._thicken_down(self._surface_face(layout, footprint, 0), self.plate_thickness)
        plate_underside = next(
            face for face in plate.faces()
            if face.geom_type == GeomType.TORUS
            and abs(face.geom_adaptor().Torus().MinorRadius() - (layout.row_radius + self.plate_thickness)) < 1e-6
        )

        top = plate
        top -= place_all(layout, keyswitch.mounting_socket(k, extra_depth=1, extra_height=3))
        top -= place_all(layout, keyswitch.switch(k))
        top -= place_all(layout, keyswitch.single_key_board(extra_spacing=0.02))
        top -= self.trackball_clearance()

        # Below the plate down to the outside of the floor, hollowed out by the space inside the walls. The cavity
        # starts at the key plane, above the plate's underside, so the two never share a face.
        bottom = self._thicken_down(plate_underside, self.cavity_depth + self.case_wall - self.plate_thickness)
        bottom -= self._thicken_down(self._surface_face(layout, inner_footprint, 0), self.cavity_depth)
        bottom -= self.trackball_clearance()
        return top, bottom

    def _thumb_arc(self, center_x: float, start_angle: float, end_angle: float, length: float) -> Part:
        """A plate-thick arc of the thumb well's cylinder, in the layout's base frame.

        Angles are column angles (degrees): 0 is the bottom of the circle, positive angles go toward -X.
        """
        layout = self.thumb_layout
        radius = layout.column_radius
        tube = Pos(center_x, 0, radius) * Rot(90, 0, 0) * (
            Cylinder(radius + self.plate_thickness, length) - Cylinder(radius, length)
        )
        steps = max(2, math.ceil(abs(end_angle - start_angle) / 15))
        far = 3 * radius
        rays = [
            (center_x - far * math.sin(math.radians(a)), radius - far * math.cos(math.radians(a)))
            for a in (start_angle + (end_angle - start_angle) * i / steps for i in range(steps + 1))
        ]
        sector = extrude(Plane.XZ * Polygon((center_x, radius), *rays, align=None), length, both=True)
        return tube & sector

    def thumb_part(self) -> Part:
        """The thumb well: a cylindrical arc of keys, split at the bottom by a flat strip under any wider keys there.
        """
        layout = self.thumb_layout
        k = layout.keyswitch
        length = layout.offset_per_row

        # The arc is split at the bottom of the circle (angle 0) and its halves are moved apart by the flat strip
        # under the keys sitting there (see `ThumbWellLayout.placement_adjust()`). Each half reaches half a key
        # spacing past its outermost key.
        half_step = math.degrees(layout.rad_per_col) / 2
        angles = [layout.key_angle(column, row) for (column, row) in layout.generate_positions()]
        flat = layout.flat_width()
        left_end = max(angles) + half_step  # toward -X
        right_end = min(angles) - half_step  # toward +X

        pieces = []
        if left_end > 0:
            pieces.append(self._thumb_arc(-flat / 2, max(right_end, 0), left_end, length))
        if right_end < 0:
            pieces.append(self._thumb_arc(flat / 2, right_end, min(left_end, 0), length))
        if flat > 0:
            pieces.append(Pos(0, 0, -self.plate_thickness / 2) * Box(flat, length, self.plate_thickness))
        shape = pieces[0].fuse(*pieces[1:]) if len(pieces) > 1 else pieces[0]

        shape = to_location(layout.layout_place(Transform())) * shape

        shape -= place_all(layout, keyswitch.mounting_socket(k, extra_depth=1, extra_height=3))
        shape -= place_all(layout, keyswitch.switch(k))
        shape -= place_all(layout, keyswitch.single_key_board(extra_spacing=0.02))
        return shape

    def _trackball_center(self) -> Location:
        return Pos(*self.trackball_position) * Pos(0, 0, self.trackball.z_offset)

    def _sensor_location(self) -> Location:
        """The sensor frame: the bottom of the ball, with the board's long side along X."""
        return self._trackball_center() * Pos(0, 0, -self.trackball.diameter / 2)

    def trackball_part(self) -> Part:
        """The trackball well: the lower half of a spherical shell around the ball, with an opening for the sensor's
        lens and screw posts for its board (no supporting wall yet).
        """
        ball = self.trackball
        inner_radius, outer_radius = ball.inner_diameter / 2, ball.outer_diameter / 2
        shell = Sphere(outer_radius) - Sphere(inner_radius)
        lower_half = Pos(0, 0, -outer_radius) * Box(*(ball.outer_diameter,) * 3)
        well = shell & lower_half

        # Screw posts from the sensor board up into the middle of the shell wall above the screw holes.
        r = sensor.HOLE_SPACING / 2
        shell_middle = -(math.sqrt(inner_radius**2 - r**2) + math.sqrt(outer_radius**2 - r**2)) / 2
        post_height = shell_middle + ball.diameter / 2 - sensor.board_face_z()
        to_sensor = Pos(0, 0, -ball.diameter / 2)
        well += to_sensor * sensor.standoffs(height=post_height)
        well -= to_sensor * sensor.lens_opening()
        well -= to_sensor * sensor.screw_holes()
        well -= Sphere(inner_radius)
        return self._trackball_center() * well

    def sensor_model(self) -> Compound:
        """The trackball's sensor module, for collision checks (not printed)."""
        model = sensor.model()
        return Compound(
            label="sensor", children=[self._sensor_location() * child for child in model.children]
        )

    def trackball_clearance(self) -> Part:
        """The space the ball needs to turn freely (the well's inner sphere)."""
        return Pos(*self.trackball_position) * Pos(0, 0, self.trackball.z_offset) * Sphere(
            self.trackball.inner_diameter / 2
        )

    def trackball_ball(self) -> Part:
        """The ball itself, for previews."""
        return Pos(*self.trackball_position) * Pos(0, 0, self.trackball.z_offset) * Sphere(self.trackball.diameter / 2)

    def switch_models(self) -> list[Shape]:
        """Cherry MX switch models in every finger and thumb socket, for collision checks (not printed)."""
        model = keyswitch.mx_switch_model()
        return (
            place_instances(self.finger_layout, model, "finger switch")
            + place_instances(self.thumb_layout, model, "thumb switch")
        )

    def keycap_models(self, pressed: bool = False) -> list[Shape]:
        """DSA keycaps on every switch, at rest or bottomed out, for collision checks (not printed)."""
        suffix = " pressed" if pressed else ""
        keycaps = []
        for layout, name in ((self.finger_layout, "finger"), (self.thumb_layout, "thumb")):
            # One shared model per key size
            by_size: dict[float, list[tuple[float, float]]] = {}
            for (column, row) in layout.generate_positions():
                by_size.setdefault(layout.key_size(column, row), []).append((column, row))
            for size, positions in by_size.items():
                model = keyswitch.dsa_keycap_model(size, pressed)
                keycaps += place_instances(layout, model, f"{name} keycap {size:g}u{suffix}", positions)
        return keycaps

    def pcb_models(self) -> list[Part]:
        """Single-key PCBs under every switch, for collision checks (not printed)."""
        pcb = keyswitch.single_key_board()
        return place_instances(self.finger_layout, pcb, "finger PCB") + place_instances(self.thumb_layout, pcb, "thumb PCB")
