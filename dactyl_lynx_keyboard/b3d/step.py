"""Importing STEP models with per-solid colors.

`build123d.import_step()` gives a single shape one color (that of its largest face), which turns multi-colored
models such as a keyswitch white. This importer keeps each solid's own color.
"""
from pathlib import Path

from build123d import Color, Compound, Location, Shape, Solid
from OCP.collections import Sequence_TDF_Label
from OCP.Quantity import Quantity_ColorRGBA
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool

_COLOR_TYPES = (XCAFDoc_ColorType.XCAFDoc_ColorSurf, XCAFDoc_ColorType.XCAFDoc_ColorGen)


def import_step_colored(path: str | Path, label: str = "") -> Compound:
    """Import a STEP file as a compound whose children are its solids, each with its own color."""
    doc = TDocStd_Document(TCollection_ExtendedString("XCAF"))
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    if not reader.ReadFile(str(path)) or not reader.Transfer(doc):
        raise ValueError(f"Could not read STEP file {path}")
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def color_of(shape) -> Color | None:
        rgba = Quantity_ColorRGBA()
        if any(color_tool.GetColor(shape, color_type, rgba) for color_type in _COLOR_TYPES):
            rgb = rgba.GetRGB()
            return Color(rgb.Red(), rgb.Green(), rgb.Blue(), rgba.Alpha())
        faces = TopExp_Explorer(shape, TopAbs_FACE)
        while faces.More():
            if any(color_tool.GetColor(faces.Current(), color_type, rgba) for color_type in _COLOR_TYPES):
                rgb = rgba.GetRGB()
                return Color(rgb.Red(), rgb.Green(), rgb.Blue(), rgba.Alpha())
            faces.Next()
        return None

    free_shapes = Sequence_TDF_Label()
    shape_tool.GetFreeShapes(free_shapes)
    solids: list[Shape] = []
    for i in range(1, free_shapes.Length() + 1):
        shape = shape_tool.GetShape_s(free_shapes.Value(i))
        explorer = TopExp_Explorer(shape, TopAbs_SOLID)
        while explorer.More():
            solid = Solid(TopoDS.Solid(explorer.Current()))
            solid.color = color_of(explorer.Current())
            solids.append(solid)
            explorer.Next()
    return Compound(label=label, children=solids)


def transformed(model: Compound, location: Location) -> Compound:
    """Return a copy of a compound from `import_step_colored()` with every solid moved by `location`.

    Colors and labels are kept.
    """
    children = []
    for child in model.children:
        moved = location * child
        moved.color = child.color
        moved.label = child.label
        children.append(moved)
    return Compound(label=model.label, children=children)
