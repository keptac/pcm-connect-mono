from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..core.config import settings

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "report"


def _currency(value: float | int | None) -> str:
    if value in (None, ""):
        return "$0"
    return f"${float(value):,.0f}"


def _percentage(actual: float | int, expected: float | int) -> str:
    expected_value = float(expected or 0)
    if expected_value <= 0:
        return "N/A"
    return f"{round((float(actual or 0) / expected_value) * 100)}%"


def _load_update_attachments(update) -> list[dict]:
    if not update.attachments_json:
        return []
    try:
        parsed = json.loads(update.attachments_json)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _split_attachment_groups(update) -> tuple[list[Path], list[str]]:
    image_paths: list[Path] = []
    document_names: list[str] = []
    for attachment in _load_update_attachments(update):
      stored_name = attachment.get("stored_name") or attachment.get("path")
      if not stored_name:
          continue
      target = Path(settings.upload_dir) / stored_name
      suffix = Path(stored_name).suffix.lower()
      if suffix in IMAGE_EXTENSIONS and target.exists():
          image_paths.append(target)
      else:
          document_names.append(attachment.get("name") or stored_name)
    return image_paths, document_names


def _header_footer(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(colors.HexColor("#123d77"))
    canvas.rect(0, height - 3.1 * cm, width, 3.1 * cm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#6a3db8"))
    canvas.rect(0, height - 3.45 * cm, width, 0.35 * cm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawString(1.6 * cm, height - 1.55 * cm, "PCM Impact Report")
    canvas.setFont("Helvetica", 9)
    canvas.drawString(1.6 * cm, height - 2.2 * cm, "Public Campus Ministries | Event reporting pack")
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - 1.4 * cm, 1.0 * cm, f"Page {doc.page}")
    canvas.restoreState()


def _metric_cards(update, expected_attendance: int, actual_attendance: int) -> Table:
    styles = getSampleStyleSheet()
    value_style = ParagraphStyle(
        "ReportMetricValue",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.HexColor("#0f172a"),
        alignment=TA_CENTER,
        leading=18,
        spaceAfter=4,
    )
    label_style = ParagraphStyle(
        "ReportMetricLabel",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#475569"),
        alignment=TA_CENTER,
        leading=10,
    )
    rows = [[
        Paragraph(str(expected_attendance), value_style),
        Paragraph(str(actual_attendance), value_style),
        Paragraph(_percentage(actual_attendance, expected_attendance), value_style),
        Paragraph(str(update.volunteers_involved or 0), value_style),
    ], [
        Paragraph("Expected attendance", label_style),
        Paragraph("Actual attendance", label_style),
        Paragraph("Attainment", label_style),
        Paragraph("Volunteers", label_style),
    ]]
    table = Table(rows, colWidths=[4.1 * cm] * 4)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 1), colors.HexColor("#e0f2fe")),
        ("BACKGROUND", (1, 0), (1, 1), colors.HexColor("#dcfce7")),
        ("BACKGROUND", (2, 0), (2, 1), colors.HexColor("#ede9fe")),
        ("BACKGROUND", (3, 0), (3, 1), colors.HexColor("#fef3c7")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _attendance_chart(expected_attendance: int, actual_attendance: int, volunteers: int, funds_used: float | None) -> Drawing:
    values = [max(expected_attendance, 0), max(actual_attendance, 0), max(volunteers, 0)]
    labels = ["Expected", "Actual", "Volunteers"]
    if funds_used:
        values.append(float(funds_used))
        labels.append("Funds used")

    chart_max = max(max(values), 1)
    drawing = Drawing(16.2 * cm, 7.4 * cm)
    chart = VerticalBarChart()
    chart.x = 1.0 * cm
    chart.y = 0.8 * cm
    chart.height = 5.2 * cm
    chart.width = 14.0 * cm
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.boxAnchor = "n"
    chart.categoryAxis.labels.dy = -8
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = chart_max * 1.2
    chart.valueAxis.valueStep = max(1, round(chart_max / 4))
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 8
    chart.valueAxis.strokeColor = colors.HexColor("#cbd5e1")
    chart.categoryAxis.strokeColor = colors.HexColor("#cbd5e1")
    chart.bars[0].fillColor = colors.HexColor("#2f77bd")
    chart.bars[0].strokeColor = colors.HexColor("#123d77")
    chart.barWidth = 0.95 * cm
    chart.groupSpacing = 0.65 * cm
    chart.barSpacing = 0.2 * cm
    drawing.add(chart)

    for index, value in enumerate(values):
        x_position = chart.x + (index * (chart.barWidth + chart.groupSpacing)) + (chart.barWidth / 2)
        bar_height = (value / chart.valueAxis.valueMax) * chart.height if chart.valueAxis.valueMax else 0
        drawing.add(String(x_position, chart.y + bar_height + 8, f"{int(round(value))}", fontName="Helvetica-Bold", fontSize=8, fillColor=colors.HexColor("#0f172a"), textAnchor="middle"))

    drawing.add(String(8.1 * cm, 6.65 * cm, "Attendance and participation snapshot", fontName="Helvetica-Bold", fontSize=10, fillColor=colors.HexColor("#123d77"), textAnchor="middle"))
    return drawing


def _section_title(text: str) -> Paragraph:
    styles = getSampleStyleSheet()
    return Paragraph(
        text,
        ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=colors.HexColor("#123d77"),
            spaceAfter=6,
            spaceBefore=6,
        ),
    )


def _body_text(text: str) -> Paragraph:
    styles = getSampleStyleSheet()
    return Paragraph(
        text or "Not provided.",
        ParagraphStyle(
            "BodyTextWrap",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#334155"),
            leading=13,
            spaceAfter=4,
        ),
    )


def _details_table(update, expected_attendance: int) -> Table:
    rows = [
        ["University / Campus", update.university.name if update.university else "Not set"],
        ["Event", update.event_detail or update.event_name or update.title],
        ["Linked program", update.program.name if update.program else "No linked ministry program"],
        ["Reporting period", update.reporting_period],
        ["Submitted", update.created_at.strftime("%b %d, %Y") if update.created_at else "Not recorded"],
        ["Expected attendance", str(expected_attendance)],
        ["Actual attendance", str(update.beneficiaries_reached or 0)],
        ["Funds used", _currency(update.funds_used)],
    ]
    table = Table(rows, colWidths=[4.5 * cm, 11.2 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#0f172a")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dbe3ee")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _gallery_table(image_paths: list[Path]) -> Table | None:
    if not image_paths:
        return None

    cells = []
    row = []
    for path in image_paths[:4]:
        image = Image(str(path), width=7.4 * cm, height=5.1 * cm)
        image.hAlign = "CENTER"
        row.append(image)
        if len(row) == 2:
            cells.append(row)
            row = []
    if row:
        while len(row) < 2:
            row.append(Spacer(7.4 * cm, 5.1 * cm))
        cells.append(row)

    table = Table(cells, colWidths=[7.8 * cm, 7.8 * cm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def build_program_update_report_pdf(update) -> bytes:
    expected_attendance = int(update.program.target_beneficiaries or 0) if update.program else 0
    actual_attendance = int(update.beneficiaries_reached or 0)
    image_paths, document_names = _split_attachment_groups(update)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.4 * cm,
        rightMargin=1.4 * cm,
        topMargin=3.9 * cm,
        bottomMargin=1.6 * cm,
        title=f"{update.title} impact report",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=colors.HexColor("#0f172a"),
        leading=24,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#475569"),
        leading=14,
        spaceAfter=12,
    )

    story = [
        Paragraph(update.event_detail or update.event_name or update.title, title_style),
        Paragraph(
            f"{update.university.name if update.university else 'Campus not set'} | {update.reporting_period} | {update.program.name if update.program else 'Standalone event report'}",
            subtitle_style,
        ),
        _metric_cards(update, expected_attendance, actual_attendance),
        Spacer(1, 0.35 * cm),
        _attendance_chart(expected_attendance, actual_attendance, int(update.volunteers_involved or 0), update.funds_used),
        Spacer(1, 0.35 * cm),
        _section_title("Report profile"),
        _details_table(update, expected_attendance),
        Spacer(1, 0.25 * cm),
        _section_title("Narrative summary"),
        _body_text(update.summary or "Not provided."),
        _section_title("Outcomes"),
        _body_text(update.outcomes or "Not provided."),
        _section_title("Challenges"),
        _body_text(update.challenges or "Not provided."),
        _section_title("Next steps"),
        _body_text(update.next_steps or "Not provided."),
    ]

    if image_paths:
        story.extend([
            _section_title("Photo gallery"),
            _body_text("Images attached to this event report are included below as a visual record of the activity."),
        ])
        gallery = _gallery_table(image_paths)
        if gallery:
            story.append(gallery)

    if document_names:
        doc_text = "<br/>".join(f"• {name}" for name in document_names)
        story.extend([
            _section_title("Supporting documents"),
            _body_text(doc_text),
        ])

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buffer.getvalue()


def build_program_update_report_pack(updates: list) -> bytes:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for update in updates:
            filename = f"{update.created_at.strftime('%Y%m%d') if update.created_at else 'report'}-{_slugify(update.university.name if update.university else 'campus')}-{_slugify(update.event_detail or update.event_name or update.title)}.pdf"
            bundle.writestr(filename, build_program_update_report_pdf(update))
    archive.seek(0)
    return archive.getvalue()
