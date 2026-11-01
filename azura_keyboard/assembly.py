"""The keyboard that gets built: its two halves.
"""
from .case.keyboard import Keyboard
from .components.trackball import TrackBall

HALVES = {
    "right": Keyboard(side="right", thumb_keys=3, trackball=TrackBall()),
    "left": Keyboard(side="left", thumb_keys=5),
}
