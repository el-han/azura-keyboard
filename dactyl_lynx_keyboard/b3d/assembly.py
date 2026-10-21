"""Assembly of the keyboard parts with build123d.
"""
from build123d import Compound, Part, extrude

from ..layouts.finger_well import FingerWellLayout
from ..layouts.keys import Kailh
from ..layouts.layout import Layout
from ..layouts.thumb_well import ThumbWellLayout
from . import keyswitch, surface
from .placement import key_location


def place_all(layout: Layout, shape: Part) -> list[Part]:
    """Place a copy of `shape` at every key position of the layout."""
    return [key_location(layout, column, row) * shape for (column, row) in layout.generate_positions()]


class KeyboardAssembly:
    def __init__(self, columns: int = 6, rows: int = 5):
        k = Kailh()
        self.finger_layout = FingerWellLayout(columns=columns, rows=rows, use_1_5u_keys=False, keyswitch=k)
        self.thumb_layout = ThumbWellLayout(keyswitch=k)

        self.plate_thickness = self.finger_layout.web_thickness
        self.max_height = 120
        "Upper bound for the height of any part (must stay below the far side of the key surface torus)"
        self.finger_straight_columns = (-0.5,)
        "Edges of the finger well that should be straight in top view (see `surface.outline()`)"
        "Upper bound for the height of any part (must stay below the far side of the key surface torus)"

    def switch_plates(self) -> Compound:
        """All switch plates of the finger and thumb wells, without any web between them."""
        plate = keyswitch.plate(self.finger_layout.keyswitch)
        return Compound(
            place_all(self.finger_layout, plate) + place_all(self.thumb_layout, plate)
        )

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
        return shape
