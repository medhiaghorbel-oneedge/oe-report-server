# report_engine/utils/units.py
# Coordinate system bridge: frontend px → ReportLab points
# ReportLab origin: bottom-left. Frontend origin: top-left.
# 1px = 0.75pt at 96 dpi (standard web/screen resolution).

PX_TO_PT: float = 0.75


def px(value: float) -> float:
    """Convert frontend pixels to ReportLab points."""
    return value * PX_TO_PT


def flip_y(page_height_pt: float, y_pt: float, element_height_pt: float) -> float:
    """
    Convert a top-left y coordinate (frontend) to bottom-left (ReportLab).

    Args:
        page_height_pt:   full page height in points
        y_pt:             element's top-left y in points (already converted from px)
        element_height_pt: element height in points

    Returns:
        ReportLab y — the BOTTOM-LEFT corner of the element
    """
    return page_height_pt - y_pt - element_height_pt


def parse_color(hex_color: str) -> tuple[float, float, float] | None:
    """
    Parse a CSS hex color string to an RGB tuple (0–1 floats) for ReportLab.
    Returns None if the color is 'transparent' or empty.

    Supports: '#RGB', '#RRGGBB', 'transparent', ''
    """
    if not hex_color or hex_color.lower() == "transparent":
        return None

    h = hex_color.lstrip("#")

    if len(h) == 3:
        h = "".join(c * 2 for c in h)

    if len(h) != 6:
        return None

    r = int(h[0:2], 16) / 255
    g = int(h[2:4], 16) / 255
    b = int(h[4:6], 16) / 255
    return (r, g, b)


def resolve_font(family: str, bold: bool = False, italic: bool = False) -> str:
    """
    Map a font family + weight/style to a ReportLab built-in font name.
    ReportLab ships 14 standard PDF fonts — no embedding required.

    Custom fonts (e.g. IBM Plex Sans) require TTF registration;
    this function provides a safe fallback chain.
    """
    family_lower = family.lower().replace(" ", "").replace("-", "")

    # Helvetica family (our primary UI font maps here)
    helvetica_aliases = {"helvetica", "ibmplexsans", "arial", "sansserif", "sans"}
    # Times family
    times_aliases = {"timesnewroman", "times", "serif", "georgia"}
    # Courier family
    courier_aliases = {"couriernew", "courier", "monospace", "ibmplexmono"}

    if any(alias in family_lower for alias in helvetica_aliases):
        base = "Helvetica"
    elif any(alias in family_lower for alias in times_aliases):
        base = "Times"
    elif any(alias in family_lower for alias in courier_aliases):
        base = "Courier"
    else:
        base = "Helvetica"  # safe default

    # Handle already-qualified names like "Helvetica-Bold" passed directly
    qualified = {
        "Helvetica-Bold",
        "Helvetica-BoldOblique",
        "Helvetica-Oblique",
        "Times-Bold",
        "Times-BoldItalic",
        "Times-Italic",
        "Times-Roman",
        "Courier-Bold",
        "Courier-BoldOblique",
        "Courier-Oblique",
    }
    if family in qualified:
        return family

    # Build qualified name
    if bold and italic:
        suffixes = {
            "Helvetica": "-BoldOblique",
            "Times": "-BoldItalic",
            "Courier": "-BoldOblique",
        }
    elif bold:
        suffixes = {"Helvetica": "-Bold", "Times": "-Bold", "Courier": "-Bold"}
    elif italic:
        suffixes = {"Helvetica": "-Oblique", "Times": "-Italic", "Courier": "-Oblique"}
    else:
        suffixes = {"Helvetica": "", "Times": "-Roman", "Courier": ""}

    return base + suffixes[base]


def format_value(
    value: object, fmt: str, pattern: str | None, null_text: str | None
) -> str:
    """
    Format a raw data value according to FieldElement.format and .pattern.
    Returns a display string ready for the PDF canvas.
    """
    if value is None:
        return null_text or "—"

    try:
        if fmt == "text":
            return str(value)

        elif fmt == "number":
            num = float(str(value))
            if pattern and "." in pattern:
                decimals = len(pattern.split(".")[-1])
                return f"{num:,.{decimals}f}"
            return f"{num:,.0f}"

        elif fmt == "currency":
            num = float(str(value))
            # Extract currency symbol from pattern (default $)
            symbol = "$"
            if pattern:
                for ch in pattern:
                    if not ch.isdigit() and ch not in ".#,+-":
                        symbol = ch
                        break
            # Handle negative values
            if num < 0:
                return f"-{symbol}{abs(num):,.2f}"
            return f"{symbol}{num:,.2f}"

        elif fmt in ("date", "datetime"):
            from datetime import datetime

            # Accept ISO string or datetime object
            if isinstance(value, str):
                for iso_fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        dt = datetime.strptime(value, iso_fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return str(value)
            elif isinstance(value, datetime):
                dt = value
            else:
                return str(value)

            # Map simple pattern tokens to Python strftime
            out_fmt = pattern or "dd/MM/yyyy"
            out_fmt = (
                out_fmt.replace("yyyy", "%Y")
                .replace("yy", "%y")
                .replace("MM", "%m")
                .replace("dd", "%d")
                .replace("HH", "%H")
                .replace("mm", "%M")
                .replace("ss", "%S")
            )
            return dt.strftime(out_fmt)

        elif fmt == "boolean":
            return "Yes" if bool(value) else "No"

        else:
            return str(value)

    except Exception:
        return str(value)


def resolve_data_path(data: dict, path: str) -> object:
    """
    Resolve a dot-notation path like "invoice.total" from a nested data dict.
    Returns None if the path does not exist.
    """
    parts = path.split(".")
    node = data
    for part in parts:
        if isinstance(node, dict):
            node = node.get(part)
        else:
            return None
    return node
