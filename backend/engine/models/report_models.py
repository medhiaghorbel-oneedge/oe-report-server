# engine/models/report_models.py
# Pydantic mirror of frontend report.models.ts (Phase 8.0 aligned).
# Every field name, type, and optional matches the TypeScript source exactly.
# v3.0 — Phase 8.0 model alignment.

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
    """
    Shared text/font style used by StaticTextElement, FieldElement,
    and TableElement header/row styles.
    Matches TypeScript TextStyle exactly.
    """

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
    """
    Data-bound field — renders a resolved value from report.data at PDF time.
    Replaces the old PlaceholderElement. Frontend type: 'field'.
    """

    type: Literal["field"]
    fieldName: str  # dot-notation path: "invoice.total"
    format: FieldFormat = "text"
    pattern: Optional[str] = None
    nullText: Optional[str] = "—"
    textStyle: TextStyle = Field(default_factory=TextStyle)


class ImageElement(BaseElement):
    """Image element — renders a URL, data-path string, or base64 image."""

    type: Literal["image"]
    src: str
    fit: Literal["fill", "contain", "cover"] = "contain"
    altText: Optional[str] = None


# ─────────────────────────────────────────────
# TABLE ELEMENT
# ─────────────────────────────────────────────


class TableColumn(BaseModel):
    """
    One column in a TableElement.
    `key`     — flat key into each row object (e.g. "description", "total")
    `label`   — column header text shown in the PDF
    `format`  — how cell values are formatted
    `pattern` — optional format pattern (e.g. "$#,##0.00")
    """

    key: str
    label: str
    width: float
    align: Literal["left", "center", "right"] = "left"
    format: Optional[FieldFormat] = "text"
    pattern: Optional[str] = None


class TableElement(BaseElement):
    type: Literal["table"]
    columns: list[TableColumn]
    headerHeight: float = 28
    rowHeight: float = 24
    # Full TextStyle for header and data cells
    headerStyle: TextStyle = Field(default_factory=TextStyle)
    rowStyle: TextStyle = Field(default_factory=TextStyle)
    # Background colours (separate from TextStyle — TextStyle has no background)
    headerBackground: str = "#2E6DA4"
    rowBackground: str = "transparent"
    altRowBackground: Optional[str] = None
    # Which key in report.data holds the array of row objects
    dataField: str
    # Border settings — controlled by the designer
    showBorder: bool = True
    borderColor: str = "#CCCCCC"
    borderWidth: float = 1
    # Legacy field kept for backwards compatibility with old payloads
    showHeader: bool = True


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

PrintWhen = Literal["always", "once", "perPage"]


class ReportBand(BaseModel):
    id: str
    type: BandType
    height: float
    elements: list[ReportElement] = Field(default_factory=list)
    # Which key in report.data this band iterates (detail band repetition)
    dataKey: Optional[str] = None
    # When to print this band
    printWhen: Optional[PrintWhen] = None

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
    # Runtime data injected at PDF export time — not stored with the design
    data: Optional[dict[str, Any]] = None
    # Named style presets — reserved, not used by the renderer yet
    styles: Optional[dict[str, Any]] = None
    # isDirty is a frontend-only flag; ignored by the engine if present
    isDirty: bool = False

    model_config = {"arbitrary_types_allowed": True}


# ─────────────────────────────────────────────
# DISCRIMINATOR HELPER
# ─────────────────────────────────────────────

_ELEMENT_MAP: dict[str, Type[BaseElement]] = {
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


def parse_report(data: dict[str, Any]) -> ReportModel:
    """
    Full deserialisation entry point.
    Handles the discriminated union for elements inside each band.
    Pops 'bands' before constructing ReportModel to avoid Pydantic
    attempting to parse elements without the discriminator helper.
    """
    data = dict(data)  # shallow copy — do not mutate caller's dict
    bands_raw = data.pop("bands", [])
    report = ReportModel(**data)
    parsed_bands = []
    for band_raw in bands_raw:
        band_raw = dict(band_raw)
        elements_raw = band_raw.pop("elements", [])
        band = ReportBand(**band_raw)
        band.elements = [parse_element(e) for e in elements_raw]
        parsed_bands.append(band)
    report.bands = parsed_bands
    return report
