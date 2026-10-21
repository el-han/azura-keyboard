"""Assembly of the keyboard parts with build123d.
"""
from build123d import Compound, Part

from ..layouts.finger_well import FingerWellLayout
from ..layouts.keys import Kailh
from ..layouts.layout import Layout
from ..layouts.thumb_well import ThumbWellLayout
from . import keyswitch
from .placement import key_location


def place_all(layout: Layout, shape: Part) -> list[Part]:
    """Place a copy of `shape` at every key position of the layout."""
    return [key_location(layout, column, row) * shape for (column, row) in layout.generate_positions()]


class KeyboardAssembly:
    def __init__(self, columns: int = 6, rows: int = 5):
        k = Kailh()
        self.finger_layout = FingerWellLayout(columns=columns, rows=rows, use_1_5u_keys=False, keyswitch=k)
        self.thumb_layout = ThumbWellLayout(keyswitch=k)

    def switch_plates(self) -> Compound:
        """All switch plates of the finger and thumb wells, without any web between them."""
        plate = keyswitch.plate(self.finger_layout.keyswitch)
        return Compound(
            place_all(self.finger_layout, plate) + place_all(self.thumb_layout, plate)
        )
