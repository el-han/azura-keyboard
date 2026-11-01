"""M2.5 screws from below into heat-set inserts, in bosses inside the case.
"""
import copy
import math
from collections.abc import Iterable

from build123d import Box, Compound, Cylinder, Part, Pos

from ..geometry.key_layout import KeyLayout
from ..geometry.placement import to_location
from .dimensions import Dimensions


class Screws:
    def __init__(self, dimensions: Dimensions):
        self.dimensions = dimensions

    @staticmethod
    def column(bottom: float, top: float, radius: float) -> Part:
        return Pos(0, 0, (bottom + top) / 2) * Cylinder(radius, top - bottom)

    def thumb_web(self, inner_length: float) -> Part:
        """A web between the thumb keys that ties a boss's upper part to the plate and the front wall; behind it, the
        wires pass. It reaches into the plate and the middle of the front wall."""
        d = self.dimensions
        split = -d.cavity_depth + d.wall
        web_end = inner_length / 2 + d.wall / 2
        web_top = -d.plate_thickness + 1
        return Pos(0, -web_end / 2, (split + web_top) / 2) * Box(d.wall, web_end, web_top - split)

    def bosses(
        self,
        places: Iterable[tuple[KeyLayout, Part, tuple[float, float], list[tuple[int, int]], Part | None]],
        obstacles: Compound,
        top: Part,
        bottom: Part,
    ) -> list[tuple[Part, Part, Part]]:
        """Bosses for screws at the given places, each as (lower part for the bottom, upper part for the top, holes).

        A place is (layout, the case's outside there, column and row, offsets to try in that frame, web or None).

        A boss stands along the key surface's normal at its place, like the walls, at the first offset where it stays
        `screw_margin` inside the case's outside and clear of the `obstacles`; it may reach into the walls. Its lower part
        reaches from inside the floor to a wall's thickness above it and holds the screw's counterbore and clearance
        hole, so the screw goes in from below; its upper part reaches to just below the plate and holds the insert.
        None of its faces lies on one of the case's curved faces.
        """
        d, column = self.dimensions, self.column
        boss, head = d.screw_boss / 2, d.screw_head[0] / 2
        underside = -(d.cavity_depth + d.wall)
        bottom_z, split, top_z = underside + 1, -d.cavity_depth + d.wall, -d.plate_thickness - 0.5
        bosses = []
        for layout, outside, place, offsets, web in places:
            at_place = to_location(layout.key_transform(*place))
            for dx, dy in offsets:
                frame = at_place * Pos(dx, dy, 0)
                whole = frame * column(bottom_z, top_z, boss)
                stray = frame * column(bottom_z, top_z, boss + d.screw_margin) - copy.deepcopy(outside)
                if stray is not None and stray.solids() and stray.volume > 0.01:
                    continue
                if (frame * (column(bottom_z, top_z, boss) + web) if web else whole).distance_to(obstacles) < 0.3:
                    continue
                # Each part holds on to its part of the case
                lower = frame * column(bottom_z, split, boss)
                upper = frame * (column(split, top_z, boss) + web if web else column(split, top_z, boss))
                holes = frame * (
                    column(underside - 1, underside + d.screw_head[1], head)
                    + column(underside - 1, split, d.screw_hole / 2)
                    + column(split, split + d.insert_hole[1], d.insert_hole[0] / 2)
                )
                if all(
                    (held := part & copy.deepcopy(holder)) is not None and held.solids() and held.volume > 10
                    for part, holder in ((lower, bottom), (upper, top))
                ):
                    break
            else:
                raise ValueError(f"No room for the screw at {place}")
            bosses.append((lower, upper, holes))
        return bosses


def around_a_corner() -> list[tuple[int, int]]:
    """Places around a corner (in its frame, 1 mm apart, up to 15 mm away), nearest first."""
    return sorted(
        [(dx, dy) for dx in range(-15, 16) for dy in range(-15, 16) if math.hypot(dx, dy) <= 15],
        key=lambda offset: math.hypot(*offset),
    )
