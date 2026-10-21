"""Assembly of the keyboard parts with build123d.
"""
from build123d import Compound, Face, Kind, Part, Polygon, extrude, offset

from ..layouts.finger_well import FingerWellLayout
from ..layouts.keys import Kailh
from ..layouts.layout import Layout
from ..layouts.thumb_well import ThumbWellLayout
from . import keyswitch, surface
from .placement import key_location


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

        self.plate_thickness = self.finger_layout.web_thickness
        self.wall_thickness = 3
        self.max_height = 120
        "Upper bound for the height of any part (must stay below the far side of the key surface torus)"
        self.wall_clearance = 0.5
        "Gap between the walls and anything mounted at a key position"
        self.outline_smoothing = 3
        "Radius for filling small notches in the footprint"
        "Upper bound for the height of any part (must stay below the far side of the key surface torus)"

    def switch_plates(self) -> Compound:
        """All switch plates of the finger and thumb wells, without any web between them."""
        plate = keyswitch.plate(self.finger_layout.keyswitch)
        return Compound(
            place_all(self.finger_layout, plate) + place_all(self.thumb_layout, plate)
        )

    def inner_footprint(self, layout: Layout) -> Face:
        """The area enclosed by the walls, projected onto the XY plane.

        This is the layout's plate outline, grown where needed so that every key's switch plate and PCB clears the
        walls.
        """
        k = layout.keyswitch
        plate_half = k.plate_size().x / 2, k.plate_size().y / 2
        pcb = keyswitch.single_key_board(extra_spacing=0.02).bounding_box()
        key_corners = [
            (sx * plate_half[0], sy * plate_half[1], z)
            for z in (0, -self.plate_thickness) for sx in (-1, 1) for sy in (-1, 1)
        ] + [
            (x, y, z)
            for z in (pcb.min.Z, pcb.max.Z) for x in (pcb.min.X, pcb.max.X) for y in (pcb.min.Y, pcb.max.Y)
        ]

        footprint = surface.outline(layout)
        for (column, row) in layout.generate_positions():
            transform = layout.key_transform(column, row)
            projected = [transform.apply(corner)[:2] for corner in key_corners]
            footprint += Polygon(*_convex_hull_2d(projected), align=None)

        footprint = offset(footprint, self.outline_smoothing, kind=Kind.ARC)
        footprint = offset(footprint, -self.outline_smoothing, kind=Kind.ARC)
        return offset(footprint, self.wall_clearance, kind=Kind.ARC)

    def finger_part(self) -> Part:
        """The finger well: plate on the key surface, walls down to the ground, and switch sockets."""
        layout = self.finger_layout
        k = layout.keyswitch
        inner = self.inner_footprint(layout)
        outer = offset(inner, self.wall_thickness, kind=Kind.ARC)

        above_plate = surface.torus(layout)
        plate = (
            extrude(outer, self.max_height)
            & (surface.torus(layout, depth=self.plate_thickness) - above_plate)
        )
        # Drop slivers from where the torus turns over beyond the footprint; keep the key surface itself.
        plate = max(plate.solids(), key=lambda solid: solid.volume)
        # Stop the walls at the plate's top, so they can't reach the far side of the torus where it turns over.
        walls = extrude(outer - inner, plate.bounding_box().max.Z) - above_plate

        # No separate switch plates: the shell is already plate-thick at every key, and a flat plate's underside
        # would only touch the curved one tangentially.
        shape = plate + walls
        # Extend the hole well beyond both sides of the shell: when it ends close to the curved surfaces, OCCT
        # sometimes keeps the cut-out piece as a separate solid.
        shape -= place_all(layout, keyswitch.mounting_socket(k, extra_depth=1, extra_height=3))
        shape -= place_all(layout, keyswitch.switch(k))
        shape -= place_all(layout, keyswitch.single_key_board(extra_spacing=0.02))
        # The walls end on the same torus as the plate's top, which can leave zero-volume slivers along that edge.
        return Part(Compound([solid for solid in shape.solids() if solid.volume > 1e-3]).wrapped)
