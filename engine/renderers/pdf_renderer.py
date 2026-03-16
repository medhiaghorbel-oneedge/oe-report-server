# report_engine/renderers/pdf_renderer.py
# Core rendering engine: ReportModel → PDF bytes via ReportLab canvas API.
#
# Rendering pipeline:
#   1. ReportModel parsed and validated by Pydantic
#   2. Bands iterated top-to-bottom, each band's y-offset accumulated
#   3. Each element dispatched to its specific draw_* method
#   4. All coordinates flipped (top-left → bottom-left) and px → pt converted
#   5. PDF bytes returned as io.BytesIO

from __future__ import annotations

import io
import urllib.request
from typing import Any

from typing import cast

from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.utils import ImageReader

from engine.models.report_models import (
    ReportModel,
    ReportBand,
    ReportElement,
    StaticTextElement,
    RectangleElement,
    LineElement,
    FieldElement,
    ImageElement,
    TableElement,
)
from engine.utils.units import (
    px,
    flip_y,
    parse_color,
    resolve_font,
    format_value,
    resolve_data_path,
)


class PDFRenderer:
    """
    Stateless renderer — create one instance per request.
    Call .render(report) to get PDF bytes.
    """

    def __init__(self):
        self._canvas: rl_canvas.Canvas | None = None
        self._page_height_pt: float = 0
        self._data: dict[str, Any] = {}

    @property
    def canvas(self) -> rl_canvas.Canvas:
        assert self._canvas is not None
        return self._canvas

    # ─────────────────────────────────────────────
    # PUBLIC ENTRY POINT
    # ─────────────────────────────────────────────

    def render(self, report: ReportModel) -> bytes:
        """Render a ReportModel to PDF and return raw bytes."""
        buf = io.BytesIO()

        page_w_pt = px(report.width)
        page_h_pt = px(report.height)
        self._page_height_pt = page_h_pt
        self._data = report.data or {}

        self._canvas = rl_canvas.Canvas(buf, pagesize=(page_w_pt, page_h_pt))
        self._canvas.setTitle(report.name)

        # Accumulate band top-offsets as we iterate top-to-bottom
        margin_top_pt = px(report.margins.top)
        band_top_pt = margin_top_pt

        for band in report.bands:
            self._render_band(band, band_top_pt, report)
            band_top_pt += px(band.height)

        self._canvas.save()
        buf.seek(0)
        return buf.read()

    # ─────────────────────────────────────────────
    # BAND RENDERER
    # ─────────────────────────────────────────────

    def _render_band(
        self, band: ReportBand, band_top_pt: float, report: ReportModel
    ) -> None:
        """Render all elements in a single band."""
        margin_left_pt = px(report.margins.left)

        for element in band.elements:
            # Element position is relative to band top-left
            el_x_pt = margin_left_pt + px(element.x)
            el_y_pt = band_top_pt + px(element.y)

            self._dispatch_element(element, el_x_pt, el_y_pt)

    # ─────────────────────────────────────────────
    # ELEMENT DISPATCHER
    # ─────────────────────────────────────────────

    def _dispatch_element(
        self, element: ReportElement, x_pt: float, y_pt: float
    ) -> None:
        """Route element to its draw method by type."""
        if isinstance(element, StaticTextElement):
            self._draw_static_text(element, x_pt, y_pt)
        elif isinstance(element, RectangleElement):
            self._draw_rectangle(element, x_pt, y_pt)
        elif isinstance(element, LineElement):
            self._draw_line(element, x_pt, y_pt)
        elif isinstance(element, FieldElement):
            self._draw_field(element, x_pt, y_pt)
        elif isinstance(element, ImageElement):
            self._draw_image(element, x_pt, y_pt)
        elif isinstance(element, TableElement):
            self._draw_table(element, x_pt, y_pt)

    # ─────────────────────────────────────────────
    # DRAW: RECTANGLE
    # ─────────────────────────────────────────────

    def _draw_rectangle(self, el: RectangleElement, x_pt: float, y_pt: float) -> None:
        c = self.canvas
        w_pt = px(el.width)
        h_pt = px(el.height)
        rl_y = flip_y(self._page_height_pt, y_pt, h_pt)

        fill_color = parse_color(el.style.fillColor)
        stroke_color = parse_color(el.style.borderColor)
        has_fill = fill_color is not None
        has_stroke = stroke_color is not None and el.style.borderStyle != "none"

        if has_fill:
            c.setFillColorRGB(*cast(tuple[float, float, float], fill_color))

        if has_stroke:
            c.setStrokeColorRGB(*cast(tuple[float, float, float], stroke_color))
            c.setLineWidth(px(el.style.borderWidth))
            self._apply_dash(el.style.borderStyle)
            c.setLineWidth(px(el.style.borderWidth))
            self._apply_dash(el.style.borderStyle)

        c.setFillAlpha(el.style.opacity if has_fill else 0)
        c.setStrokeAlpha(el.style.opacity if has_stroke else 0)

        radius_pt = px(el.radius)
        if radius_pt > 0:
            c.roundRect(
                x_pt,
                rl_y,
                w_pt,
                h_pt,
                radius_pt,
                fill=1 if has_fill else 0,
                stroke=1 if has_stroke else 0,
            )
        else:
            c.rect(
                x_pt,
                rl_y,
                w_pt,
                h_pt,
                fill=1 if has_fill else 0,
                stroke=1 if has_stroke else 0,
            )

        # Reset alpha
        c.setFillAlpha(1)
        c.setStrokeAlpha(1)

    # ─────────────────────────────────────────────
    # DRAW: LINE
    # ─────────────────────────────────────────────

    def _draw_line(self, el: LineElement, x_pt: float, y_pt: float) -> None:
        c = self.canvas
        w_pt = px(el.width)
        h_pt = px(el.height)

        stroke_color = parse_color(el.style.borderColor)
        if stroke_color:
            c.setStrokeColorRGB(*stroke_color)
        c.setLineWidth(px(el.style.borderWidth) or 0.75)
        self._apply_dash(el.style.borderStyle)

        if el.direction == "horizontal":
            rl_y = flip_y(self._page_height_pt, y_pt, h_pt)
            c.line(x_pt, rl_y, x_pt + w_pt, rl_y)
        elif el.direction == "vertical":
            rl_y_top = flip_y(self._page_height_pt, y_pt, h_pt)
            c.line(x_pt, rl_y_top + h_pt, x_pt, rl_y_top)
        else:  # diagonal
            rl_y = flip_y(self._page_height_pt, y_pt, h_pt)
            c.line(x_pt, rl_y + h_pt, x_pt + w_pt, rl_y)

        # Reset dash
        c.setDash()

    # ─────────────────────────────────────────────
    # DRAW: STATIC TEXT
    # ─────────────────────────────────────────────

    def _draw_static_text(
        self, el: StaticTextElement, x_pt: float, y_pt: float
    ) -> None:
        self._draw_text_in_box(
            text=el.text,
            text_style=el.textStyle,
            x_pt=x_pt,
            y_pt=y_pt,
            w_pt=px(el.width),
            h_pt=px(el.height),
        )

    # ─────────────────────────────────────────────
    # DRAW: FIELD (data-bound text)
    # ─────────────────────────────────────────────

    def _draw_field(self, el: FieldElement, x_pt: float, y_pt: float) -> None:
        raw_value = resolve_data_path(self._data, el.fieldName)
        display = format_value(raw_value, el.format, el.pattern, el.nullText)
        self._draw_text_in_box(
            text=display,
            text_style=el.textStyle,
            x_pt=x_pt,
            y_pt=y_pt,
            w_pt=px(el.width),
            h_pt=px(el.height),
        )

    # ─────────────────────────────────────────────
    # DRAW: IMAGE
    # ─────────────────────────────────────────────

    def _draw_image(self, el: ImageElement, x_pt: float, y_pt: float) -> None:
        c = self.canvas
        w_pt = px(el.width)
        h_pt = px(el.height)
        rl_y = flip_y(self._page_height_pt, y_pt, h_pt)

        # Resolve src — may be a data path, URL, or base64
        src = el.src
        if not src.startswith(("http", "data:", "/")):
            resolved = resolve_data_path(self._data, src)
            if resolved:
                src = str(resolved)

        try:
            if src.startswith("http"):
                with urllib.request.urlopen(src, timeout=5) as resp:
                    img_data = io.BytesIO(resp.read())
                img_reader = ImageReader(img_data)
            else:
                img_reader = ImageReader(src)

            c.drawImage(
                img_reader,
                x_pt,
                rl_y,
                width=w_pt,
                height=h_pt,
                preserveAspectRatio=(el.fit == "contain"),
                mask="auto",
            )
        except Exception as e:
            # Draw a placeholder box with an X on failure
            self._draw_image_placeholder(x_pt, rl_y, w_pt, h_pt, str(e))

    # ─────────────────────────────────────────────
    # DRAW: TABLE
    # ─────────────────────────────────────────────

    def _draw_table(self, el: TableElement, x_pt: float, y_pt: float) -> None:
        c = self.canvas

        # Resolve row data from the data context
        rows_data = resolve_data_path(self._data, el.dataField)
        rows: list[dict] = rows_data if isinstance(rows_data, list) else []
        if not isinstance(rows, list):
            rows = []

        header_h_pt = px(el.headerHeight) if el.showHeader else 0
        row_h_pt = px(el.rowHeight)
        cursor_y_pt = y_pt  # top-left, will advance downward

        # ── Header row ──
        if el.showHeader:
            col_x = x_pt
            # Header background — use the font color's dark base as bg
            # (we use the dark brand color #1A1A2E from the style)
            c.setFillColorRGB(0.102, 0.102, 0.18)  # #1A1A2E
            c.setStrokeAlpha(0)
            header_rl_y = flip_y(self._page_height_pt, cursor_y_pt, header_h_pt)
            c.rect(x_pt, header_rl_y, px(el.width), header_h_pt, fill=1, stroke=0)
            c.setStrokeAlpha(1)

            for col in el.columns:
                col_w_pt = px(col.width)
                self._draw_text_in_box(
                    text=col.label,
                    text_style=el.headerStyle,
                    x_pt=col_x + px(6),  # inner padding
                    y_pt=cursor_y_pt,
                    w_pt=col_w_pt - px(12),
                    h_pt=header_h_pt,
                    h_align_override=col.align,
                )
                col_x += col_w_pt

            cursor_y_pt += header_h_pt

        # ── Data rows ──
        for row_idx, row in enumerate(rows):
            row_rl_y = flip_y(self._page_height_pt, cursor_y_pt, row_h_pt)

            # Zebra striping
            if el.altRowColor and row_idx % 2 == 1:
                alt = parse_color(el.altRowColor)
                if alt:
                    c.setFillColorRGB(*alt)
                    c.setStrokeAlpha(0)
                    c.rect(x_pt, row_rl_y, px(el.width), row_h_pt, fill=1, stroke=0)
                    c.setStrokeAlpha(1)

            # Row bottom border
            c.setStrokeColorRGB(0.878, 0.878, 0.878)  # #E0E0E0
            c.setLineWidth(0.5)
            c.line(x_pt, row_rl_y, x_pt + px(el.width), row_rl_y)

            # Cells
            col_x = x_pt
            for col in el.columns:
                col_w_pt = px(col.width)
                raw = row.get(col.key)
                display = format_value(raw, col.format or "text", col.pattern, "—")
                self._draw_text_in_box(
                    text=display,
                    text_style=el.rowStyle,
                    x_pt=col_x + px(6),
                    y_pt=cursor_y_pt,
                    w_pt=col_w_pt - px(12),
                    h_pt=row_h_pt,
                    h_align_override=col.align,
                )
                col_x += col_w_pt

            cursor_y_pt += row_h_pt

    # ─────────────────────────────────────────────
    # SHARED TEXT DRAWING HELPER
    # ─────────────────────────────────────────────

    def _draw_text_in_box(
        self,
        text: str,
        text_style,
        x_pt: float,
        y_pt: float,
        w_pt: float,
        h_pt: float,
        h_align_override: str | None = None,
    ) -> None:
        """
        Draw a string clipped inside a bounding box, respecting
        horizontal and vertical alignment.
        """
        c = self.canvas
        if not text:
            return

        font_name = resolve_font(
            text_style.fontFamily, text_style.bold, text_style.italic
        )
        font_size = text_style.fontSize
        color = parse_color(text_style.color) or (0, 0, 0)
        h_align = h_align_override or text_style.hAlign
        v_align = text_style.vAlign

        c.setFont(font_name, font_size)
        c.setFillColorRGB(*color)

        # Vertical alignment: compute text baseline
        ascent = font_size * 0.8  # approximate cap height
        if v_align == "top":
            text_y_in_box = h_pt - ascent - px(2)
        elif v_align == "bottom":
            text_y_in_box = px(2)
        else:  # middle
            text_y_in_box = (h_pt - ascent) / 2

        rl_y = flip_y(self._page_height_pt, y_pt, h_pt) + text_y_in_box

        # Horizontal alignment
        if h_align == "right":
            c.drawRightString(x_pt + w_pt, rl_y, text)
        elif h_align == "center":
            c.drawCentredString(x_pt + w_pt / 2, rl_y, text)
        else:
            c.drawString(x_pt, rl_y, text)

        # Underline
        if text_style.underline:
            text_width = c.stringWidth(text, font_name, font_size)
            ul_y = rl_y - px(1)
            c.setLineWidth(0.5)
            if h_align == "right":
                c.line(x_pt + w_pt - text_width, ul_y, x_pt + w_pt, ul_y)
            elif h_align == "center":
                mid = x_pt + w_pt / 2
                c.line(mid - text_width / 2, ul_y, mid + text_width / 2, ul_y)
            else:
                c.line(x_pt, ul_y, x_pt + text_width, ul_y)

    # ─────────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────────

    def _apply_dash(self, border_style: str) -> None:
        c = self.canvas
        if border_style == "dashed":
            c.setDash(6, 3)
        elif border_style == "dotted":
            c.setDash(2, 2)
        else:
            c.setDash()

    def _draw_image_placeholder(
        self, x: float, y: float, w: float, h: float, reason: str
    ) -> None:
        c = self.canvas
        c.setStrokeColorRGB(0.8, 0.2, 0.2)
        c.setFillColorRGB(0.98, 0.95, 0.95)
        c.rect(x, y, w, h, fill=1, stroke=1)
        c.setFillColorRGB(0.6, 0.2, 0.2)
        c.setFont("Helvetica", 8)
        c.drawCentredString(x + w / 2, y + h / 2, "[Image load failed]")
