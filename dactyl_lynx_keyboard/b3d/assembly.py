"""Assembly of the keyboard parts with build123d.
"""
import copy
import math
from collections.abc import Iterable
from typing import Optional

from build123d import Box, Compound, Cylinder, Location, Part, Plane, Polygon, Pos, Rot, Shape, Sphere, extrude

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
        "Edges of the finger well that should be straight in top view (see `surface.outline()`)"
        "Upper bound for the height of any part (must stay below the far side of the key surface torus)"

    def finger_part(self) -> Part:
        """The finger well: plate on the key surface with switch sockets."""
        layout = self.finger_layout
        k = layout.keyswitch
        footprint = surface.outline(layout, straight_columns=self.finger_straight_columns)

        plate = (
            extrude(footprint, self.max_height)
            & (surface.torus(layout, depth=self.plate_thickness) - surface.torus(layout))
        )
        # Drop slivers from where the torus turns over beyond the footprint; keep the key surface itself.
        shape = max(plate.solids(), key=lambda solid: solid.volume)

        # Extend the hole well beyond both sides of the shell: when it ends close to the curved surfaces, OCCT
        # sometimes keeps the cut-out piece as a separate solid.
        shape -= place_all(layout, keyswitch.mounting_socket(k, extra_depth=1, extra_height=3))
        shape -= place_all(layout, keyswitch.switch(k))
        shape -= place_all(layout, keyswitch.single_key_board(extra_spacing=0.02))
        shape -= self.trackball_clearance()
        return shape

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
