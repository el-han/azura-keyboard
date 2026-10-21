"""The layout of a finger well.
"""
import math
import operator
from collections.abc import Iterable
from functools import reduce
from itertools import chain
from typing import Optional, Tuple

from solid2.core.object_base import OpenSCADObject
from solid2 import sphere, hull

from spkb.keyswitch import Keyswitch

from .layout import Layout, XYAdjustCallback
from .keys import Kailh


class FingerWellLayout(Layout):
    """The layout of a finger well.
    """
    def __init__(self, columns: int = 6, rows: int = 5, use_1_5u_keys: bool = True, keyswitch: Keyswitch = Kailh):
        super(FingerWellLayout, self).__init__(columns=columns, rows=rows, keyswitch=keyswitch)

        self.use_1_5u_keys = use_1_5u_keys

        self.placement_transform = (0, 0, 1.6 + 3.0)

        self.positions_to_skip = ((0, 4), (1, 4), (2, 4))

    def column_adjust(self, column: float) -> float:
        """Adjust the effective column number of a given column to account for 1.5u keys on the
        outside columns.

        :param column: the column number to adjust
        """
        if self.use_1_5u_keys and column >= 5:
            return column + (column - 4) * 0.25
        else:
            return column

    def row_angle(self, row: float) -> float:
        """Calculate the X rotation angle for the given row.

        :param row: the row number to rotate for
        """
        return math.degrees(self.rad_per_row * (2 - row))

    def column_angle(self, column: float) -> float:
        """Calculate the Y rotation angle for the given column.

        :param column: the row number to rotate for
        """
        return math.degrees(self.rad_per_col * (2.5 - column))

    def placement_adjust(self, column: float, row: float, shape: OpenSCADObject) -> OpenSCADObject:
        """Adjust the position of the given key/location in the layout.

        :param column: the column to place the key in
        :param row: the row to place the key in
        :param shape: the shape to place
        """
        shape = shape.down(self.row_radius)
        shape = shape.rotate(-self.row_angle(3), (1, 0, 0))
        shape = shape.up(self.row_radius)
        shape = shape.translate((0.0, -1*self.offset_per_row, 0.0))

        shape = shape.down(self.column_radius)
        shape = shape.rotate(-self.column_angle(4), (0, 1, 0))
        shape = shape.up(self.column_radius)
        shape = shape.translate((1.5*self.offset_per_col, 0.0, 0.0))

        # shape = shape.rotate(10, (0,0,1))
        
        return shape.translate((0.5*self.offset_per_col, 0.0, 0.0))

    def generate_positions(self) -> Iterable[Tuple[float, float]]:
        """Generate the list of locations within the layout.

        Override this to change the list of locations, or set `positions_to_skip` to filter out certain positions.
        """
        positions = []
        
        for column in range(self.columns):
            for row in range(self.rows):
                if (column, row) in self.positions_to_skip:
                    continue
                    
                # shift rows for middle finger and pinky
                if column == 2:
                    row += -0.25
                elif column >=4:
                    row += 0.25
                    
                positions.append((column, row))

        return positions

    def layout_place(self, shape: OpenSCADObject) -> OpenSCADObject:
        """Place the layout.

        :param shape: the shape to place
        """
        return shape \
            .up(self.web_thickness) \
            .translate(self.placement_transform)


    def plate_node_positions(self) -> Iterable[Tuple[float, float]]:
        positions = super().plate_node_positions()
        positions.extend([
            (-0.75, -0.75),
            (-0.50, -0.75),
            (-0.25, -0.75),
            (0.00, -0.75),
            (0.25, -0.75),
            (0.50, -0.75),
            (0.75, -0.75),
            (1.00, -0.75),
            (1.25, -0.75),
            (1.50, -0.75),
        ])
        positions.extend([
            (3.50, -0.50),
            (3.75, -0.50),
            (4.00, -0.50),
            (4.25, -0.50),
            (4.50, -0.50),
            (4.75, -0.50),
            (5.00, -0.50),
            (5.25, -0.50),
            (5.50, -0.50),
        ])
        positions.extend([
            (2.50, -0.75),
            (2.75, -0.75),
            (3.00, -0.75),
            (3.25, -0.75),
            (3.50, -0.75),
            (3.75, -0.75),
            (4.00, -0.75),
            (4.25, -0.75),
            (4.50, -0.75),
            (4.75, -0.75),
            (5.00, -0.75),
            (5.25, -0.75),
            (5.50, -0.75),
        ])
        positions.extend([
            (1.75, 3.50),
            (2.00, 3.50),
            (2.25, 3.50),
        ])
        positions.extend([
            (2.50, 4.75),
            (2.75, 4.75),
            (3.00, 4.75),
            (3.25, 4.75),
        ])
        return positions
