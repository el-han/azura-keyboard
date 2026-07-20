from solid2 import hull, polygon
from solid2.core.object_base import OpenSCADObject

from spkb.keyswitch import MX


class Kailh(MX):
    """An encapsulation of all measurements and shapes related to Cherry MX-style switches.
    """
    keyswitch_depth: float = 3
    "From the base of the switch to the mounting plate face"



"""Renderers for approximations of keycap shapes.
"""
dsa_length = 18.15
dsa_1_5_length = 28
dsa_double_length = 37.5
dsa_mid_shrink = 0.15
dsa_top_shrink = 2.9


def dsa_cap(units: float) -> OpenSCADObject:
    """Create an "SA" keycap shape.

    (actually something akin to SA row 3, but with flat tops)

    :param units: the size of the key, in key units
    """
    if units == 1:
        bl2 = dsa_length / 2
        ml2 = dsa_length / 2 - dsa_mid_shrink
        tl2 = dsa_length / 2 - dsa_top_shrink
        key_cap = hull()(
            polygon(((bl2, bl2), (bl2, -bl2), (-bl2, -bl2), (-bl2, bl2)))
            .linear_extrude(height=0.1, twist=0, convexity=0)
            .translate((0, 0, 0.05)),
            polygon(((ml2, ml2), (ml2, -ml2), (-ml2, -ml2), (-ml2, ml2)))
            .linear_extrude(height=0.1, twist=0, convexity=0)
            .translate((0, 0, 2)),
            polygon(((tl2, tl2), (tl2, -tl2), (-tl2, -tl2), (-tl2, tl2)))
            .linear_extrude(height=0.1, twist=0, convexity=0)
            .translate((0, 0, 8.3)),
        )
        return (
            key_cap
            .translate((0, 0, 5))
            .color((220 / 255, 163 / 255, 163 / 255, 1))
        )

    elif units == 2:
        bl2 = dsa_double_length / 2
        bw2 = dsa_length / 2
        ml2 = dsa_double_length / 2 - dsa_mid_shrink
        mw2 = dsa_length / 2 - dsa_mid_shrink
        tl2 = dsa_double_length / 2 - dsa_top_shrink
        tw2 = dsa_length / 2 - dsa_top_shrink
        key_cap = hull()(
            polygon(((bw2, bl2), (bw2, -bl2), (-bw2, -bl2), (-bw2, bl2)))
            .linear_extrude(height=0.1, twist=0, convexity=0)
            .translate((0, 0, 0.05)),
            polygon(((mw2, ml2), (mw2, -ml2), (-mw2, -ml2), (-mw2, ml2)))
            .linear_extrude(height=0.1, twist=0, convexity=0)
            .translate((0, 0, 5)),
            polygon(((tw2, tl2), (tw2, -tl2), (-tw2, -tl2), (-tw2, tl2)))
            .linear_extrude(height=0.1, twist=0, convexity=0)
            .translate((0, 0, 8.3)),
        )
        return (
            key_cap
            .translate((0, 0, 5))
            .color((127 / 255, 159 / 255, 127 / 255, 1))
        )

    elif units == 1.5:
        bl2 = dsa_1_5_length / 2
        bw2 = dsa_length / 2
        ml2 = dsa_1_5_length / 2 - dsa_mid_shrink
        mw2 = dsa_length / 2 - dsa_mid_shrink
        tl2 = dsa_1_5_length / 2 - dsa_top_shrink
        tw2 = dsa_length / 2 - dsa_top_shrink
        key_cap = hull()(
            polygon(((bw2, bl2), (bw2, -bl2), (-bw2, -bl2), (-bw2, bl2)))
            .linear_extrude(height=0.1, twist=0, convexity=0)
            .translate((0, 0, 0.05)),
            polygon(((mw2, ml2), (mw2, -ml2), (-mw2, -ml2), (-mw2, ml2)))
            .linear_extrude(height=0.1, twist=0, convexity=0)
            .translate((0, 0, 5)),
            polygon(((tw2, tl2), (tw2, -tl2), (-tw2, -tl2), (-tw2, tl2)))
            .linear_extrude(height=0.1, twist=0, convexity=0)
            .translate((0, 0, 8.3)),
        )
        return (
            key_cap
            .translate((0, 0, 5))
            .color((240 / 255, 223 / 255, 175 / 255, 1))
        )

    else:
        raise ValueError(f"Unrecognized key size: {units} units")


# To test, use the command line: pipenv run python -m spkb.keycaps
if __name__ == "__main__":
    print("Rendering dsa_cap(1), dsa_cap(1.5), and dsa_cap(2) to keycaps.scad...")
    (
        dsa_cap(1).translate((-30, 0, 0))
        + dsa_cap(1.5)
        + dsa_cap(2).translate((30, 0, 0))
    ).save_as_scad("keycaps.scad")
