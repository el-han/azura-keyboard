"""Assembly of the keyboard parts with build123d.
"""
import copy
import math
from collections.abc import Iterable
from typing import Optional

from build123d import Box, Compound, Cylinder, Part, Plane, Polygon, Pos, Rot, Shape, Sphere, extrude

from ..layouts.finger_well import FingerWellLayout
from ..layouts.keys import Kailh
from ..layouts.layout import Layout
from ..layouts.thumb_well import ThumbWellLayout
from . import keyswitch, surface
from ..layouts.transform import Transform
from ..trackball import TrackBall
from .placement import key_location, to_location


def place_instances(
    layout: Layout, shape: Shape, name: str, positions: Optional[Iterable[tuple[float, float]]] = None
) -> list[Shape]:
    """Place an instance of `shape` at every key position (or the given ones), sharing its geometry.

    Exported as children of an assembly, the geometry is written to STEP only once. Each instance is labelled
    "<name> c<column> r<row>".
    """
    instances = []
    for (column, row) in layout.generate_positions() if positions is None else positions:
        instance = copy.copy(shape)
        instance.location = key_location(layout, column, row) * shape.location
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
        """The thumb well: a cylindrical arc of keys, split at the bottom by a flat strip where the right part of the
        arc is shifted outward.
        """
        layout = self.thumb_layout
        k = layout.keyswitch
        columns = [column for (column, _) in layout.generate_positions()]
        length = layout.offset_per_row

        # Wider keys sit on a flat strip at the bottom of the circle, as wide as their combined extra width; the part of
        # the arc past them is shifted by that much (see `ThumbWellLayout.placement_adjust()`).
        shift = sum(layout.extra_width(column, row) for (column, row) in layout.generate_positions())
        left = self._thumb_arc(0, 0, layout.column_angle(min(columns) - 0.5), length)
        right = self._thumb_arc(shift, layout.column_angle(max(columns) + 0.5), 0, length)
        flat = Pos(shift / 2, 0, -self.plate_thickness / 2) * Box(shift, length, self.plate_thickness)

        shape = to_location(layout.layout_place(Transform())) * (left + right + flat)

        shape -= place_all(layout, keyswitch.mounting_socket(k, extra_depth=1, extra_height=3))
        shape -= place_all(layout, keyswitch.switch(k))
        shape -= place_all(layout, keyswitch.single_key_board(extra_spacing=0.02))
        return shape

    def trackball_part(self) -> Part:
        """The trackball well: the lower half of a spherical shell around the ball (no supporting wall yet)."""
        ball = self.trackball
        shell = Sphere(ball.outer_diameter / 2) - Sphere(ball.inner_diameter / 2)
        lower_half = Pos(0, 0, -ball.outer_diameter / 2) * Box(*(ball.outer_diameter,) * 3)
        return Pos(*self.trackball_position) * Pos(0, 0, ball.z_offset) * (shell & lower_half)

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
