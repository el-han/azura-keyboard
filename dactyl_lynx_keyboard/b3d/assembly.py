"""Assembly of the keyboard parts with build123d.
"""
import copy
import math
from collections.abc import Iterable
from typing import Callable, Optional

from build123d import (
    Box, Compound, Cylinder, Face, GeomType, Kind, Location, Part, Plane, Polygon, Pos, Rot, Shape, Solid, Sphere,
    Vector, extrude, mirror, offset,
)
from OCP.gp import gp_Trsf

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


def mirrored(location: Location) -> Location:
    """The location mirrored across the YZ plane, for an unmirrored part: its position and orientation are mirrored
    (X turned around), but it stays a rotation, so the part itself keeps its handedness."""
    trsf = location.wrapped.Transformation()
    sign = (-1, 1, 1, 1)  # X turned around; the last column is the translation
    values = [sign[i] * sign[j] * trsf.Value(i + 1, j + 1) for i in range(3) for j in range(4)]
    mirrored_trsf = gp_Trsf()
    mirrored_trsf.SetValues(*values)
    return Location(mirrored_trsf)


def place_instances(
    layout: Layout,
    shape: Shape,
    name: str,
    positions: Optional[Iterable[tuple[float, float]]] = None,
    place: Callable[[Location], Location] = lambda location: location,
) -> list[Shape]:
    """Place an instance of `shape` at every key position (or the given ones), sharing its geometry; `place` turns
    a key's location into the instance's (e.g. mirrored for the left half).

    Exported as children of an assembly, the geometry is written to STEP only once. Each instance is labelled
    "<name> c<column> r<row>".
    """
    instances = []
    for (column, row) in layout.generate_positions() if positions is None else positions:
        location = key_location(layout, column, row)
        instance = _instance(shape, place(location))
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


def _grid(shape: Shape, n: int) -> list[Vector]:
    """Points of an n×n×n grid over the shape's bounding box that lie inside it."""
    box = shape.bounding_box()
    steps = [i / (n - 1) for i in range(n)]
    points = [
        box.min + Vector(box.size.X * u, box.size.Y * v, box.size.Z * w) for u in steps for v in steps for w in steps
    ]
    return [point for point in points if shape.is_inside(point)]


HALVES = {
    "right": dict(side="right", with_trackball=True, thumb_keys=3),
    "left": dict(side="left", with_trackball=False, thumb_keys=5),
}
"The two halves that are built: keyword arguments for `KeyboardAssembly`, by name"


class KeyboardAssembly:
    def __init__(
        self, columns: int = 6, rows: int = 5, with_trackball: bool = True, thumb_keys: int = 5, side: str = "right"
    ):
        if side not in ("left", "right"):
            raise ValueError(f"side must be 'left' or 'right', not {side!r}")
        self.side = side
        "Which half: everything is designed as the right half; the left half's case is its mirror image"
        self.offset = Location()
        "Where the parts that are not printed are moved to (e.g. to show both halves side by side)"
        k = Keyswitch()
        self.finger_layout = FingerWellLayout(columns=columns, rows=rows, keyswitch=k)
        # Low enough that the finger well's bottom half rests on the table
        self.finger_layout.placement_transform = (0, 0, 12.05)
        self.thumb_layout = ThumbWellLayout(keyswitch=k, keys=thumb_keys)
        self.with_trackball = with_trackball
        "Whether this half has the trackball, its well and its sensor"
        self.trackball = TrackBall()
        self.trackball_position = (-80.25, -25, 37)
        "Center of the ball"
        self.bearing_pocket = (7.5, 4)
        "Diameter and depth of the pockets for the ball transfer units (QB310 7.5) that hold the ball"
        self.bearing_tilt = 60
        "Angle of the bearings' axes from the vertical (degrees)"
        self.bearing_azimuths = (90, 210, 330)
        "Directions of the bearings around the ball in top view (degrees from +X), clear of the sensor's screw posts"

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
        self.dome_flat = 6
        "How far the hemisphere under the trackball would reach below the table; cut off, it stands on a flat disc"

        # Cable passages into the finger well, where the controller sits (in the skirt, at the back left)
        self.thumb_passage = (12, 5)
        "Width and height of the passage for the thumb keys' wires"
        self.trackball_passage = (12, 5)
        "Width and height of the passage for the sensor's wires (one per pin of its 7-pin header)"

        # M2.5 screws from below into heat-set inserts, in bosses inside corners of the finger well
        self.screw_corners = ((-0.5, -0.75), (5.5, -0.75), (2.5, 4.75))
        "Corners of the finger well's outline (column, row) with a screw"
        self.screw_hole = 2.9
        "Diameter of the screws' clearance holes"
        self.screw_head = (5.0, 2.6)
        "Diameter and depth of the counterbores for the screw heads (DIN 912: 4.5 × 2.5 mm)"
        self.insert_hole = (3.5, 5)
        "Diameter and depth of the holes for the heat-set inserts"
        self.screw_boss = 7
        "Diameter of the bosses around the screws and inserts"
        self.screw_margin = 1.5
        "Smallest thickness of the case's outside around a boss"

    def case(self) -> dict[str, Part]:
        """The keyboard's case as two parts: "top" (key plates, walls and the trackball well with its cylinder) and
        "bottom" (the floors, the trackball's hemisphere and the skirt). Without `with_trackball`, there is no
        trackball well, cylinder or hemisphere.

        Where the two wells' cases overlap, their walls fall away and their insides run into each other: each part
        loses whatever lies inside the other well's cavity (for the plates, only below the other plate), and the finger
        parts also give way to the thumb parts.

        The top joins both key plates: next to the finger well, everything of the thumb well's bottom half that rises
        above the top edge of the finger well's floor belongs to the top as well, which ties the two plates
        together.
        """
        finger_plate, finger_outer, finger_cavity, finger_footprint = self._finger_case()
        thumb_plate, thumb_outer, thumb_cavity, thumb_plate_region = self._thumb_case()
        below_finger_plate = finger_cavity - surface.torus(self.finger_layout, depth=self.plate_thickness)
        below_thumb_plate = thumb_cavity - thumb_plate_region

        thumb_top = thumb_plate - below_finger_plate
        # Cut with copies: OCCT can alter a boolean's tool shape.
        thumb_bottom = thumb_outer - thumb_cavity - finger_cavity - copy.deepcopy(thumb_top)
        thumb_parts = copy.deepcopy(thumb_top) + copy.deepcopy(thumb_bottom)
        finger_top = finger_plate - below_thumb_plate - thumb_parts
        finger_bottom = finger_outer - finger_cavity - thumb_cavity - copy.deepcopy(thumb_parts)

        next_to_finger_well = self._prism(offset(finger_footprint, self.join_margin, kind=Kind.ARC))
        # The walls (everything above the cavities' floor) belong to the top, the floors to the bottom.
        above_finger_floor = surface.torus(self.finger_layout, depth=self.cavity_depth)
        # Next to the finger well, the thumb well's bottom half belongs to the top above the finger floor's top edge:
        # only where the two wells meet, not where the thumb well's arc comes back up into that margin.
        join = copy.deepcopy(thumb_bottom) & next_to_finger_well & copy.deepcopy(above_finger_floor)
        join = [solid for solid in join.solids() if solid.distance_to(finger_outer) < 1e-3]
        above_thumb_floor = self._thumb_above(self.cavity_depth).fuse(*join)
        finger_walls = copy.deepcopy(finger_bottom) & above_finger_floor
        thumb_walls = copy.deepcopy(thumb_bottom) & above_thumb_floor
        finger_floor = finger_bottom - above_finger_floor
        thumb_floor = thumb_bottom - above_thumb_floor

        # Heal before further cuts: the fuse leaves small topology errors that make the next cut fail.
        top = (
            self._with_switch_holes(finger_top, self.finger_layout)
            + self._with_switch_holes(thumb_top, self.thumb_layout)
            + finger_walls
            + thumb_walls
        ).fix()
        # The finger floor is open inside the skirt.
        skirt_outline = self._skirt_outline(finger_outer)
        inside_skirt = self._prism(offset(skirt_outline, -self.case_wall))
        finger_floor -= copy.deepcopy(inside_skirt)
        bottom = (finger_floor + thumb_floor).fix()
        # The thumb well's floor reaches back to the skirt, and no further toward -X than the skirt's outside
        extension = (self._thumb_floor_extension() & self._beside_skirt(skirt_outline)) - inside_skirt
        bottom = (bottom + (extension - finger_cavity - thumb_cavity)).fix()
        if self.with_trackball:
            # The trackball's bottom: its cylinder and the well join the top, its hemisphere the bottom. Where they
            # overlap the wells' cases, the walls fall away and the insides run into each other.
            cylinder, hemisphere, cup_inside = self._trackball_cup()
            top = (top - copy.deepcopy(cup_inside)).fix()
            # Join the well and its cylinder first: their outsides meet flush, which the fuse with the rest can't
            # handle.
            trackball_top = ((cylinder - finger_cavity - thumb_cavity) + self.trackball_part()).fix()
            top = (top + trackball_top).fix()
            bottom = (bottom + (hemisphere - finger_cavity - thumb_cavity)).fix() - cup_inside

        bottom -= copy.deepcopy(top)
        # Where the thumb and finger wells meet, the top cuts a bit of floor loose; drop it.
        bottom = max(bottom.solids(), key=lambda solid: solid.volume)
        bottom = self._with_skirt(bottom, finger_outer)
        bottom = bottom - copy.deepcopy(top)

        passages = self._cable_passages(finger_cavity, thumb_cavity)
        top, bottom = top - copy.deepcopy(passages), bottom - passages
        # A passage can cut off the bit of wall between it and the bottom part; drop it.
        top = max(top.solids(), key=lambda solid: solid.volume)

        lower, upper, holes = self._screw_bosses(copy.deepcopy(finger_outer), copy.deepcopy(thumb_outer), top, bottom)
        top = (((top - copy.deepcopy(lower)) + upper).fix() - copy.deepcopy(holes)).fix()
        bottom = ((bottom + lower).fix() - holes).fix()

        parts = {"top": top, "bottom": bottom}
        if self.left:
            parts = {name: mirror(part, Plane.YZ) for name, part in parts.items()}
        return {name: part.fix() for name, part in parts.items()}

    def _screw_bosses(
        self, finger_outside: Part, thumb_outside: Part, top: Part, bottom: Part
    ) -> tuple[Part, Part, Part]:
        """Bosses for the screws in the finger well's `screw_corners` and the thumb well's gaps after its first and
        before its last key, as (lower parts for the bottom, upper parts for the top, holes).

        A boss stands along the key surface's normal at its place, like the walls, at the nearest place where it
        stays `screw_margin` inside the case's outside and clear of the switches and PCBs; it may reach into the
        walls. Its lower part reaches from inside the floor to a wall's thickness above it and holds the screw's
        counterbore and clearance hole, so the screw goes in from below; its upper part reaches to just below the
        plate and holds the insert. None of its faces lies on one of the case's curved faces.

        In the thumb well, a boss stands midway between the front and back walls, and a web between the keys ties its
        upper part to the plate and the front wall; behind it, the wires pass.
        """
        boss, head = self.screw_boss / 2, self.screw_head[0] / 2
        underside = -(self.cavity_depth + self.case_wall)
        bottom_z, split, top_z = underside + 1, -self.cavity_depth + self.case_wall, -self.plate_thickness - 0.5
        obstacles = Compound(children=[
            shape
            for layout in (self.finger_layout, self.thumb_layout)
            for model in (keyswitch.mx_switch_envelope(), keyswitch.single_key_board())
            for shape in place_instances(layout, model, "")
        ] + ([self._trackball_cup()[2]] if self.with_trackball else []))

        def column(bottom: float, top: float, radius: float) -> Part:
            return Pos(0, 0, (bottom + top) / 2) * Cylinder(radius, top - bottom)

        # Places around a corner (in its frame, 1 mm apart, up to 15 mm away), nearest first
        around = sorted(
            [(dx, dy) for dx in range(-15, 16) for dy in range(-15, 16) if math.hypot(dx, dy) <= 15],
            key=lambda offset: math.hypot(*offset),
        )
        thumb_columns = sorted({-0.5, self.thumb_layout.keys - 2.5})
        # The web reaches into the plate and the middle of the front wall
        web_end = self._thumb_inner_length / 2 + self.case_wall / 2
        web_top = -self.plate_thickness + 1
        web = Pos(0, -web_end / 2, (split + web_top) / 2) * Box(self.case_wall, web_end, web_top - split)
        places = [(self.finger_layout, finger_outside, corner, around, None) for corner in self.screw_corners] + [
            (self.thumb_layout, thumb_outside, (column, 0), [(0, 0)], web) for column in thumb_columns
        ]
        bosses = []
        for layout, outside, corner, offsets, tie in places:
            at_corner = to_location(layout.key_transform(*corner))
            for dx, dy in offsets:
                frame = at_corner * Pos(dx, dy, 0)
                whole = frame * column(bottom_z, top_z, boss)
                stray = frame * column(bottom_z, top_z, boss + self.screw_margin) - copy.deepcopy(outside)
                if stray is not None and stray.solids() and stray.volume > 0.01:
                    continue
                if (frame * (column(bottom_z, top_z, boss) + tie) if tie else whole).distance_to(obstacles) < 0.3:
                    continue
                # Each part holds on to its part of the case
                lower = frame * column(bottom_z, split, boss)
                upper = frame * (column(split, top_z, boss) + tie if tie else column(split, top_z, boss))
                holes = frame * (
                    column(underside - 1, underside + self.screw_head[1], head)
                    + column(underside - 1, split, self.screw_hole / 2)
                    + column(split, split + self.insert_hole[1], self.insert_hole[0] / 2)
                )
                if all(
                    (held := part & copy.deepcopy(holder)) is not None and held.solids() and held.volume > 10
                    for part, holder in ((lower, bottom), (upper, top))
                ):
                    break
            else:
                raise ValueError(f"No room for the screw at {corner}")
            bosses.append((lower, upper, holes))
        return tuple(Compound(children=[found[i] for found in bosses]) for i in range(3))

    def _prism(self, face: Face) -> Part:
        """Everything above and below a face in top view."""
        return extrude(face, 2 * self.max_height, both=True)

    def _cable_passages(self, finger_cavity: Part, thumb_cavity: Part) -> Part:
        """Slots through the walls where the thumb well's and the trackball cup's insides come closest to the finger
        well's."""
        def passage(point: Vector, direction: Vector, size: tuple[float, float], length: float) -> Part:
            # Wide side horizontal
            angle = math.degrees(math.atan2(direction.Y, direction.X))
            tilt = math.degrees(math.asin(max(-1, min(1, direction.Z))))
            return Pos(point) * Rot(0, 0, angle) * Rot(0, -tilt, 0) * Box(length, size[0], size[1])

        _, p, q = copy.deepcopy(thumb_cavity).distance_to_with_closest_points(copy.deepcopy(finger_cavity))
        p, q = Vector(p), Vector(q)
        # Through the middle of the wall the two wells share, lowered until it stays within the wells' walls and
        # insides (and clear of the plates above)
        finger_outer, thumb_outer = self._finger_case()[1], self._thumb_case()[1]
        shared = (copy.deepcopy(thumb_outer) & copy.deepcopy(finger_outer)).bounding_box().center()
        across = Vector((q - p).X, (q - p).Y, 0).normalized()
        along = Vector(-across.Y, across.X, 0)
        middle = (p + q) / 2 + along * (shared - (p + q) / 2).dot(along)
        walls_and_insides = (finger_outer, thumb_outer, finger_cavity, thumb_cavity)
        for drop in [0.5 * i for i in range(21)]:
            center = middle - Vector(0, 0, drop)
            thumb = passage(center, across, self.thumb_passage, 4 * self.case_wall)
            if all(any(shape.is_inside(point) for shape in walls_and_insides) for point in _grid(thumb, 5)):
                break
        else:
            raise ValueError("No room for the thumb well's cable passage")
        passages = thumb
        if self.with_trackball:
            cup_inside = self._trackball_cup()[2]
            _, p, q = cup_inside.distance_to_with_closest_points(copy.deepcopy(finger_cavity))
            point = (Vector(p) + Vector(q)) / 2
            outward = point - self._trackball_center().position
            # Through the cup's wall and the finger well's
            passages += passage(
                point, Vector(outward.X, outward.Y, 0).normalized(), self.trackball_passage, 4 * self.case_wall
            )
        return passages

    def _skirt_outline(self, finger_outer: Part) -> Face:
        """The skirt's outside in top view: the finger well's underside's outline, shrunk by `skirt_inset`."""
        underside = _torus_face(finger_outer, self.finger_layout.row_radius + self.cavity_depth + self.case_wall)
        outline = Polygon(
            *[(p.X, p.Y) for p in underside.outer_wire().positions([i / 400 for i in range(400)])], align=None
        )
        return offset(outline, -self.skirt_inset, kind=Kind.ARC)

    def _beside_skirt(self, skirt_outline: Face) -> Part:
        """Everything on the +X side of the line along the skirt's outside toward -X (from its front corner to its
        back end)."""
        points = [v.center() for v in skirt_outline.vertices()]
        front = min(points, key=lambda p: p.X)
        back_y = max(p.Y for p in points)
        back = min((p for p in points if p.Y > back_y - 0.5), key=lambda p: p.X)
        along = (back - front).normalized()
        normal = Vector(along.Y, -along.X, 0)  # toward +X
        size = 4 * self.max_height
        return Pos(front + normal * (size / 2)) * Rot(0, 0, math.degrees(math.atan2(normal.Y, normal.X))) * Box(
            size, size, size
        )

    def _with_skirt(self, bottom: Part, finger_outer: Part) -> Part:
        """Add a skirt under the finger well: a wall from the table up to the bottom half's underside, along the
        underside's outline in top view, shrunk by `skirt_inset`, closed by a floor on the table.
        """
        outside = self._skirt_outline(finger_outer)
        ring = outside - offset(outside, -self.case_wall, kind=Kind.ARC)
        # Up to `max_height`, which stays below the far side of the torus
        skirt = Pos(0, 0, self.table_z) * extrude(ring, self.max_height, dir=(0, 0, 1)) - copy.deepcopy(bottom)
        skirt -= surface.torus(self.finger_layout, depth=self.cavity_depth + self.case_wall)
        # Closed at the bottom by a floor of `case_wall`, which stays out of the finger well's inside
        floor = Pos(0, 0, self.table_z) * extrude(outside, self.case_wall, dir=(0, 0, 1))
        floor -= surface.torus(self.finger_layout, depth=self.cavity_depth)
        return (bottom + skirt + floor).fix()


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
        self,
        center_x: float,
        start_angle: float,
        end_angle: float,
        length: float,
        top_depth: float,
        bottom_depth: float,
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

    @property
    def _thumb_inner_length(self) -> float:
        """Length of the thumb well's inside across the arc: a PCB plus clearance."""
        return keyswitch.PCB_SIZE + 2 * self.case_clearance

    def _thumb_placed(self, band: Part) -> Part:
        """A shape from the thumb layout's base frame, where it goes."""
        return to_location(self.thumb_layout.layout_place(Transform())) * band

    def _thumb_floor_extension(self) -> Part:
        """The thumb well's floor, reaching well past the case's back end (to be cut off at the skirt)."""
        e = 40
        length = self._thumb_inner_length + 2 * self.case_wall + e
        return self._thumb_placed(
            Pos(0, e / 2, 0) * self._thumb_band(self.cavity_depth, self.cavity_depth + self.case_wall, length)
        )

    def _thumb_above(self, depth: float) -> Part:
        """Everything of the thumb well (from almost its arc's axis) down to `depth` below its key plane."""
        length = 2 * (self._thumb_inner_length + 2 * self.case_wall)
        return self._thumb_placed(self._thumb_band(1 - self.thumb_layout.column_radius, depth, length))

    def _thumb_case(self) -> tuple[Part, Part, Part, Part]:
        """The thumb well's case as (plate, bottom outside, cavity, everything above the plate's underside), built like
        `_finger_case()`, without any holes.

        The thumb surface is made of cylinder arcs and a flat strip, whose normals are radial or vertical, so moving
        it along its normals just means larger radii and a lower strip.
        """
        # The case is as long as a PCB plus clearance and walls; along the arc, the walls sit inside the half key
        # spacing past the outermost keys, which leaves room for the PCBs.
        inner_length = self._thumb_inner_length
        length = inner_length + 2 * self.case_wall
        return tuple(self._thumb_placed(band) for band in (
            self._thumb_band(0, self.plate_thickness, length),
            self._thumb_band(self.plate_thickness, self.cavity_depth + self.case_wall, length),
            self._thumb_band(-1, self.cavity_depth, inner_length, inset=self.case_wall),
            # Everything from (almost) the arc's axis down to the plate's underside
            self._thumb_band(1 - self.thumb_layout.column_radius, self.plate_thickness, length),
        ))

    def _trackball_center(self) -> Location:
        return Pos(*self.trackball_position)

    def _sensor_location(self) -> Location:
        """The sensor frame: the bottom of the ball, with the board's long side along X."""
        return self._trackball_center() * Pos(0, 0, -self.trackball.diameter / 2)

    def trackball_part(self) -> Part:
        """The trackball well: the lower half of a spherical shell around the ball, with an opening for the sensor's
        lens, screw posts for its board and pockets for the ball transfer units the ball rests on. Its outside is flush
        with the cylinder below it.
        """
        ball = self.trackball
        inner_radius, outer_radius = ball.inner_diameter / 2, self._trackball_cup_radius()
        shell = Sphere(outer_radius) - Sphere(inner_radius)
        lower_half = Pos(0, 0, -outer_radius) * Box(*(2 * outer_radius,) * 3)
        well = shell & lower_half
        # Room for the sensor board, which the thick shell would reach into
        board = sensor.model().bounding_box()
        c = self.case_clearance
        board_room = Pos(board.center().X, board.center().Y, (sensor.board_face_z() + c - outer_radius) / 2) * Box(
            board.size.X + 2 * c, board.size.Y + 2 * c, sensor.board_face_z() + c + outer_radius
        )
        well -= Pos(0, 0, -ball.diameter / 2) * board_room

        # Screw posts from the sensor board up into the middle of the shell wall above the screw holes.
        r = sensor.hole_radius()
        shell_middle = -(math.sqrt(inner_radius**2 - r**2) + math.sqrt(outer_radius**2 - r**2)) / 2
        post_height = shell_middle + ball.diameter / 2 - sensor.board_face_z()
        to_sensor = Pos(0, 0, -ball.diameter / 2)
        well += to_sensor * sensor.standoffs(height=post_height)
        well -= to_sensor * sensor.lens_opening()
        well -= to_sensor * sensor.screw_holes()
        well -= Sphere(inner_radius)
        # Pockets for the bearings, from the inside of the shell outward, their axes through the ball's center
        diameter, depth = self.bearing_pocket
        tilt = math.radians(self.bearing_tilt)
        for azimuth in map(math.radians, self.bearing_azimuths):
            axis = Vector(math.sin(tilt) * math.cos(azimuth), math.sin(tilt) * math.sin(azimuth), -math.cos(tilt))
            well -= Solid.make_cylinder(diameter / 2, depth + 1, Plane(origin=axis * (inner_radius - 1), z_dir=axis))
        return self._trackball_center() * well

    def _hemisphere_center(self, radius: float) -> float:
        """Height of the trackball cup's hemisphere center relative to the ball's center."""
        center_height = self._trackball_center().position.Z - self.table_z
        return radius - self.dome_flat - center_height

    def _trackball_cup_radius(self) -> float:
        """Outer radius of the trackball cup (and the well): the smallest that leaves the sensor board
        `case_clearance` of room inside a wall of `case_wall`."""
        ball = self.trackball
        board = sensor.model().bounding_box()
        # Board corners in the ball center's frame
        corners = [(x, y, z - ball.diameter / 2) for x in (board.min.X, board.max.X)
                   for y in (board.min.Y, board.max.Y) for z in (board.min.Z, board.max.Z)]

        def room(radius: float) -> float:
            """Smallest gap between the board's corners and the inside of the cylinder and hemisphere."""
            inner, z0 = radius - self.case_wall, self._hemisphere_center(radius)
            return min(
                inner - (math.dist((x, y, z), (0, 0, z0)) if z < z0 else math.hypot(x, y)) for (x, y, z) in corners
            )

        radius = ball.inner_diameter / 2 + self.case_wall
        while room(radius) < self.case_clearance:
            radius += 0.25
        return radius

    def _trackball_cup(self) -> tuple[Part, Part, Part]:
        """The trackball well's bottom, enclosing the sensor module, as (cylinder, hemisphere, inside): a cylinder
        from the well's equator down, flush with the well's outside, ending in a hemisphere of the same radius that
        rests on the table.

        The hemisphere reaches `dome_flat` below the table, where it is cut off flat so it stands on a small disc.
        """
        ball = self.trackball
        center_height = self._trackball_center().position.Z - self.table_z
        radius = self._trackball_cup_radius()
        z0 = self._hemisphere_center(radius)

        def capsule(r: float) -> Part:
            cylinder = Pos(0, 0, z0 / 2) * Cylinder(r, -z0)
            return cylinder + Pos(0, 0, z0) * Sphere(r)

        def between(bottom: float, top: float) -> Part:
            """Everything between two heights (relative to the ball's center) around the cup."""
            return Pos(0, 0, (bottom + top) / 2) * Box(4 * radius, 4 * radius, top - bottom)

        # With a floor of `case_wall` on the table
        inside = capsule(radius - self.case_wall) & between(self.case_wall - center_height, 0)
        shell = (capsule(radius) & between(-center_height, 0)) - copy.deepcopy(inside) - Sphere(ball.inner_diameter / 2)
        # Split at the hemisphere's center: the cylinder above, the hemisphere below
        cylinder_part = between(z0, z0 + center_height)
        return tuple(
            self._trackball_center() * shape
            for shape in (shell & copy.deepcopy(cylinder_part), shell - cylinder_part, inside)
        )

    def sensor_model(self, simple: bool = False) -> Compound:
        """The trackball's sensor module, for collision checks (not printed); `simple` uses a few boxes around it
        instead."""
        model = sensor.envelope() if simple else sensor.model()
        location = self._placed(self._sensor_location())
        return Compound(label="sensor", children=[location * child for child in model.children])

    def trackball_clearance(self) -> Part:
        """The space the ball needs to turn freely (the well's inner sphere)."""
        return self._placed(self._trackball_center()) * Sphere(self.trackball.inner_diameter / 2)

    def trackball_ball(self) -> Part:
        """The ball itself, for previews."""
        return self._placed(self._trackball_center()) * Sphere(self.trackball.diameter / 2)

    @property
    def left(self) -> bool:
        return self.side == "left"

    def _placed(self, location: Location) -> Location:
        """Where a part that is not printed goes: at `location` in the right half, mirrored in the left; moved by
        `offset`."""
        return self.offset * (mirrored(location) if self.left else location)

    def switch_models(self, simple: bool = False) -> list[Shape]:
        """Cherry MX switch models in every finger and thumb socket, for collision checks (not printed); `simple`
        uses a few boxes around each switch instead."""
        return self._on_every_key(keyswitch.mx_switch_envelope() if simple else keyswitch.mx_switch_model(), "switch")

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
                keycaps += place_instances(
                    layout, model, f"{name} keycap {size:g}u{suffix}", positions, place=self._placed
                )
        return keycaps

    def pcb_models(self) -> list[Part]:
        """Single-key PCBs under every switch, for collision checks (not printed)."""
        return self._on_every_key(keyswitch.single_key_board(), "PCB")

    def _on_every_key(self, model: Shape, name: str) -> list[Shape]:
        """Instances of `model` on every finger and thumb key, labelled "finger <name> c<column> r<row>" etc."""
        return [
            instance
            for layout, well in ((self.finger_layout, "finger"), (self.thumb_layout, "thumb"))
            for instance in place_instances(layout, model, f"{well} {name}", place=self._placed)
        ]
