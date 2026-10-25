"""Assembly of the keyboard parts with build123d.
"""
import copy
import math
from collections.abc import Iterable
from typing import Optional

from build123d import (
    Box, Compound, Cylinder, Face, GeomType, Kind, Location, Part, Polygon, Pos, Rot, Shape, Solid, Sphere, extrude,
    offset,
)

from ..layouts.finger_well import FingerWellLayout
from ..layouts.keys import Keyswitch
from ..layouts.layout import Layout
from ..layouts.thumb_well import ThumbWellLayout
from ..layouts.transform import Transform
from ..trackball import TrackBall
from . import keyswitch, sensor, surface
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


def place_all(layout: Layout, shape: Part) -> list[Part]:
    """Place a copy of `shape` at every key position of the layout."""
    return [key_location(layout, column, row) * shape for (column, row) in layout.generate_positions()]


def _torus_face(solid: Shape, minor_radius: float) -> Face:
    """The face of `solid` lying on the torus with the given minor radius."""
    return next(
        face for face in solid.faces()
        if face.geom_type == GeomType.TORUS and abs(face.geom_adaptor().Torus().MinorRadius() - minor_radius) < 1e-6
    )


class KeyboardAssembly:
    def __init__(self, columns: int = 6, rows: int = 5):
        k = Keyswitch()
        self.finger_layout = FingerWellLayout(columns=columns, rows=rows, keyswitch=k)
        self.thumb_layout = ThumbWellLayout(keyswitch=k)
        self.trackball = TrackBall()
        self.trackball_position = (-80.25, -25, 14)

        self.plate_thickness = self.finger_layout.plate_thickness
        self.max_height = 120
        "Upper bound for the height of any part (must stay below the far side of the key surface torus)"
        self.finger_straight_columns = (-0.5,)
        self.finger_straight_rows = (-0.75,)
        "Edges of the finger well that should be straight in top view (see `surface.outline()`)"

        self.cavity_depth = 12
        "Depth of the case's inside below the key plane (switch pins end 8.3 mm below it)"
        self.case_wall = 3
        "Thickness of the case's walls and floor"
        self.case_clearance = 0.5
        "Gap between the case's walls and the PCBs under the switches"
        self.join_margin = 15
        "How far past the finger well the thumb well's bottom half is joined to the top (see `case()`)"

        # Stand
        self.table_z = 0
        "Height of the table: the thumb well touches it with the flat strip in its middle"
        self.skirt_inset = 10
        "How far the skirt under the finger well stays inside the outline of the finger well's underside"
        self.dome_flat = 2
        "How far the hemisphere under the trackball would reach below the table; cut off, it stands on a flat disc"

    def case(self) -> dict[str, Part]:
        """The keyboard's case as two parts, "top" and "bottom" (with the trackball's cup).

        Where the two wells' cases overlap, their walls fall away and their insides run into each other: each part
        loses whatever lies inside the other well's cavity (for the plates, only below the other plate), and the thumb
        parts also give way to the finger parts.

        The top joins both key plates: next to the finger well, everything of the thumb well's bottom half that rises
        above the top edge of the finger well's bottom half belongs to the top as well, which ties the two plates
        together.
        """
        finger_plate, finger_outer, finger_cavity, finger_footprint = self._finger_case()
        thumb_plate, thumb_outer, thumb_cavity, thumb_plate_region = self._thumb_case()
        below_finger_plate = finger_cavity - surface.torus(self.finger_layout, depth=self.plate_thickness)
        below_thumb_plate = thumb_cavity - thumb_plate_region

        finger_top = finger_plate - below_thumb_plate
        finger_bottom = finger_outer - finger_cavity - thumb_cavity
        # Cut with copies: OCCT can alter a boolean's tool shape.
        finger_parts = copy.deepcopy(finger_top) + copy.deepcopy(finger_bottom)
        thumb_top = thumb_plate - below_finger_plate - finger_parts
        thumb_bottom = thumb_outer - thumb_cavity - finger_cavity - finger_parts - copy.deepcopy(thumb_top)

        next_to_finger_well = extrude(
            offset(finger_footprint, self.join_margin, kind=Kind.ARC), 2 * self.max_height, both=True
        )
        # Above the finger well's bottom half, i.e. above the finger plate's underside
        above_finger_bottom = surface.torus(self.finger_layout, depth=self.plate_thickness)
        joint = copy.deepcopy(thumb_bottom) & next_to_finger_well & above_finger_bottom
        thumb_bottom -= copy.deepcopy(joint)

        # Heal before further cuts: the fuse leaves small topology errors that make the next cut fail.
        top = (
            self._with_switch_holes(finger_top, self.finger_layout)
            + self._with_switch_holes(thumb_top, self.thumb_layout)
            + joint
        ).fix()
        # The trackball's cup joins both wells' bottom halves into one; where they overlap, the walls fall away and
        # their insides run into each other.
        cup, cup_inside = self._trackball_cup()
        bottom = (finger_bottom + thumb_bottom + (cup - finger_cavity - thumb_cavity)).fix() - cup_inside
        bottom -= copy.deepcopy(top)
        # Where the cup's rim meets the finger well's wall, tiny loose slivers can be left; drop them.
        bottom = max(bottom.solids(), key=lambda solid: solid.volume)
        # The trackball well sits on the cup and just touches the top; that cut can leave a loose sliver of the plate's
        # edge, which is dropped.
        top = max((top - self.trackball_part()).solids(), key=lambda solid: solid.volume)

        bottom = self._with_skirt(bottom, finger_outer)
        # Near the trackball well's equator the finger well's bottom half can reach into the well and the top.
        bottom = bottom - copy.deepcopy(top) - self.trackball_part()

        parts = {"top": top, "bottom": bottom}
        return {name: part.fix() for name, part in parts.items()}

    def _with_skirt(self, bottom: Part, finger_outer: Part) -> Part:
        """Add a skirt under the finger well: a wall from the table up to the bottom half's underside, along the
        underside's outline in top view, shrunk by `skirt_inset`.
        """
        underside = _torus_face(finger_outer, self.finger_layout.row_radius + self.cavity_depth + self.case_wall)
        # The underside's outline in top view
        outline = Polygon(
            *[(p.X, p.Y) for p in underside.outer_wire().positions([i / 400 for i in range(400)])], align=None
        )
        outside = offset(outline, -self.skirt_inset, kind=Kind.ARC)
        ring = outside - offset(outside, -self.case_wall, kind=Kind.ARC)
        skirt = Pos(0, 0, self.table_z) * extrude(ring, 2 * self.max_height, dir=(0, 0, 1)) - copy.deepcopy(bottom)
        skirt -= surface.torus(self.finger_layout, depth=self.cavity_depth + self.case_wall)
        # Keep only what stands on the table (not pieces beyond the case)
        skirt = [solid for solid in skirt.solids() if solid.bounding_box().min.Z < self.table_z + 1e-3]
        return (bottom + skirt).fix()


    def _with_switch_holes(self, plate: Part, layout: Layout) -> Part:
        # Extend the hole well beyond both sides of the plate: when it ends close to the curved surfaces, OCCT
        # sometimes keeps the cut-out piece as a separate solid.
        k = layout.keyswitch
        plate -= place_all(layout, keyswitch.mounting_socket(k, extra_depth=1, extra_height=3))
        plate -= place_all(layout, keyswitch.switch(k))
        return plate

    def _surface_face(self, layout: Layout, footprint: Face, depth: float) -> Face:
        """The key surface at `depth` below the key plane, trimmed by a vertical prism over `footprint`."""
        slab = extrude(footprint, self.max_height) & (
            surface.torus(layout, depth=depth + 1) - surface.torus(layout, depth=depth)
        )
        # Drop slivers from where the torus turns over beyond the footprint; keep the key surface itself.
        slab = max(slab.solids(), key=lambda solid: solid.volume)
        return _torus_face(slab, layout.row_radius + depth)

    @staticmethod
    def _thicken_down(face: Face, amount: float) -> Solid:
        """Thicken a key surface face by `amount` along its normals, away from the keycaps."""
        pointing_up = face.normal_at(face.center()).Z > 0
        return Solid.thicken(face, -amount if pointing_up else amount)

    def _case_inner_footprint(self, layout: Layout) -> Face:
        """The inside of the case in top view: the plate outline, grown to hold every key's PCB.

        The PCBs hang below the keys along the surface normals, just like the case walls, so their squares projected
        from the key plane are what has to fit.
        """
        half = keyswitch.PCB_SIZE / 2 + self.case_clearance
        # Counter-clockwise; the keys face up, so the projections stay counter-clockwise and fuse into one face.
        corners = [(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0)]
        squares = [
            [layout.key_transform(column, row).apply(corner)[:2] for corner in corners]
            for (column, row) in layout.generate_positions()
        ]
        # Straight edges are moved out far enough to hold the PCBs, instead of bulging around them.
        footprint = surface.outline(
            layout,
            straight_columns=self.finger_straight_columns,
            straight_rows=self.finger_straight_rows,
            enclose=[point for square in squares for point in square],
        ).fuse(*[Polygon(*square, align=None) for square in squares]).clean()
        # Fill the small notches between neighbouring squares
        smoothing = 3
        return offset(offset(footprint, smoothing, kind=Kind.ARC), -smoothing, kind=Kind.ARC)

    def _finger_case(self) -> tuple[Part, Part, Part, Face]:
        """The finger well's case as (plate, bottom outside, cavity, footprint in top view), without any holes.

        The top half is the key plate. The bottom half is a copy of it moved down along the surface normals,
        joined to the plate's rim by walls that also run along the normals, so the whole case follows the key
        surface. Screws will go into the rim later.
        """
        layout = self.finger_layout
        inner_footprint = self._case_inner_footprint(layout)
        footprint = offset(inner_footprint, self.case_wall, kind=Kind.ARC)

        # Everything is trimmed on the key plane and then thickened along the surface normals, so all edges follow
        # the normals and the two halves meet flush.
        plate = self._thicken_down(self._surface_face(layout, footprint, 0), self.plate_thickness)
        plate_underside = _torus_face(plate, layout.row_radius + self.plate_thickness)

        # Below the plate down to the outside of the floor, hollowed out by the space inside the walls. The cavity
        # starts at the key plane, above the plate's underside, so the two never share a face.
        outer = self._thicken_down(plate_underside, self.cavity_depth + self.case_wall - self.plate_thickness)
        cavity = self._thicken_down(self._surface_face(layout, inner_footprint, 0), self.cavity_depth)
        # Reaching a bit past the footprint, so the thumb well's case is trimmed flush with the finger well's edge.
        return plate, outer, cavity, footprint

    def _thumb_arc(
        self, center_x: float, start_angle: float, end_angle: float, length: float, top_depth: float, bottom_depth: float
    ) -> Part:
        """An arc of the thumb well's cylinder between two depths below the key plane, in the layout's base frame.

        Angles are column angles (degrees): 0 is the bottom of the circle, positive angles go toward -X. The arc's
        ends are radial planes, so they follow the surface normals.
        """
        radius = self.thumb_layout.column_radius
        arc = end_angle - start_angle
        # A cylinder's arc starts on its local +X axis; after turning its axis onto Y, local angle a points along
        # (cos a, 0, sin a), and a column angle c along (-sin c, 0, -cos c), i.e. local angle -90 - c.
        # (align=None keeps the cylinder's axis at the origin; otherwise a partial cylinder is centered on its bounds.)
        tube = Pos(0, 0, -length / 2) * (
            Cylinder(radius + bottom_depth, length, arc_size=arc, align=None)
            - Cylinder(radius + top_depth, length, arc_size=arc, align=None)
        )
        return Pos(center_x, 0, radius) * Rot(90, 0, 0) * Rot(0, 0, -90 - end_angle) * tube

    def _thumb_band(self, top_depth: float, bottom_depth: float, length: float, inset: float = 0) -> Part:
        """The thumb well's surface thickened between two depths along its normals, in the layout's base frame.

        The arc is split at the bottom of the circle (angle 0) and its halves are moved apart by the flat strip
        under the keys sitting there (see `ThumbWellLayout.placement_adjust()`). Each half reaches half a key
        spacing past its outermost key, less `inset` (mm, measured on the key plane).
        """
        layout = self.thumb_layout
        half_step = math.degrees(layout.rad_per_col) / 2 - math.degrees(inset / layout.column_radius)
        angles = [layout.key_angle(column, row) for (column, row) in layout.generate_positions()]
        flat = layout.flat_width()
        left_end = max(angles) + half_step  # toward -X
        right_end = min(angles) - half_step  # toward +X

        pieces = []
        if left_end > 0:
            pieces.append(self._thumb_arc(-flat / 2, max(right_end, 0), left_end, length, top_depth, bottom_depth))
        if right_end < 0:
            pieces.append(self._thumb_arc(flat / 2, right_end, min(left_end, 0), length, top_depth, bottom_depth))
        if flat > 0:
            pieces.append(
                Pos(0, 0, -(top_depth + bottom_depth) / 2) * Box(flat, length, bottom_depth - top_depth)
            )
        return pieces[0].fuse(*pieces[1:]) if len(pieces) > 1 else pieces[0]

    def _thumb_case(self) -> tuple[Part, Part, Part, Part]:
        """The thumb well's case as (plate, bottom outside, cavity, everything above the plate's underside), built like
        `_finger_case()`, without any holes.

        The thumb surface is made of cylinder arcs and a flat strip, whose normals are radial or vertical, so moving
        it along its normals just means larger radii and a lower strip.
        """
        layout = self.thumb_layout
        to_layout = to_location(layout.layout_place(Transform()))
        # The case is as long as a PCB plus clearance and walls; along the arc, the walls sit inside the half key
        # spacing past the outermost keys, which leaves room for the PCBs.
        inner_length = keyswitch.PCB_SIZE + 2 * self.case_clearance
        length = inner_length + 2 * self.case_wall

        plate = self._thumb_band(0, self.plate_thickness, length)
        outer = self._thumb_band(self.plate_thickness, self.cavity_depth + self.case_wall, length)
        cavity = self._thumb_band(-1, self.cavity_depth, inner_length, inset=self.case_wall)
        # Everything from (almost) the arc's axis down to the plate's underside
        plate_region = self._thumb_band(1 - layout.column_radius, self.plate_thickness, length)
        return to_layout * plate, to_layout * outer, to_layout * cavity, to_layout * plate_region

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
        r = sensor.hole_radius()
        shell_middle = -(math.sqrt(inner_radius**2 - r**2) + math.sqrt(outer_radius**2 - r**2)) / 2
        post_height = shell_middle + ball.diameter / 2 - sensor.board_face_z()
        to_sensor = Pos(0, 0, -ball.diameter / 2)
        well += to_sensor * sensor.standoffs(height=post_height)
        well -= to_sensor * sensor.lens_opening()
        well -= to_sensor * sensor.screw_holes()
        well -= Sphere(inner_radius)
        return self._trackball_center() * well

    def _trackball_cup(self) -> tuple[Part, Part]:
        """The trackball well's bottom, enclosing the sensor module, as (shell, inside): a cylinder from the well's
        equator down, ending in a hemisphere of the same radius that rests on the table.

        The hemisphere reaches `dome_flat` below the table, where it is cut off flat so it stands on a small disc. The
        radius is the smallest that clears the well and leaves the sensor board `case_clearance` of room.
        """
        ball = self.trackball
        center_height = self._trackball_center().position.Z - self.table_z
        board = sensor.model().bounding_box()
        # Board corners in the ball center's frame
        corners = [(x, y, z - ball.diameter / 2) for x in (board.min.X, board.max.X)
                   for y in (board.min.Y, board.max.Y) for z in (board.min.Z, board.max.Z)]

        def hemisphere_center(radius: float) -> float:
            """Height of the hemisphere's center relative to the ball's center."""
            return radius - self.dome_flat - center_height

        def room(radius: float) -> float:
            """Smallest gap between the board's corners and the inside of the cylinder and hemisphere."""
            inner, z0 = radius - self.case_wall, hemisphere_center(radius)
            return min(
                inner - (math.dist((x, y, z), (0, 0, z0)) if z < z0 else math.hypot(x, y)) for (x, y, z) in corners
            )

        # Keep clear of the well's outer sphere too: nearly coincident curved faces break the booleans.
        radius = ball.outer_diameter / 2 + 1 + self.case_wall
        while room(radius) < self.case_clearance:
            radius += 0.25
        z0 = hemisphere_center(radius)

        def capsule(r: float) -> Part:
            cylinder = Pos(0, 0, z0 / 2) * Cylinder(r, -z0)
            return cylinder + Pos(0, 0, z0) * Sphere(r)

        above_table = Pos(0, 0, -center_height / 2) * Box(4 * radius, 4 * radius, center_height)
        inside = capsule(radius - self.case_wall) & above_table
        shell = (capsule(radius) & above_table) - copy.deepcopy(inside) - Sphere(ball.outer_diameter / 2)
        return self._trackball_center() * shell, self._trackball_center() * inside

    def sensor_model(self) -> Compound:
        """The trackball's sensor module, for collision checks (not printed)."""
        return Compound(
            label="sensor", children=[self._sensor_location() * child for child in sensor.model().children]
        )

    def trackball_clearance(self) -> Part:
        """The space the ball needs to turn freely (the well's inner sphere)."""
        return self._trackball_center() * Sphere(self.trackball.inner_diameter / 2)

    def trackball_ball(self) -> Part:
        """The ball itself, for previews."""
        return self._trackball_center() * Sphere(self.trackball.diameter / 2)

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
