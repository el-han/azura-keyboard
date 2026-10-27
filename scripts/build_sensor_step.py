"""Build the trackball sensor's STEP model from the pmw3610-pcb KiCad project.

1. Model the PMW3610DM-SUDU sensor and its LM18-LSI lens (not part of KiCad's libraries) and write
   `resources/sensor/PMW3610DM-SUDU_LM18-LSI.step`, in the footprint's frame.
2. Copy the board from the `resources/pmw3610-pcb` submodule to `resources/sensor/`, add that model to the sensor's
   footprint, mark the pin header "do not populate" (the wires are soldered straight to its pads), and point the
   other 3D models at KiCad's STEP library.
3. Export the board with KiCad, without do-not-populate parts, to `resources/sensor/pmw3610_pcb.step`.

Run with `uv run python scripts/build_sensor_step.py` (needs `kicad-cli`).

Dimensions are from the PixArt PMW3610DM-SUDU datasheet: the package outline (figure 2) and the assembly drawing
(figure 4). The datasheet has no outline of the lens, so it is a generous envelope around the sensor's cutout.
"""
import re
import subprocess
from pathlib import Path

from build123d import Box, Color, Compound, Pos, export_step

ROOT = Path(__file__).resolve().parents[1]
SUBMODULE = ROOT / "resources" / "pmw3610-pcb"
OUT = ROOT / "resources" / "sensor"
MODEL_NAME = "PMW3610DM-SUDU_LM18-LSI.step"
MODEL_PLACEHOLDER = "@@SENSOR_MODEL@@"

# Assembly drawing (heights above the navigation surface, sensor on top of the PCB, lens below it)
PCB_TOP_TO_SURFACE = 7.40
PCB_THICKNESS = 1.60
SENSOR_TOP_TO_SURFACE = 9.05
LENS_REFERENCE_TO_SURFACE = 2.40
# Package outline
PACKAGE_LENGTH = 16.20
"Along the rows of pins"
PACKAGE_WIDTH = 9.10
PACKAGE_HEIGHT = 2.91
# Footprint "PMW3610DM-SUDU 16Pin": the board cutout under the sensor, which the package and lens are centred on
CUTOUT_X = (-8.252, 8.948)
LENS_LENGTH = 20.0
LENS_WIDTH = 14.0


def sensor_model() -> Compound:
    """Sensor and lens in the footprint's frame: Z=0 is the top of the board, the lens hangs below it."""
    center_x = sum(CUTOUT_X) / 2
    package_top = SENSOR_TOP_TO_SURFACE - PCB_TOP_TO_SURFACE
    package = Pos(center_x, 0, package_top - PACKAGE_HEIGHT / 2) * Box(PACKAGE_LENGTH, PACKAGE_WIDTH, PACKAGE_HEIGHT)
    package.label, package.color = "PMW3610DM-SUDU", Color(0.05, 0.05, 0.05)
    lens_top = -PCB_THICKNESS
    lens_bottom = -(PCB_TOP_TO_SURFACE - LENS_REFERENCE_TO_SURFACE)
    lens = Pos(center_x, 0, (lens_top + lens_bottom) / 2) * Box(LENS_LENGTH, LENS_WIDTH, lens_top - lens_bottom)
    lens.label, lens.color = "LM18-LSI", Color(0.6, 0.75, 0.9, 0.6)
    return Compound(label="PMW3610 with lens", children=[package, lens])


def patched_board() -> str:
    """The board file with the sensor model added and the other models pointed at KiCad's STEP library."""
    with open(SUBMODULE / "pmw3610_pcb.kicad_pcb") as f:
        board = f.read()
    board = re.sub(r"\$\{KICAD\d+_3DMODEL_DIR\}", "${KICAD9_3DMODEL_DIR}", board)
    board = board.replace('.wrl"', '.step"')
    footprint = board.index('(footprint "pmw3610_pcb:PMW3610DM-SUDU 16Pin"')
    # The footprint's first pad marks where its own properties end; put the model right before it.
    first_pad = board.index("(pad ", footprint)
    board = board[:first_pad] + MODEL_PLACEHOLDER + board[first_pad:]
    header = board.index('(footprint "Connector_PinHeader_2.54mm:')
    attr = board.index("(attr through_hole", header)
    if not board.startswith("(attr through_hole dnp", attr):
        board = board[:attr] + "(attr through_hole dnp" + board[attr + len("(attr through_hole"):]
    model = (
        f'(model "${{KIPRJMOD}}/{MODEL_NAME}"\n'
        "\t\t\t(offset (xyz 0 0 0))\n\t\t\t(scale (xyz 1 1 1))\n\t\t\t(rotate (xyz 0 0 0))\n\t\t)\n\t\t"
    )
    return board.replace(MODEL_PLACEHOLDER, model)


if __name__ == "__main__":
    export_step(sensor_model(), OUT / MODEL_NAME)
    board_path = OUT / "pmw3610_pcb.kicad_pcb"
    with open(board_path, "w") as f:
        f.write(patched_board())
    subprocess.run(
        ["kicad-cli", "pcb", "export", "step", "-f", "--no-dnp", "-o", OUT / "pmw3610_pcb.step", board_path],
        check=True,
    )
