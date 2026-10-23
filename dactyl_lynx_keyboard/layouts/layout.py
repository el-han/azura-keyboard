"""Defines the base class for key layouts.
"""
import math
from collections.abc import Iterable, Sequence
from typing import Tuple

from .keys import Keyswitch
from .transform import Transform


class Layout:
    """The base implementation of a layout manager.

    This can generate a grid of key positions.
    """
    def __init__(self, columns: int = 6, rows: int = 5, keyswitch: Keyswitch = Keyswitch()):
        """Create a layout manager.

        :param columns: the number of columns in the layout

        :param rows: the number of rows in the layout
        """

        self.rows = rows
        self.columns = columns

        self.rad_per_row = math.pi / 12
        "Cupping amount, in radians per row"
        self.rad_per_col = math.pi / 36
        "Cupping amount, in radians per column"

        self.keyswitch = keyswitch

        self.cap_top_height = 12.7
        """Approx. height from top of the plate to the top of the shortest keycap in an SA profile; the key spacing
        below is measured there."""

        self.plate_thickness = self.keyswitch.plate_thickness

        self.offset_per_row = 17.5
        self.offset_per_col = 20

        self.unit_width = 19
        "The width of a 1u key position (mm), used to space out wider keys"

        self.outline_corners: Sequence[Tuple[float, float]] = (
            (-0.5, -0.5), (-0.5, rows - 0.5), (columns - 0.5, rows - 0.5), (columns - 0.5, -0.5)
        )
        """Corners of the plate's outline as (column, row) positions, counter-clockwise in top view. The edges between
        them run along the key surface."""

    @property
    def row_radius(self) -> float:
        return (
            (self.offset_per_row / 2)
            / (math.sin(self.rad_per_row / 2))
        ) + self.cap_top_height

    @property
    def column_radius(self) -> float:
        return (
            (self.offset_per_col / 2)
            / (math.sin(self.rad_per_col / 2))
        ) + self.cap_top_height

    def generate_positions(self) -> Iterable[Tuple[float, float]]:
        """Generate the list of locations within the layout.

        Override this to change the list of locations.
        """
        return ((column, row) for row in range(self.rows) for column in range(self.columns))

    def key_size(self, column: float, row: float) -> float:
        """Override this method to give the key at the given position a different width, in keyboard units (1u).

        :param column: the column of the key
        :param row: the row of the key
        """
        return 1.0

    def placement_adjust(self, column: float, row: float, transform: Transform) -> Transform:
        """Override this method to adjust the position of the given key/location in the layout.

        :param column: the column to place the key in

        :param row: the row to place the key in

        :param transform: the placement so far
        """
        return transform

    def row_angle(self, row: float) -> float:
        """Calculate the X rotation angle for the given row.

        :param row: the row number to rotate for
        """
        return math.degrees(self.rad_per_row * -row)

    def column_angle(self, column: float) -> float:
        """Calculate the Y rotation angle for the given column.

        :param column: the row number to rotate for
        """
        return math.degrees(self.rad_per_col * -column)

    def key_transform(self, column: float, row: float) -> Transform:
        """Return the placement of a key (or other shape) in the layout.

        :param column: the column to place the key in

        :param row: the row to place the key in
        """
        row_placed = Transform() \
            .down(self.row_radius) \
            .rotate(self.row_angle(row), (1, 0, 0)) \
            .up(self.row_radius)

        column_placed = row_placed \
            .down(self.column_radius) \
            .rotate(self.column_angle(column), (0, 1, 0)) \
            .up(self.column_radius)

        return self.layout_place(
            self.placement_adjust(column, row, column_placed)
        )

    def layout_place(self, transform: Transform) -> Transform:
        """Place the layout.

        Override to adjust the placement of the entire layout.

        :param transform: the placement so far
        """
        return transform
