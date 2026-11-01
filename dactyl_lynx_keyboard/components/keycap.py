"""DSA keycaps.
"""
from functools import cache
from pathlib import Path

from build123d import Compound, Pos, Rot

from ..geometry.step import import_step_colored, transformed
from .keyswitch import MX_STEM_TOP, MX_TRAVEL

DSA_KEYCAP_DIR = Path(__file__).resolve().parents[2] / "resources" / "dsa-keycap"
"DSA keycaps from https://github.com/anhthang/dsa-keycap (MIT); modelled Y-up, bottom at Y=0, wide side along X"
DSA_KEYCAP_FILES = {
    1.0: "DSA 1u.step",
    1.25: "DSA 1.25u.step",
    1.5: "DSA 1.5u.step",
    1.75: "DSA 1.75u.step",
    2.0: "DSA 2u.step",
    2.25: "DSA 2.25u.step",
    2.75: "DSA 2.75u.step",
}
DSA_SOCKET_DEPTH = 4.7
"Depth of the keycap's stem socket above its bottom edge (measured from the STEP model)"


@cache
def _dsa_keycap_step(size: float) -> Compound:
    try:
        file_name = DSA_KEYCAP_FILES[size]
    except KeyError:
        raise ValueError(f"No DSA keycap model for {size}u keys") from None
    return import_step_colored(DSA_KEYCAP_DIR / file_name, label=f"DSA {size:g}u")


def dsa_keycap_model(size: float = 1.0, pressed: bool = False) -> Compound:
    """A DSA keycap of the given width (in units) on an MX stem for collision checks (not printed), at rest or
    bottomed out. The wide side runs along X.
    """
    bottom = MX_STEM_TOP - DSA_SOCKET_DEPTH - (MX_TRAVEL if pressed else 0)
    return transformed(_dsa_keycap_step(size), Pos(0, 0, bottom) * Rot(90, 0, 0))
