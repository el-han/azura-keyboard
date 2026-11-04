"""One half of a keyboard: puts the parts of the case together and places the components on it.
"""
import copy
from typing import Optional

from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
from build123d import Box, Compound, Kind, Location, Part, Plane, Polygon, Pos, Shape, Sphere, mirror, offset

from ..components import key_pcb, keycap, keyswitch, trackball_sensor
from ..components.keyswitch import Keyswitch
from ..components.trackball import TrackBall
from ..geometry import surface
from ..geometry.key_layout import KeyLayout
from ..geometry.placement import mirrored, place_all, place_instances
from .dimensions import Dimensions
from .finger_case import FingerCase, FingerLayout
from .screws import Screws, around_a_corner
from .skirt import Skirt
from .thumb_case import ThumbCase, ThumbLayout
from .trackball_case import TrackballCase

def _with_switch_holes(plate: Part, layout: KeyLayout) -> Part:
    # Extend the hole well beyond both sides of the plate: when it ends close to the curved surfaces, OCCT
    # sometimes keeps the cut-out piece as a separate solid.
    k = layout.keyswitch
    plate -= place_all(layout, keyswitch.mounting_socket(k, extra_depth=1, extra_height=3))
    plate -= place_all(layout, keyswitch.switch(k))
    return plate


class Keyboard:
    def __init__(
        self, side: str = "right", thumb_keys: int = 5, trackball: Optional[TrackBall] = None, columns: int = 6,
        rows: int = 5, dimensions: Dimensions = Dimensions(),
    ):
        if side not in ("left", "right"):
            raise ValueError(f"side must be 'left' or 'right', not {side!r}")
        self.side = side
        "Which half: everything is designed as the right half; the left half's case is its mirror image"
        self.offset = Location()
        "Where the parts that are not printed are moved to (e.g. to show both halves side by side)"
        self.dimensions = dimensions
        k = Keyswitch()
        self.finger_layout = FingerLayout(columns=columns, rows=rows, keyswitch=k)
        self.finger_layout.placement_transform = dimensions.finger_placement
        self.thumb_layout = ThumbLayout(keyswitch=k, keys=thumb_keys)
        self.finger_case = FingerCase(self.finger_layout, self.dimensions)
        self.thumb_case = ThumbCase(self.thumb_layout, self.dimensions)
        self.trackball_case = TrackballCase(trackball, self.dimensions) if trackball else None
        self.skirt = Skirt(self.finger_layout, self.dimensions)
        self.screws = Screws(self.dimensions)

    @property
    def with_trackball(self) -> bool:
        return self.trackball_case is not None

    @property
    def left(self) -> bool:
        return self.side == "left"

    def case(self) -> dict[str, Part]:
        """The keyboard's case as two parts: "top" (key plates, walls and the trackball's shell and cup) and
        "bottom" (the floors, the foot of the trackball's cup and the skirt).

        Where the finger and thumb cases overlap, their walls fall away and their insides run into each other. The
        steps' order matters: OCCT fails on some cuts and fuses once parts have been joined.
        """
        thumb = self.thumb_case.shapes()
        finger, raised_wall = self._finger_behind_thumb(self.finger_case.shapes())
        top_pieces, floors = self._walls_and_floors(finger, thumb)
        # The floors first, from copies: joining the top alters shapes they share with it, and the joined floors lose
        # the finger case's.
        bottom = self._joined_floors(*copy.deepcopy(floors), copy.deepcopy(finger), copy.deepcopy(thumb))
        # The finger case's corner that now lies inside the keyboard falls away
        finger_top, thumb_top, finger_walls, thumb_walls = top_pieces
        finger_walls = finger_walls - self._corner_inside_thumb_room()
        top = (self._joined_top(finger_top, thumb_top, finger_walls, thumb_walls) + raised_wall).fix()
        top = (top + self._plate_beside_thumb(copy.deepcopy(finger), copy.deepcopy(thumb))).fix()
        top = (top + self._front_wall_beside_thumb(copy.deepcopy(finger), copy.deepcopy(thumb))).fix()
        if self.trackball_case:
            top, bottom = self._with_trackball_cup(top, bottom, thumb[2])
        bottom = self._finished_bottom(top, bottom, finger[1])
        # (No cable passages for now, to the thumb case or the trackball: see `thumb_passage()` and
        # `TrackballCase.passage()`.)
        hook, pocket = self.thumb_case.hook()
        top, bottom = (top - pocket).fix(), (bottom + hook).fix()
        top, bottom = self._with_screws(top, bottom, finger[1], thumb[1])

        # The skirt's walls are extrusions of offset curves, which OCCT's STEP writer drops: as NURBS they come through
        bottom = Part(BRepBuilderAPI_NurbsConvert(bottom.wrapped, True).Shape())
        parts = {"top": top, "bottom": bottom}
        if self.left:
            parts = {name: mirror(part, Plane.YZ) for name, part in parts.items()}
        return {name: part.fix() for name, part in parts.items()}

    def _finger_behind_thumb(self, finger: tuple) -> tuple[tuple, Part]:
        """The finger case cut off where the thumb case's back wall stands, and that wall raised to the finger case's
        key plane, which makes it the finger case's front wall there.

        Where the thumb case's top rises above the finger case's key plane, nothing is left of the raised wall: the
        thumb case's own wall closes the finger case there.
        """
        plate, outer, cavity, footprint = finger
        fc, d = self.finger_case, self.dimensions
        # Left of the step between columns 2 and 3
        xy = lambda column, row: self.finger_layout.key_transform(column, row).apply((0, 0, 0))[:2]
        (x0, y0), (x1, y1) = xy(2.5, 2.5), xy(2.5, 6)
        beside_thumb = d.prism(Polygon((x0, y0), (x1, y1), (x1 - 300, y1), (x0 - 300, y0), align=None))
        # Trimmed like the finger case's walls, along the key surface's normals, so it runs flush into them
        under_finger_case = fc._thicken_down(fc.key_plane_face, d.cavity_depth + d.wall + 30)
        wall = self.thumb_case.back_wall() & under_finger_case & beside_thumb
        wall = wall - surface.torus(self.finger_layout, depth=0) - copy.deepcopy(self.thumb_case.shapes()[1])
        # The finger case gives way to the thumb case and the room above its keys; `_walls_and_floors()` cuts the rest
        # of its outside to fit
        _, thumb_outer, thumb_cavity, above_thumb_plate = self.thumb_case.shapes()
        plate = plate - copy.deepcopy(above_thumb_plate)
        cavity = cavity - (above_thumb_plate + thumb_outer + thumb_cavity)
        # Nor does its front stay above the inside of the thumb case's walls, where the thumb keys need room
        outer = outer - self.thumb_case.inside_and_above()
        return (plate, outer, cavity, footprint), wall

    def _walls_and_floors(self, finger: tuple, thumb: tuple) -> tuple[tuple[Part, Part, Part, Part], tuple[Part, Part]]:
        """The finger and thumb cases cut to fit each other, as ((finger plate, thumb plate, finger walls, thumb
        walls), (finger floor, thumb floor)).

        Each part loses whatever lies inside the other case's cavity (for the plates, only below the other plate), and
        the finger parts also give way to the thumb parts.

        The top joins both key plates: next to the finger case, the thumb case's side walls above the finger floor's
        top belong to the top as well, which ties the two plates together, and its floor above the finger plate's
        underside; the floor between those two falls away, inside the case.
        """
        d = self.dimensions
        finger_plate, finger_outer, finger_cavity, finger_footprint = finger
        thumb_plate, thumb_outer, thumb_cavity, thumb_plate_region = thumb
        below_finger_plate = finger_cavity - surface.torus(self.finger_layout, depth=d.plate_thickness)
        below_thumb_plate = thumb_cavity - thumb_plate_region

        thumb_top = thumb_plate - below_finger_plate
        # Cut with copies: OCCT can alter a boolean's tool shape.
        thumb_bottom = thumb_outer - thumb_cavity - finger_cavity - copy.deepcopy(thumb_top)
        thumb_parts = copy.deepcopy(thumb_top) + copy.deepcopy(thumb_bottom)
        finger_top = finger_plate - below_thumb_plate - thumb_parts
        finger_bottom = finger_outer - finger_cavity - thumb_cavity - copy.deepcopy(thumb_parts)

        # (grown in steps: OCCT's offset of the finger case's many-sided outline in one go comes out invalid)
        grown = finger_footprint
        for _ in range(3):
            grown = offset(grown, d.join_margin / 3, kind=Kind.ARC)
        next_to_finger_case = d.prism(grown)
        # The walls (everything above the cavities' floor) belong to the top, the floors to the bottom.
        above_finger_floor = surface.torus(self.finger_layout, depth=d.cavity_depth)
        # Next to the finger case, the thumb case's bottom half belongs to the top above the finger floor's top: its
        # side walls all of it, its floor (the arc's cylinder piece between the side walls) only above the finger
        # plate's underside; between that and the finger floor's top the floor lies inside the case and falls away.
        # Only where the two meet, not where the thumb case's arc comes back up into that margin.
        above_plate_underside = surface.torus(self.finger_layout, depth=d.plate_thickness)
        tc = self.thumb_case
        thumb_floor_arc = tc._placed(tc._band(d.cavity_depth, d.cavity_depth + d.wall, tc.inner_length))

        def meeting(part: Part) -> list:
            return [solid for solid in part.solids() if solid.distance_to(finger_outer) < 1e-3] if part else []

        near = copy.deepcopy(thumb_bottom) & next_to_finger_case
        near_floor = copy.deepcopy(near) & copy.deepcopy(thumb_floor_arc)
        near_sides = copy.deepcopy(near) - copy.deepcopy(thumb_floor_arc)
        join = meeting(copy.deepcopy(near_sides) & copy.deepcopy(above_finger_floor))
        join += meeting(copy.deepcopy(near_floor) & copy.deepcopy(above_plate_underside))
        inside = meeting(
            copy.deepcopy(near_floor) & copy.deepcopy(above_finger_floor) - copy.deepcopy(above_plate_underside)
        )
        if inside:
            thumb_bottom = thumb_bottom - Compound(children=inside)
        above_thumb_floor = self.thumb_case.above(d.cavity_depth).fuse(*join) if join else self.thumb_case.above(d.cavity_depth)
        finger_walls = copy.deepcopy(finger_bottom) & above_finger_floor
        thumb_walls = copy.deepcopy(thumb_bottom) & above_thumb_floor
        finger_floor = finger_bottom - above_finger_floor
        thumb_floor = thumb_bottom - above_thumb_floor
        return (finger_top, thumb_top, finger_walls, thumb_walls), (finger_floor, thumb_floor)

    def _joined_top(self, finger_top: Part, thumb_top: Part, finger_walls: Part, thumb_walls: Part) -> Part:
        """The plates, with their switch holes, and the walls, as one part, making way for the trackball."""
        trackball_case = self.trackball_case
        if trackball_case:
            # The finger case gives way to the ball's shell all the way up. Before the switch holes and the fuse: the
            # cut fails on those.
            shaft = trackball_case.shaft()
            finger_top -= copy.deepcopy(shaft)
            finger_walls -= shaft
        finger_top = _with_switch_holes(finger_top, self.finger_layout)
        thumb_top = _with_switch_holes(thumb_top, self.thumb_layout)
        if trackball_case:
            cup_inside = trackball_case.cup()[2]
            thumb_top, finger_walls, thumb_walls = (
                part - copy.deepcopy(cup_inside) for part in (thumb_top, finger_walls, thumb_walls)
            )
        # Heal before further cuts: the fuse leaves small topology errors that make the next cut fail.
        return (finger_top + thumb_top + finger_walls + thumb_walls).fix()

    def _joined_floors(self, finger_floor: Part, thumb_floor: Part, finger: tuple, thumb: tuple) -> Part:
        """The floors as one part, open inside the skirt."""
        d = self.dimensions
        # Open within the skirt's inside, the very same curves as the skirt's, so the two meet exactly
        inside_skirt = d.prism(self.skirt.inside(copy.deepcopy(finger[1])))
        finger_floor -= copy.deepcopy(inside_skirt)
        return (finger_floor + thumb_floor + self._floor_beside_thumb(finger, thumb)).fix()

    def _floor_beside_thumb(self, finger: tuple, thumb: tuple) -> Part:
        """At the finger case's middle corner, beside the thumb case's free end: the finger case's floor (the torus
        band of its floor) carried on until it meets the thumb case's bottom part (see `_beside_thumb()`)."""
        d = self.dimensions
        return self._beside_thumb(finger, thumb, d.cavity_depth, d.cavity_depth + d.wall)

    def _plate_beside_thumb(self, finger: tuple, thumb: tuple) -> Part:
        """At the finger case's middle corner, beside the thumb case's free end: the finger case's plate (the torus
        band of its plate) carried on until it meets the thumb case's top part (see `_beside_thumb()`)."""
        return self._beside_thumb(finger, thumb, 0, self.dimensions.plate_thickness)

    def _front_wall_beside_thumb(self, finger: tuple, thumb: tuple) -> Part:
        """At the finger case's middle corner, beside the thumb case's free end: the thumb case's front wall carried
        on, from the plate carried on there down to the floor carried on there (see `_beside_thumb()`), until it
        meets the finger case's wall."""
        d = self.dimensions
        return self._beside_thumb(
            finger, thumb, d.plate_thickness, d.cavity_depth, within=self.thumb_case.front_wall_slab()
        )

    def _corner_inside_thumb_room(self) -> Part:
        """The finger case's corner that now lies inside the keyboard: the thumb case's cylindrical room carried on
        past its free end (see `ThumbCase.inside_carried_on()`), up to the finger plate's underside (if the thumb
        case's end wall doesn't bound it first) and down to the finger floor's top."""
        d, layout = self.dimensions, self.finger_layout
        room = self.thumb_case.inside_carried_on()
        room = room & surface.torus(layout, depth=d.cavity_depth) - surface.torus(layout, depth=d.plate_thickness)
        # (the torus comes round again far above: only the case's height)
        room = room & Pos(0, 0, d.max_height / 2) * Box(4 * d.max_height, 4 * d.max_height, d.max_height)
        # Only the piece toward +X, at the corner (the room also comes out on the far side of the arc's axis)
        return max(room.solids(), key=lambda solid: solid.bounding_box().max.X)

    def _beside_thumb(
        self, finger: tuple, thumb: tuple, top_depth: float, bottom_depth: float, within: Part | None = None
    ) -> Part:
        """The finger case's torus band between two depths below its key plane, carried on beside the thumb case's
        free end until it meets the thumb case, between the planes of the outsides of the thumb case's front and back
        walls (and `within`), and only outside the finger case as it is."""
        d, layout = self.dimensions, self.finger_layout
        band = surface.torus(layout, depth=bottom_depth) - surface.torus(layout, depth=top_depth)
        # Around the corner: from column 1 to inside column 3, from inside the finger case to past the thumb
        # case's front (the thumb case's side planes and the thumb case itself bound it there)
        xy = lambda column, row: layout.key_transform(column, row).apply((0, 0, 0))[:2]
        around = d.prism(Polygon(*[xy(c, r) for c, r in ((1, 3), (3, 3), (3, 7), (1, 7))], align=None))
        # (the torus band comes round again far above: only the case's height)
        height = Pos(0, 0, d.max_height / 2) * Box(4 * d.max_height, 4 * d.max_height, d.max_height)
        piece = band & around & height & self.thumb_case.between_sides()
        if within is not None:
            piece = piece & within
        # The thumb case, and the room above its keys
        thumb_plate, thumb_outer, thumb_cavity, above_thumb_plate = (copy.deepcopy(shape) for shape in thumb)
        piece = piece - thumb_plate - thumb_outer - thumb_cavity - above_thumb_plate
        # Only outside the finger case as it is: within it, the band is there already (or left open inside the skirt)
        return piece - copy.deepcopy(finger[0]) - copy.deepcopy(finger[1])

    def _with_trackball_cup(self, top: Part, bottom: Part, thumb_cavity: Part) -> tuple[Part, Part]:
        """The cup's wall and the shell join the top, its foot the bottom. Toward the finger case, the cup's wall
        replaces the finger case; toward the thumb case, the walls fall away and the insides run into each other."""
        cylinder, foot, cup_inside = self.trackball_case.cup()
        # Join the shell and the cup's wall first: their outsides meet flush, which the fuse with the rest can't handle.
        trackball_top = ((cylinder - thumb_cavity) + self.trackball_case.shell()).fix()
        top = (top + trackball_top).fix()
        # Cut before the fuse here too: the cut leaves the fused bottom invalid.
        return top, ((bottom - copy.deepcopy(cup_inside)) + (foot - thumb_cavity)).fix()

    def _finished_bottom(self, top: Part, bottom: Part, finger_outer: Part) -> Part:
        """The bottom clear of the top, with the skirt."""
        # (healed after each cut: the cuts leave small topology errors the next fuse fails on)
        bottom = (bottom - copy.deepcopy(top)).fix()
        # Where the thumb and finger cases meet, the top cuts a bit of floor loose; drop it.
        bottom = max(bottom.solids(), key=lambda solid: solid.volume)
        bottom = self.skirt.added_to(bottom, finger_outer)
        return (bottom - copy.deepcopy(top)).fix()

    def _with_screws(self, top: Part, bottom: Part, finger_outer: Part, thumb_outer: Part) -> tuple[Part, Part]:
        """Both parts with the screws' bosses and holes."""
        lower, upper, holes = self._screw_bosses(copy.deepcopy(finger_outer), copy.deepcopy(thumb_outer), top, bottom)
        top = (((top - copy.deepcopy(lower)) + upper).fix() - copy.deepcopy(holes)).fix()
        return top, ((bottom + lower).fix() - holes).fix()

    def _screw_bosses(
        self, finger_outside: Part, thumb_outside: Part, top: Part, bottom: Part
    ) -> tuple[Part, Part, Part]:
        """The screws' bosses and holes as (lower parts for the bottom, upper parts for the top, holes): in the finger
        case's corners, in the thumb case's gaps after its first and before its last key (midway between its front and
        back walls), and on the trackball's cup if there is one, otherwise in one more corner."""
        trackball_case = self.trackball_case
        obstacles = Compound(children=[
            shape
            for layout in (self.finger_layout, self.thumb_layout)
            for model in (keyswitch.mx_switch_envelope(), key_pcb.single_key_board())
            for shape in place_instances(layout, model, "")
        ] + ([trackball_case.cup()[2]] if trackball_case else []))
        d = self.dimensions
        corners = d.finger_screw_corners + (() if trackball_case else (d.corner_without_trackball,))
        web = self.screws.thumb_web(self.thumb_case.inner_length)
        around = around_a_corner()
        places = [(self.finger_layout, finger_outside, corner, around, None) for corner in corners] + [
            (self.thumb_layout, thumb_outside, (column, 0), [(0, 0)], web)
            for column in sorted({-0.5, self.thumb_layout.keys - 2.5})
        ]
        bosses = self.screws.bosses(places, obstacles, top, bottom)
        if trackball_case:
            bosses.append(trackball_case.screw())
        return tuple(Compound(children=[found[i] for found in bosses]) for i in range(3))

    def _placed(self, location: Location) -> Location:
        """Where a part that is not printed goes: at `location` in the right half, mirrored in the left; moved by
        `offset`."""
        return self.offset * (mirrored(location) if self.left else location)

    def sensor_model(self, simple: bool = False) -> Compound:
        """The trackball's sensor module, for collision checks (not printed); `simple` uses a few boxes around it
        instead."""
        model = trackball_sensor.envelope() if simple else trackball_sensor.model()
        location = self._placed(self.trackball_case.sensor_location())
        return Compound(label="sensor", children=[location * child for child in model.children])

    def trackball_clearance(self) -> Part:
        """The space the ball needs to turn freely (the shell's inner sphere)."""
        case = self.trackball_case
        return self._placed(case.center()) * Sphere(case.trackball.inner_diameter / 2)

    def trackball_ball(self) -> Part:
        """The ball itself, for previews."""
        case = self.trackball_case
        return self._placed(case.center()) * Sphere(case.trackball.diameter / 2)

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
                model = keycap.dsa_keycap_model(size, pressed)
                keycaps += place_instances(
                    layout, model, f"{name} keycap {size:g}u{suffix}", positions, place=self._placed
                )
        return keycaps

    def pcb_models(self) -> list[Part]:
        """Single-key PCBs under every switch, for collision checks (not printed)."""
        return self._on_every_key(key_pcb.single_key_board(), "PCB")

    def _on_every_key(self, model: Shape, name: str) -> list[Shape]:
        """Instances of `model` on every finger and thumb key, labelled "finger <name> c<column> r<row>" etc."""
        return [
            instance
            for layout, part in ((self.finger_layout, "finger"), (self.thumb_layout, "thumb"))
            for instance in place_instances(layout, model, f"{part} {name}", place=self._placed)
        ]
