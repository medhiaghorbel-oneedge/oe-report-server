import json
from pathlib import Path

from engine.models.report_models import parse_report
from engine.renderers.pdf_renderer import PDFRenderer


def main():
    print("Loading payload...")

    payload_path = Path("payload.json")

    with payload_path.open() as f:
        payload = json.load(f)

    print("Parsing report...")
    report = parse_report(payload)

    print(f"Report : {report.name}")
    print(f"Bands  : {len(report.bands)}")

    print("\nRendering PDF...")
    renderer = PDFRenderer()
    pdf_bytes = renderer.render(report)

    out = Path("output.pdf")
    out.write_bytes(pdf_bytes)

    print(f"\nDone -> {out} ({len(pdf_bytes)/1024:.1f} KB)")


if __name__ == "__main__":
    main()
