"""One half of a keyboard: puts the parts of the case together and places the components on it.
"""
import copy
from typing import Optional

from build123d import Compound, Kind, Location, Part, Plane, Shape, Sphere, mirror, offset

from ..components import key_pcb, keycap, keyswitch, trackball_sensor
from ..components.keyswitch import Keyswitch
from ..components.trackball import TrackBall
from ..geometry import surface
from ..geometry.key_layout import KeyLayout
from ..geometry.placement import mirrored, place_all, place_instances
from .dimensions import CaseDimensions
from .finger_case import FingerCase, FingerLayout
from .passages import thumb_passage
from .screws import Screws, around_a_corner
from .skirt import Skirt
from .thumb_case import ThumbCase, ThumbLayout
from .trackball_case import TrackballCase

JOIN_MARGIN = 15
"How far past the finger case the thumb case's bottom half is joined to the top (see `Keyboard.case()`)"
FINGER_SCREW_CORNERS = ((-0.5, -0.75), (5.5, -0.75), (2.5, 4.75))
"Corners of the finger case's outline (column, row) with a screw"
CORNER_WITHOUT_TRACKBALL = (-0.5, 3.5)
"One more such corner where there is no trackball cup to take a screw (in the mirrored left half, front right)"


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
        rows: int = 5,
    ):
        if side not in ("left", "right"):
            raise ValueError(f"side must be 'left' or 'right', not {side!r}")
        self.side = side
        "Which half: everything is designed as the right half; the left half's case is its mirror image"
        self.offset = Location()
        "Where the parts that are not printed are moved to (e.g. to show both halves side by side)"
        self.dimensions = CaseDimensions()
        k = Keyswitch()
        self.finger_layout = FingerLayout(columns=columns, rows=rows, keyswitch=k)
        # Low enough that the finger case's bottom half rests on the table
        self.finger_layout.placement_transform = (0, 0, 12.05)
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

        Where the finger and thumb cases overlap, their walls fall away and their insides run into each other: each part
        loses whatever lies inside the other's cavity (for the plates, only below the other plate), and the finger
        parts also give way to the thumb parts.

        The top joins both key plates: next to the finger case, everything of the thumb case's bottom half that rises
        above the top edge of the finger case's floor belongs to the top as well, which ties the two plates
        together.
        """
        d, trackball_case = self.dimensions, self.trackball_case
        finger_plate, finger_outer, finger_cavity, finger_footprint = self.finger_case.shapes()
        thumb_plate, thumb_outer, thumb_cavity, thumb_plate_region = self.thumb_case.shapes()
        below_finger_plate = finger_cavity - surface.torus(self.finger_layout, depth=d.plate_thickness)
        below_thumb_plate = thumb_cavity - thumb_plate_region

        thumb_top = thumb_plate - below_finger_plate
        # Cut with copies: OCCT can alter a boolean's tool shape.
        thumb_bottom = thumb_outer - thumb_cavity - finger_cavity - copy.deepcopy(thumb_top)
        thumb_parts = copy.deepcopy(thumb_top) + copy.deepcopy(thumb_bottom)
        finger_top = finger_plate - below_thumb_plate - thumb_parts
        finger_bottom = finger_outer - finger_cavity - thumb_cavity - copy.deepcopy(thumb_parts)

        next_to_finger_case = d.prism(offset(finger_footprint, JOIN_MARGIN, kind=Kind.ARC))
        # The walls (everything above the cavities' floor) belong to the top, the floors to the bottom.
        above_finger_floor = surface.torus(self.finger_layout, depth=d.cavity_depth)
        # Next to the finger case, the thumb case's bottom half belongs to the top above the finger floor's top edge:
        # only where the two meet, not where the thumb case's arc comes back up into that margin.
        join = copy.deepcopy(thumb_bottom) & next_to_finger_case & copy.deepcopy(above_finger_floor)
        join = [solid for solid in join.solids() if solid.distance_to(finger_outer) < 1e-3]
        above_thumb_floor = self.thumb_case.above(d.cavity_depth).fuse(*join)
        finger_walls = copy.deepcopy(finger_bottom) & above_finger_floor
        thumb_walls = copy.deepcopy(thumb_bottom) & above_thumb_floor
        finger_floor = finger_bottom - above_finger_floor
        thumb_floor = thumb_bottom - above_thumb_floor

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
        top = (finger_top + thumb_top + finger_walls + thumb_walls).fix()
        # The finger floor is open inside the skirt.
        skirt_outline = self.skirt.outline(finger_outer)
        inside_skirt = d.prism(offset(skirt_outline, -d.wall))
        finger_floor -= copy.deepcopy(inside_skirt)
        bottom = (finger_floor + thumb_floor).fix()
        # The thumb case's floor reaches back to the skirt, and no further toward -X than the skirt's outside
        extension = (self.thumb_case.floor_extension() & self.skirt.beside(skirt_outline)) - inside_skirt
        bottom = (bottom + (extension - finger_cavity - thumb_cavity)).fix()
        if trackball_case:
            # The cup's wall and the shell join the top, its foot the bottom. Toward the finger case, the cup's wall
            # replaces the finger case; toward the thumb case, the walls fall away and the insides run into each other.
            cylinder, foot, cup_inside = trackball_case.cup()
            # Join the shell and the cup's wall first: their outsides meet flush, which the fuse with the rest can't
            # handle.
            trackball_top = ((cylinder - thumb_cavity) + trackball_case.shell()).fix()
            top = (top + trackball_top).fix()
            # Cut before the fuse here too: the cut leaves the fused bottom invalid.
            bottom = ((bottom - copy.deepcopy(cup_inside)) + (foot - thumb_cavity)).fix()

        bottom -= copy.deepcopy(top)
        # Where the thumb and finger cases meet, the top cuts a bit of floor loose; drop it.
        bottom = max(bottom.solids(), key=lambda solid: solid.volume)
        bottom = self.skirt.added_to(bottom, finger_outer)
        bottom = bottom - copy.deepcopy(top)

        passages = thumb_passage(
            self.finger_case.shapes()[1], self.thumb_case.shapes()[1], finger_cavity, thumb_cavity, d
        )
        if trackball_case:
            for slot in trackball_case.passage():
                passages += slot
        top, bottom = top - copy.deepcopy(passages), bottom - passages
        # A passage can cut off the bit of wall between it and the bottom part; drop it.
        top = max(top.solids(), key=lambda solid: solid.volume)

        hook, pocket = self.thumb_case.hook()
        top, bottom = (top - pocket).fix(), (bottom + hook).fix()

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
        corners = FINGER_SCREW_CORNERS + (() if trackball_case else (CORNER_WITHOUT_TRACKBALL,))
        web = self.screws.thumb_web(self.thumb_case.inner_length)
        around = around_a_corner()
        places = [(self.finger_layout, finger_outside, corner, around, None) for corner in corners] + [
            (self.thumb_layout, thumb_outside, (column, 0), [(0, 0)], web)
            for column in sorted({-0.5, self.thumb_layout.keys - 2.5})
        ]
        bosses = self.screws.bosses(places, obstacles, top, bottom)
        if trackball_case:
            bosses.append(trackball_case.screw(self.screws))
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
