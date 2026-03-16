# report_engine/models/report_models.py
# Pydantic models — mirror of frontend report.models.ts (v2.0)
# Every field name, type, and optional matches the TypeScript source exactly.

from __future__ import annotations
from typing import Any, Literal, Optional, Union, Type
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# STYLE PRIMITIVES
# ─────────────────────────────────────────────


class BaseElementStyle(BaseModel):
    borderStyle: Literal["none", "solid", "dashed", "dotted"] = "none"
    borderWidth: float = 1
    borderColor: str = "#000000"
    fillColor: str = "transparent"
    opacity: float = 1.0


class TextStyle(BaseModel):
    fontFamily: str = "Helvetica"
    fontSize: float = 12
    bold: bool = False
    italic: bool = False
    underline: bool = False
    hAlign: Literal["left", "center", "right"] = "left"
    vAlign: Literal["top", "middle", "bottom"] = "middle"
    color: str = "#000000"
    lineHeight: float = 1.2


# ─────────────────────────────────────────────
# FIELD FORMAT
# ─────────────────────────────────────────────

FieldFormat = Literal[
    "text", "number", "currency", "date", "datetime", "boolean", "image"
]


# ─────────────────────────────────────────────
# BASE ELEMENT
# ─────────────────────────────────────────────


class BaseElement(BaseModel):
    id: str
    type: str
    bandId: str
    x: float
    y: float
    width: float
    height: float
    locked: bool = False
    style: BaseElementStyle = Field(default_factory=BaseElementStyle)


# ─────────────────────────────────────────────
# CONCRETE ELEMENT TYPES
# ─────────────────────────────────────────────


class StaticTextElement(BaseElement):
    type: Literal["staticText"]
    text: str
    textStyle: TextStyle = Field(default_factory=TextStyle)


class RectangleElement(BaseElement):
    type: Literal["rectangle"]
    radius: float = 0


class LineElement(BaseElement):
    type: Literal["line"]
    direction: Literal["horizontal", "vertical", "diagonal"] = "horizontal"


class FieldElement(BaseElement):
    type: Literal["field"]
    fieldName: str
    format: FieldFormat = "text"
    pattern: Optional[str] = None
    nullText: Optional[str] = "—"
    textStyle: TextStyle = Field(default_factory=TextStyle)


class ImageElement(BaseElement):
    type: Literal["image"]
    src: str
    fit: Literal["fill", "contain", "cover"] = "contain"
    altText: Optional[str] = None


# ─────────────────────────────────────────────
# TABLE ELEMENT
# ─────────────────────────────────────────────


class TableColumn(BaseModel):
    key: str
    label: str
    width: float
    align: Literal["left", "center", "right"] = "left"
    format: Optional[FieldFormat] = "text"
    pattern: Optional[str] = None


class TableElement(BaseElement):
    type: Literal["table"]
    columns: list[TableColumn]
    headerStyle: TextStyle = Field(default_factory=TextStyle)
    rowStyle: TextStyle = Field(default_factory=TextStyle)
    rowHeight: float = 24
    headerHeight: float = 26
    altRowColor: Optional[str] = None
    showHeader: bool = True
    dataField: str


# ─────────────────────────────────────────────
# DISCRIMINATED UNION
# ─────────────────────────────────────────────

ReportElement = Union[
    StaticTextElement,
    RectangleElement,
    LineElement,
    FieldElement,
    ImageElement,
    TableElement,
]


# ─────────────────────────────────────────────
# BAND
# ─────────────────────────────────────────────

BandType = Literal[
    "title",
    "pageHeader",
    "columnHeader",
    "detail",
    "columnFooter",
    "pageFooter",
    "summary",
]
BandPrintWhen = Literal["always", "once", "perPage"]


class ReportBand(BaseModel):
    id: str
    type: BandType
    height: float
    elements: list[ReportElement] = Field(default_factory=list)
    dataKey: Optional[str] = None
    printWhen: Optional[BandPrintWhen] = None

    model_config = {"arbitrary_types_allowed": True}


# ─────────────────────────────────────────────
# REPORT MARGINS
# ─────────────────────────────────────────────


class ReportMargins(BaseModel):
    top: float = 20
    right: float = 20
    bottom: float = 20
    left: float = 20


# ─────────────────────────────────────────────
# REPORT MODEL  (top-level payload)
# ─────────────────────────────────────────────


class ReportModel(BaseModel):
    id: str
    name: str
    width: float = 595
    height: float = 842
    margins: ReportMargins = Field(default_factory=ReportMargins)
    bands: list[ReportBand] = Field(default_factory=list)
    data: Optional[dict[str, Any]] = None
    styles: Optional[dict[str, Any]] = None
    isDirty: bool = False

    model_config = {"arbitrary_types_allowed": True}


# ─────────────────────────────────────────────
# DISCRIMINATOR HELPER
# Used by Pydantic to route each element dict to the right class
# ─────────────────────────────────────────────

_ELEMENT_MAP: dict[str, Type[ReportElement]] = {
    "staticText": StaticTextElement,
    "rectangle": RectangleElement,
    "line": LineElement,
    "field": FieldElement,
    "image": ImageElement,
    "table": TableElement,
}


def parse_element(data: dict[str, Any]) -> ReportElement:
    """Deserialise a raw element dict into the correct typed model."""

    el_type = data.get("type")

    if not isinstance(el_type, str):
        raise ValueError("Element missing 'type'")

    cls = _ELEMENT_MAP.get(el_type)

    if cls is None:
        raise ValueError(f"Unknown element type: '{el_type}'")

    return cls(**data)


def parse_report(data: dict) -> ReportModel:
    """
    Full deserialization entry point.
    Handles the discriminated union for elements inside each band.
    """
    bands_raw = data.pop("bands", [])
    report = ReportModel(**data)
    parsed_bands = []
    for band_raw in bands_raw:
        elements_raw = band_raw.pop("elements", [])
        band = ReportBand(**band_raw)
        band.elements = [parse_element(e) for e in elements_raw]
        parsed_bands.append(band)
    report.bands = parsed_bands
    return report
