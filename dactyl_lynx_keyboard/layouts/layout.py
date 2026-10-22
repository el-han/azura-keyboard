"""Defines the base class for key layouts.
"""
import math
from collections.abc import Iterable, Sequence
from typing import Tuple

from .keys import Kailh, Keyswitch
from .transform import Transform


class Layout:
    """The base implementation of a layout manager.

    This can generate a grid of key positions.
    """
    def __init__(self, columns: int = 6, rows: int = 5, keyswitch: Keyswitch = Kailh()):
        """Create a layout manager.

        :param columns: the number of columns in the layout

        :param rows: the number of rows in the layout
        """

        self.rows = rows
        self.columns = columns

        self.sa_profile_key_height = 12.7
        """Approx. height from top of the plate to the top of the shortest
        keycap in an SA profile? Really not sure."""

        self.rad_per_row = math.pi / 12
        "Cupping amount, in radians per row"
        self.rad_per_col = math.pi / 36
        "Cupping amount, in radians per column"

        self.thumb_switch_clearance = 12
        """Clearance for the depth of the switch - only needed for the bottom
        right 2x key and the top right 1x key"""

        self.keyswitch = keyswitch

        self.cap_top_height = self.sa_profile_key_height

        self.web_thickness = self.keyswitch.keyswitch_depth

        # self.offset_per_row = self.keyswitch.plate_size().y
        self.offset_per_row = 17.5
        # self.offset_per_col = self.keyswitch.plate_size().x
        self.offset_per_col = 20

        self.positions_to_skip: Sequence[Tuple[float, float]] = ()
        "A sequence of positions in the layout to skip when generating positions."

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

        Override this to change the list of locations, or set `positions_to_skip` to filter out certain positions.
        """
        return (
            (column, row)
            for row in range(self.rows)
            for column in range(self.columns)
            if (column, row) not in self.positions_to_skip
        )

    def plate_node_positions(self) -> list[Tuple[float, float]]:
        key_positions = self.generate_positions()
        #return key_positions

        positions = []
        for (column, row) in key_positions:
            for col_offset in (-0.5, -0.25, 0, 0.25, 0.5):
                for row_offset in (-0.5, -0.25, 0, 0.25, 0.5):
                    if (column+col_offset, row+row_offset) in positions:
                        continue
                    positions.append((column+col_offset, row+row_offset))
        return positions

    def column_adjust(self, column: float) -> float:
        """Override this method to adjust the effective column number of a given column.

        :param column: the column number to adjust
        """
        return column

    def row_adjust(self, row: float) -> float:
        """Override this method to adjust the effective row number of a given row.

        :param row: the row number to adjust
        """
        return row

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
        row = self.row_adjust(row)
        row_angle = self.row_angle(row)

        row_placed = Transform() \
            .down(self.row_radius) \
            .rotate(row_angle, (1, 0, 0)) \
            .up(self.row_radius)

        column = self.column_adjust(column)
        column_angle = self.column_angle(column)

        column_placed = row_placed \
            .down(self.column_radius) \
            .rotate(column_angle, (0, 1, 0)) \
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

    def plate_edge_nodes(self) -> Iterable[Tuple[float, float, bool, bool, bool, bool]]:
        edge_nodes = []
        plate_nodes = self.plate_node_positions()

        # Find first corner node (top left)
        for (column, row) in plate_nodes:
            if (column-0.25, row-0.25) not in plate_nodes:
                edge_nodes.append((column, row, True, True, False, False))
                break

        def node_is_top(column, row) -> bool:
            if (column, row) in plate_nodes and (column, row-0.25) not in plate_nodes:
                return True
            if (column, row) in plate_nodes and (column-0.25, row-0.25) not in plate_nodes:
                return True
            if (column, row) in plate_nodes and (column+0.25, row-0.25) not in plate_nodes:
                return True
            return False

        def node_is_bottom(column, row) -> bool:
            if (column, row) in plate_nodes and (column, row+0.25) not in plate_nodes:
                return True
            if (column, row) in plate_nodes and (column-0.25, row+0.25) not in plate_nodes:
                return True
            if (column, row) in plate_nodes and (column+0.25, row+0.25) not in plate_nodes:
                return True
            return False

        def node_is_left(column, row) -> bool:
            if (column, row) in plate_nodes and (column-0.25, row) not in plate_nodes:
                return True
            if (column, row) in plate_nodes and (column-0.25, row-0.25) not in plate_nodes:
                return True
            if (column, row) in plate_nodes and (column-0.25, row+0.25) not in plate_nodes:
                return True
            return False

        def node_is_right(column, row) -> bool:
            if (column, row) in plate_nodes and (column+0.25, row) not in plate_nodes:
                return True
            if (column, row) in plate_nodes and (column+0.25, row-0.25) not in plate_nodes:
                return True
            if (column, row) in plate_nodes and (column+0.25, row+0.25) not in plate_nodes:
                return True
            return False

        def find_next_edge_node(column, row) -> Tuple[float, float, bool, bool, bool, bool]:
            try_nodes = [
                (column+0.25, row),
                (column, row+0.25),
                (column-0.25, row),
                (column, row-0.25),
            ]

            for (column, row) in try_nodes:
                if node_is_top(column, row) or node_is_bottom(column, row) or node_is_left(column, row) or node_is_right(column, row):
                    found_node = (column, row, node_is_left(column, row), node_is_top(column, row), node_is_right(column, row), node_is_bottom(column, row))
                    if found_node in edge_nodes:
                        continue
                    return found_node

        while True:
            (current_column, current_row, _, _, _, _) = edge_nodes[-1]
            next_node = find_next_edge_node(current_column, current_row)

            if next_node is None:
                break

            if next_node == edge_nodes[0]:
                break

            edge_nodes.append(next_node)

        edge_nodes.append(edge_nodes[0])

        return edge_nodes
