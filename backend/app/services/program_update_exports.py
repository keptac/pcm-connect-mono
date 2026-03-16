import importlib
import json
import shutil
import subprocess
import tempfile
from datetime import date
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from xml.sax.saxutils import escape

from ..core.config import settings
from ..models import ProgramUpdate

PCM_BLUE = colors.HexColor("#233A78")
PCM_VIOLET = colors.HexColor("#5641A7")
PCM_RED = colors.HexColor("#D33D48")
PCM_SKY = colors.HexColor("#4A9BD6")
PCM_GOLD = colors.HexColor("#D6A73D")
PCM_SLATE = colors.HexColor("#64748B")
PCM_BORDER = colors.HexColor("#D7E0EE")
PCM_SURFACE = colors.HexColor("#F8FBFF")
CONTENT_WIDTH = A4[0] - (32 * mm)

REPO_ROOT = Path(__file__).resolve().parents[3]
LOGO_PATHS = (
    Path(__file__).resolve().parents[1] / "assets" / "pcm_logo.png",
    Path(__file__).resolve().parents[1] / "assets" / "pcm_logo.jpg",
    REPO_ROOT / "frontend" / "src" / "images" / "pcm_logo.png",
)
FONT_CANDIDATES = {
    "regular": (
        Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Poppins-Regular.ttf",
        Path.home() / "Library" / "Fonts" / "Poppins-Regular.ttf",
    ),
    "semibold": (
        Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Poppins-SemiBold.ttf",
        Path.home() / "Library" / "Fonts" / "Poppins-SemiBold.ttf",
    ),
    "bold": (
        Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Poppins-Bold.ttf",
        Path.home() / "Library" / "Fonts" / "Poppins-Bold.ttf",
    ),
}
PDF_FONT_NAMES = {
    "regular": "Helvetica",
    "semibold": "Helvetica-Bold",
    "bold": "Helvetica-Bold",
}
PDF_FONT_REGISTRATION_ATTEMPTED = False
OCR_ENGINE = None
OCR_ENGINE_ATTEMPTED = False
WORDPROCESSING_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def build_program_update_report_pack(updates: list[ProgramUpdate]) -> bytes:
    bundle = BytesIO()
    with ZipFile(bundle, "w", ZIP_DEFLATED) as archive:
        for index, update in enumerate(updates, start=1):
            filename = f"{index:02d}_{_slugify(_meeting_report_title(update) if _is_meeting_update(update) else _report_title(update))}.pdf"
            archive.writestr(filename, build_program_update_pdf(update))
    return bundle.getvalue()


def build_program_update_pdf(update: ProgramUpdate) -> bytes:
    if _is_meeting_update(update):
        return _build_meeting_minutes_pdf(update)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=34 * mm,
        bottomMargin=16 * mm,
        title=_report_title(update),
        author="Public Campus Ministries",
    )
    styles = _build_styles()
    image_attachments, document_attachments = _resolve_attachments(update)

    story = [
        *_build_cover_page(update, styles),
        PageBreak(),
        _build_hero(update, styles),
        Spacer(1, 8),
        _build_metric_cards(update, styles),
        Spacer(1, 12),
        _build_attendance_chart(update, styles),
        PageBreak(),
        Paragraph("Program context", styles["section"]),
        _build_context_table(update, styles),
        Spacer(1, 10),
        Paragraph("Narrative summary", styles["section"]),
        _build_summary_callout(update, styles),
        Spacer(1, 10),
    ]

    story.extend(_build_narrative_sections(update, styles))

    if image_attachments:
        story.extend(
            [
                PageBreak(),
                Paragraph("Evidence gallery", styles["section"]),
                Paragraph(
                    "Photos attached to this update are arranged below as visual evidence of participation and delivery.",
                    styles["bodyMuted"],
                ),
                Spacer(1, 8),
                _build_gallery(image_attachments, styles),
            ]
        )

    if document_attachments:
        story.extend(
            [
                Spacer(1, 12),
                Paragraph("Supporting documents", styles["section"]),
                Paragraph(
                    "Additional documents uploaded with this update are listed here for reference in the system record.",
                    styles["bodyMuted"],
                ),
                Spacer(1, 6),
                _build_document_table(document_attachments, styles),
            ]
        )

    doc.build(
        story,
        onFirstPage=lambda canvas, built_doc: _decorate_cover_page(canvas, built_doc, update),
        onLaterPages=lambda canvas, built_doc: _decorate_page(canvas, built_doc, update),
    )
    return buffer.getvalue()


def _build_meeting_minutes_pdf(update: ProgramUpdate) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=34 * mm,
        bottomMargin=16 * mm,
        title=_meeting_report_title(update),
        author="Public Campus Ministries",
    )
    styles = _build_styles()
    minute_documents = _extract_meeting_minutes_documents(update)

    story = [
        *_build_meeting_minutes_cover_page(update, styles, minute_documents),
        PageBreak(),
        *_build_meeting_minutes_content(update, styles, minute_documents),
    ]

    doc.build(
        story,
        onFirstPage=lambda canvas, built_doc: _decorate_meeting_minutes_cover_page(canvas, built_doc, update),
        onLaterPages=lambda canvas, built_doc: _decorate_meeting_minutes_page(canvas, built_doc, update),
    )
    return buffer.getvalue()


def _build_styles():
    fonts = _ensure_pdf_fonts()
    sample = getSampleStyleSheet()
    return {
        "heroTitle": ParagraphStyle(
            "heroTitle",
            parent=sample["Heading1"],
            fontName=fonts["bold"],
            fontSize=19,
            leading=23,
            textColor=colors.white,
            spaceAfter=4,
        ),
        "heroMeta": ParagraphStyle(
            "heroMeta",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=9.5,
            leading=12,
            textColor=colors.white,
            alignment=TA_RIGHT,
        ),
        "coverEyebrow": ParagraphStyle(
            "coverEyebrow",
            parent=sample["BodyText"],
            fontName=fonts["semibold"],
            fontSize=10,
            leading=12,
            textColor=PCM_RED,
            alignment=TA_CENTER,
        ),
        "coverTitle": ParagraphStyle(
            "coverTitle",
            parent=sample["Heading1"],
            fontName=fonts["bold"],
            fontSize=24,
            leading=28,
            textColor=PCM_BLUE,
            alignment=TA_CENTER,
        ),
        "coverSubtitle": ParagraphStyle(
            "coverSubtitle",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=11,
            leading=15,
            textColor=PCM_SLATE,
            alignment=TA_CENTER,
        ),
        "coverFactLabel": ParagraphStyle(
            "coverFactLabel",
            parent=sample["BodyText"],
            fontName=fonts["semibold"],
            fontSize=8,
            leading=10,
            textColor=PCM_SLATE,
        ),
        "coverFactValue": ParagraphStyle(
            "coverFactValue",
            parent=sample["BodyText"],
            fontName=fonts["semibold"],
            fontSize=10,
            leading=13,
            textColor=PCM_BLUE,
        ),
        "section": ParagraphStyle(
            "section",
            parent=sample["Heading2"],
            fontName=fonts["bold"],
            fontSize=13,
            leading=16,
            textColor=PCM_BLUE,
            spaceAfter=6,
        ),
        "chartTitle": ParagraphStyle(
            "chartTitle",
            parent=sample["Heading2"],
            fontName=fonts["bold"],
            fontSize=11,
            leading=13,
            textColor=PCM_BLUE,
        ),
        "body": ParagraphStyle(
            "body",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#243446"),
        ),
        "bodyMuted": ParagraphStyle(
            "bodyMuted",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=9,
            leading=13,
            textColor=PCM_SLATE,
        ),
        "callout": ParagraphStyle(
            "callout",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#18324E"),
        ),
        "metricLabel": ParagraphStyle(
            "metricLabel",
            parent=sample["BodyText"],
            fontName=fonts["semibold"],
            fontSize=8.2,
            leading=10,
            textColor=PCM_SLATE,
        ),
        "metricValue": ParagraphStyle(
            "metricValue",
            parent=sample["BodyText"],
            fontName=fonts["bold"],
            fontSize=13.5,
            leading=16,
            textColor=PCM_BLUE,
        ),
        "metricHelper": ParagraphStyle(
            "metricHelper",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=7.8,
            leading=10,
            textColor=PCM_SLATE,
        ),
        "insightTitle": ParagraphStyle(
            "insightTitle",
            parent=sample["BodyText"],
            fontName=fonts["semibold"],
            fontSize=9.5,
            leading=12,
            textColor=PCM_BLUE,
        ),
        "insightBody": ParagraphStyle(
            "insightBody",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=8.5,
            leading=11,
            textColor=PCM_SLATE,
        ),
        "tableLabel": ParagraphStyle(
            "tableLabel",
            parent=sample["BodyText"],
            fontName=fonts["semibold"],
            fontSize=8,
            leading=10,
            textColor=PCM_SLATE,
        ),
        "tableValue": ParagraphStyle(
            "tableValue",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#223247"),
        ),
        "galleryCaption": ParagraphStyle(
            "galleryCaption",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=8.5,
            leading=11,
            alignment=TA_CENTER,
            textColor=PCM_SLATE,
        ),
        "docName": ParagraphStyle(
            "docName",
            parent=sample["BodyText"],
            fontName=fonts["semibold"],
            fontSize=9,
            leading=12,
            textColor=PCM_BLUE,
        ),
        "docMeta": ParagraphStyle(
            "docMeta",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=8.5,
            leading=11,
            textColor=PCM_SLATE,
        ),
        "minutesContent": ParagraphStyle(
            "minutesContent",
            parent=sample["Code"],
            fontName=fonts["regular"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#243446"),
        ),
        "minutesParagraph": ParagraphStyle(
            "minutesParagraph",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#243446"),
            spaceAfter=4,
        ),
        "minutesHeading": ParagraphStyle(
            "minutesHeading",
            parent=sample["Heading3"],
            fontName=fonts["bold"],
            fontSize=11.5,
            leading=15,
            textColor=PCM_BLUE,
            spaceBefore=2,
            spaceAfter=5,
        ),
        "minutesBullet": ParagraphStyle(
            "minutesBullet",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#243446"),
            leftIndent=14,
            bulletIndent=2,
            spaceAfter=3,
        ),
        "minutesTableCell": ParagraphStyle(
            "minutesTableCell",
            parent=sample["BodyText"],
            fontName=fonts["regular"],
            fontSize=8.8,
            leading=12,
            textColor=colors.HexColor("#243446"),
        ),
        "minutesTableHeader": ParagraphStyle(
            "minutesTableHeader",
            parent=sample["BodyText"],
            fontName=fonts["bold"],
            fontSize=8.8,
            leading=12,
            textColor=PCM_BLUE,
        ),
        "valueRight": ParagraphStyle(
            "valueRight",
            parent=sample["BodyText"],
            fontName=fonts["semibold"],
            fontSize=9.5,
            leading=12,
            textColor=PCM_BLUE,
            alignment=TA_RIGHT,
        ),
    }


def _build_cover_page(update: ProgramUpdate, styles):
    university = update.university
    conference = university.conference if university else None
    metrics = _collect_report_metrics(update)
    cover_elements = [Spacer(1, 18 * mm)]

    logo_path = _logo_path()
    if logo_path:
        logo = _scaled_image(logo_path, 34 * mm, 34 * mm)
        if logo is not None:
            logo.hAlign = "CENTER"
            cover_elements.extend([logo, Spacer(1, 8 * mm)])

    cover_elements.extend(
        [
            Paragraph("Public Campus Ministries", styles["coverEyebrow"]),
            Spacer(1, 3 * mm),
            Paragraph("Impact Report", styles["coverTitle"]),
            Spacer(1, 2 * mm),
            Paragraph(_safe_text(_display_event_name(update)), styles["coverSubtitle"]),
            Spacer(1, 8 * mm),
            _build_cover_identity_table(update, styles),
            Spacer(1, 7 * mm),
            _build_cover_snapshot_table(_build_cover_metric_items(metrics), styles),
            Spacer(1, 7 * mm),
            _build_cover_summary_panel(update, styles),
        ]
    )
    return cover_elements


def _build_meeting_minutes_cover_page(update: ProgramUpdate, styles, minute_documents: list[dict]):
    cover_elements = [Spacer(1, 18 * mm)]

    logo_path = _logo_path()
    if logo_path:
        logo = _scaled_image(logo_path, 34 * mm, 34 * mm)
        if logo is not None:
            logo.hAlign = "CENTER"
            cover_elements.extend([logo, Spacer(1, 8 * mm)])

    cover_elements.extend(
        [
            Paragraph("Public Campus Ministries", styles["coverEyebrow"]),
            Spacer(1, 3 * mm),
            Paragraph("Meeting Minutes", styles["coverTitle"]),
            Spacer(1, 2 * mm),
            Paragraph(_safe_text(_display_event_name(update)), styles["coverSubtitle"]),
            Spacer(1, 8 * mm),
            _build_meeting_minutes_identity_table(update, styles, minute_documents),
            Spacer(1, 7 * mm),
            _build_meeting_minutes_summary_panel(update, styles, minute_documents),
        ]
    )
    return cover_elements


def _build_hero(update: ProgramUpdate, styles):
    title = _display_event_name(update)
    schedule = _program_schedule(update)
    right_note = "<br/>".join(
        part
        for part in [
            f"<b>Reporting period:</b> {escape(update.reporting_period or 'Not set')}",
            f"<b>Reporting date:</b> {_format_date(update.reporting_date)}",
            f"<b>Generated:</b> {_format_datetime(update.updated_at or update.created_at)}",
            f"<b>Audience:</b> {escape(update.program.audience) if update.program and update.program.audience else 'General'}",
        ]
        if part
    )
    hero = Table(
        [[
            Paragraph(
                f"{escape(title)}<br/><font size='10'>{escape(update.university.name if update.university else 'PCM network')} | {escape(schedule)}</font>",
                styles["heroTitle"],
            ),
            Paragraph(right_note, styles["heroMeta"]),
        ]],
        colWidths=[118 * mm, 56 * mm],
    )
    hero.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), PCM_BLUE),
                ("BACKGROUND", (1, 0), (1, 0), PCM_VIOLET),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 1, colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return hero


def _build_metric_cards(update: ProgramUpdate, styles):
    return _build_metric_grid(_build_detailed_metric_items(_collect_report_metrics(update)), styles, columns=3)


def _build_attendance_chart(update: ProgramUpdate, styles):
    fonts = _ensure_pdf_fonts()
    metrics = _collect_report_metrics(update)
    expected = metrics["expected"]
    actual = metrics["actual"]
    volunteers = metrics["volunteers"]
    visual_width = 104 * mm
    visual_height = 48 * mm
    chart = Drawing(visual_width, visual_height)

    baseline_y = 10 * mm
    chart_height = 26 * mm
    chart_width = 70 * mm
    origin_x = 10 * mm
    chart.add(Line(origin_x, baseline_y, origin_x + chart_width, baseline_y, strokeColor=PCM_BORDER, strokeWidth=1))

    chart_series = [
        ("Expected", expected, PCM_BLUE),
        ("Actual", actual, PCM_RED),
        ("Missionaries", volunteers, PCM_VIOLET),
    ]
    maximum = max([value for _, value, _ in chart_series] + [1])
    bar_width = 14 * mm
    gap = 9 * mm

    for index, (label, value, color) in enumerate(chart_series):
        x = origin_x + (6 * mm) + (index * (bar_width + gap))
        bar_height = chart_height * (value / maximum) if maximum else 0
        chart.add(Rect(x, baseline_y, bar_width, chart_height, fillColor=colors.HexColor("#E7EEF8"), strokeColor=None))
        chart.add(Rect(x, baseline_y, bar_width, bar_height, fillColor=color, strokeColor=None))
        chart.add(
            String(
                x + (bar_width / 2),
                baseline_y + chart_height + 5,
                _format_number(value),
                fontName=fonts["bold"],
                fontSize=8.5,
                fillColor=PCM_BLUE,
                textAnchor="middle",
            )
        )
        chart.add(
            String(
                x + (bar_width / 2),
                baseline_y - 10,
                label,
                fontName=fonts["regular"],
                fontSize=8,
                fillColor=PCM_SLATE,
                textAnchor="middle",
            )
        )

    insight_panel = Table(
        [
            [Paragraph("Insight", styles["insightTitle"])],
            [Paragraph(_safe_text(_build_report_insight(metrics, include_funds=False)), styles["insightBody"])],
        ],
        colWidths=[54 * mm],
    )
    insight_panel.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    content = Table([[chart, insight_panel]], colWidths=[110 * mm, 58 * mm])
    content.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    card = Table(
        [
            [Paragraph("Visitor reach and missionary mobilization", styles["chartTitle"])],
            [content],
        ],
        colWidths=[CONTENT_WIDTH],
    )
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PCM_SURFACE),
                ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return card


def _build_context_table(update: ProgramUpdate, styles):
    expected = max(int(update.program.target_beneficiaries or 0), 0) if update.program else 0
    rows = [
        ("University / campus", update.university.name if update.university else "PCM Office / Network"),
        ("Linked ministry program", update.program.name if update.program else "Not linked"),
        ("Program audience", update.program.audience if update.program and update.program.audience else "General"),
        ("Reporting date", _format_date(update.reporting_date)),
        ("Reporting period", update.reporting_period or "Not set"),
        ("Schedule", _program_schedule(update)),
        ("Duration", _format_duration(update.program.duration_weeks if update.program else None)),
        ("Expected visitors / reach", _format_number(expected) if expected else "Not configured"),
    ]
    table = Table(
        [
            [Paragraph(escape(label), styles["tableLabel"]), Paragraph(escape(value), styles["tableValue"])]
            for label, value in rows
        ],
        colWidths=[52 * mm, 122 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.8, PCM_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F7FAFD")),
            ]
        )
    )
    return table


def _build_cover_identity_table(update: ProgramUpdate, styles):
    university = update.university
    conference = university.conference if university else None
    rows = [
        ("University / campus", university.name if university else "PCM network"),
        ("Conference", conference.name if conference else "Not assigned"),
        ("Union", conference.union_name if conference and conference.union_name else "Not assigned"),
        ("Reporting date", _format_date(update.reporting_date)),
        ("Reporting period", update.reporting_period or "Not set"),
        ("Schedule", _program_schedule(update)),
        ("Generated", _format_datetime(update.updated_at or update.created_at)),
    ]
    table = Table(
        [
            [
                Paragraph(escape(label), styles["coverFactLabel"]),
                Paragraph(escape(value), styles["coverFactValue"]),
            ]
            for label, value in rows
        ],
        colWidths=[58 * mm, 112 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.8, PCM_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F7FAFD")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    return table


def _build_cover_snapshot_table(items: list[dict], styles):
    return _build_metric_grid(items, styles, columns=2)


def _build_cover_summary_panel(update: ProgramUpdate, styles):
    metrics = _collect_report_metrics(update)
    summary_parts = [f"<b>Calculated insight:</b> {escape(_build_report_insight(metrics))}"]
    if update.summary:
        summary_parts.append(_safe_text(update.summary))
    content = Table(
        [[
            Paragraph(
                "<br/><br/>".join(summary_parts),
                styles["callout"],
            )
        ]],
        colWidths=[CONTENT_WIDTH - (4 * mm)],
    )
    content.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF4FF")),
                ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return content


def _build_meeting_minutes_identity_table(update: ProgramUpdate, styles, minute_documents: list[dict]):
    first_minutes_document = minute_documents[0] if minute_documents else {}
    rows = [
        ("University / campus", update.university.name if update.university else "PCM network"),
        ("Meeting", _display_event_name(update)),
        ("Date", _format_date(_meeting_date_value(update, first_minutes_document))),
        ("Venue", first_minutes_document.get("venue") or "Not recorded"),
        ("Uploaded by", _uploaded_by_label(update)),
        ("Uploaded on", _format_datetime(update.updated_at or update.created_at)),
    ]
    table = Table(
        [
            [
                Paragraph(escape(label), styles["coverFactLabel"]),
                Paragraph(_safe_text(value), styles["coverFactValue"]),
            ]
            for label, value in rows
        ],
        colWidths=[58 * mm, 112 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.8, PCM_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F7FAFD")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    return table


def _build_meeting_minutes_summary_panel(update: ProgramUpdate, styles, minute_documents: list[dict]):
    extracted_page_count = sum(len(item.get("pages") or []) for item in minute_documents)
    summary_parts = [
        f"<b>Source files:</b> {len(minute_documents) or 0}",
        f"<b>Extracted pages:</b> {extracted_page_count or 0}",
    ]
    if update.summary:
        summary_parts.append(_safe_text(update.summary))
    content = Table(
        [[Paragraph("<br/><br/>".join(summary_parts), styles["callout"])]],
        colWidths=[CONTENT_WIDTH - (4 * mm)],
    )
    content.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF4FF")),
                ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return content


def _build_summary_callout(update: ProgramUpdate, styles):
    metrics = _collect_report_metrics(update)
    content_parts = [f"<b>Calculated insight:</b> {escape(_build_report_insight(metrics))}"]
    if update.summary:
        content_parts.append(_safe_text(update.summary))
    else:
        content_parts.append("No additional narrative summary was provided.")
    card = Table([[Paragraph("<br/><br/>".join(content_parts), styles["callout"])]], colWidths=[CONTENT_WIDTH - (4 * mm)])
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF5FF")),
                ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return card


def _build_narrative_sections(update: ProgramUpdate, styles):
    sections = []
    narrative_rows = [
        ("Outcomes", update.outcomes, colors.HexColor("#EFFAF5")),
        ("Challenges", update.challenges, colors.HexColor("#FFF4F4")),
        ("Next steps", update.next_steps, colors.HexColor("#F4F0FF")),
    ]
    for heading, value, background in narrative_rows:
        if not value:
            continue
        card = Table([[Paragraph(_safe_text(value), styles["body"])]], colWidths=[174 * mm])
        card.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), background),
                    ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        sections.extend([Paragraph(heading, styles["section"]), card, Spacer(1, 10)])

    if not sections:
        sections.append(Paragraph("No additional narrative fields were provided for this update.", styles["bodyMuted"]))
        sections.append(Spacer(1, 8))
    return sections


def _build_gallery(image_attachments: list[dict], styles):
    gallery_rows = []
    row = []
    for attachment in image_attachments:
        tile = _build_gallery_tile(attachment, styles)
        if tile is None:
            continue
        row.append(tile)
        if len(row) == 2:
            gallery_rows.append(row)
            row = []
    if row:
        if len(row) == 1:
            row.append(Spacer(1, 1))
        gallery_rows.append(row)

    if not gallery_rows:
        return Paragraph("No image attachments were available to render in the gallery.", styles["bodyMuted"])

    gallery = Table(gallery_rows, colWidths=[87 * mm, 87 * mm], hAlign="LEFT")
    gallery.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return gallery


def _build_gallery_tile(attachment: dict, styles):
    image_path = attachment["path"]
    scaled = _scaled_image(image_path, 80 * mm, 52 * mm)
    if scaled is None:
        return None
    caption = Paragraph(_safe_text(attachment["name"]), styles["galleryCaption"])
    tile = Table([[scaled], [caption]], colWidths=[84 * mm])
    tile.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return tile


def _build_document_table(document_attachments: list[dict], styles):
    rows = []
    for attachment in document_attachments:
        rows.append(
            [
                Paragraph(_safe_text(attachment["name"]), styles["docName"]),
                Paragraph(
                    _safe_text(
                        " | ".join(
                            part
                            for part in [
                                attachment.get("content_type") or "Document",
                                _format_file_size(attachment.get("size_bytes")),
                            ]
                            if part
                        )
                    ),
                    styles["docMeta"],
                ),
            ]
        )
    table = Table(rows, colWidths=[120 * mm, 54 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.8, PCM_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _decorate_page(canvas, doc, update: ProgramUpdate):
    fonts = _ensure_pdf_fonts()
    canvas.saveState()
    page_width, page_height = A4
    canvas.setFillColor(PCM_BLUE)
    canvas.rect(0, page_height - 24 * mm, page_width, 24 * mm, stroke=0, fill=1)
    canvas.setFillColor(PCM_VIOLET)
    canvas.rect(page_width - 58 * mm, page_height - 24 * mm, 58 * mm, 24 * mm, stroke=0, fill=1)
    canvas.setFillColor(PCM_RED)
    canvas.rect(page_width - 24 * mm, page_height - 24 * mm, 24 * mm, 24 * mm, stroke=0, fill=1)

    logo_path = _logo_path()
    if logo_path:
        canvas.drawImage(str(logo_path), 16 * mm, page_height - 18 * mm, width=12 * mm, height=12 * mm, mask="auto", preserveAspectRatio=True)
        header_x = 31 * mm
    else:
        header_x = 16 * mm

    canvas.setFillColor(colors.white)
    canvas.setFont(fonts["bold"], 11)
    canvas.drawString(header_x, page_height - 11 * mm, "Public Campus Ministries")
    canvas.setFont(fonts["regular"], 8.5)
    canvas.drawString(header_x, page_height - 15.5 * mm, "Impact reporting pack")

    canvas.setStrokeColor(PCM_BORDER)
    canvas.line(doc.leftMargin, 14 * mm, page_width - doc.rightMargin, 14 * mm)
    canvas.setFillColor(PCM_SLATE)
    canvas.setFont(fonts["regular"], 8)
    canvas.drawString(
        doc.leftMargin,
        9.5 * mm,
        _truncate_canvas_text(
            canvas,
            _report_title(update),
            page_width - doc.leftMargin - doc.rightMargin - (24 * mm),
            fonts["regular"],
            8,
        ),
    )
    canvas.drawRightString(page_width - doc.rightMargin, 9.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _decorate_meeting_minutes_page(canvas, doc, update: ProgramUpdate):
    fonts = _ensure_pdf_fonts()
    canvas.saveState()
    page_width, page_height = A4
    canvas.setFillColor(PCM_BLUE)
    canvas.rect(0, page_height - 24 * mm, page_width, 24 * mm, stroke=0, fill=1)
    canvas.setFillColor(PCM_VIOLET)
    canvas.rect(page_width - 58 * mm, page_height - 24 * mm, 58 * mm, 24 * mm, stroke=0, fill=1)
    canvas.setFillColor(PCM_RED)
    canvas.rect(page_width - 24 * mm, page_height - 24 * mm, 24 * mm, 24 * mm, stroke=0, fill=1)

    logo_path = _logo_path()
    if logo_path:
        canvas.drawImage(str(logo_path), 16 * mm, page_height - 18 * mm, width=12 * mm, height=12 * mm, mask="auto", preserveAspectRatio=True)
        header_x = 31 * mm
    else:
        header_x = 16 * mm

    canvas.setFillColor(colors.white)
    canvas.setFont(fonts["bold"], 11)
    canvas.drawString(header_x, page_height - 11 * mm, "Public Campus Ministries")
    canvas.setFont(fonts["regular"], 8.5)
    canvas.drawString(header_x, page_height - 15.5 * mm, "Meeting minutes")

    canvas.setStrokeColor(PCM_BORDER)
    canvas.line(doc.leftMargin, 14 * mm, page_width - doc.rightMargin, 14 * mm)
    canvas.setFillColor(PCM_SLATE)
    canvas.setFont(fonts["regular"], 8)
    canvas.drawString(
        doc.leftMargin,
        9.5 * mm,
        _truncate_canvas_text(
            canvas,
            _meeting_report_title(update),
            page_width - doc.leftMargin - doc.rightMargin - (24 * mm),
            fonts["regular"],
            8,
        ),
    )
    canvas.drawRightString(page_width - doc.rightMargin, 9.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _decorate_meeting_minutes_cover_page(canvas, doc, update: ProgramUpdate):
    fonts = _ensure_pdf_fonts()
    canvas.saveState()
    page_width, page_height = A4
    canvas.setFillColor(colors.HexColor("#F7FAFF"))
    canvas.rect(0, 0, page_width, page_height, stroke=0, fill=1)
    canvas.setFillColor(PCM_BLUE)
    canvas.rect(0, page_height - 38 * mm, page_width, 38 * mm, stroke=0, fill=1)
    canvas.setFillColor(PCM_VIOLET)
    canvas.rect(page_width - 72 * mm, page_height - 38 * mm, 72 * mm, 38 * mm, stroke=0, fill=1)
    canvas.setFillColor(PCM_RED)
    canvas.rect(0, 0, page_width, 12 * mm, stroke=0, fill=1)

    canvas.setStrokeColor(colors.HexColor("#E4EBF7"))
    canvas.line(doc.leftMargin, 24 * mm, page_width - doc.rightMargin, 24 * mm)
    canvas.setFillColor(PCM_SLATE)
    canvas.setFont(fonts["regular"], 8.5)
    canvas.drawString(doc.leftMargin, 17 * mm, "Public Campus Ministries meeting minutes")
    canvas.drawRightString(
        page_width - doc.rightMargin,
        17 * mm,
        _truncate_canvas_text(
            canvas,
            _format_date(update.reporting_date),
            56 * mm,
            fonts["regular"],
            8.5,
        ),
    )
    canvas.restoreState()


def _decorate_cover_page(canvas, doc, update: ProgramUpdate):
    fonts = _ensure_pdf_fonts()
    canvas.saveState()
    page_width, page_height = A4
    canvas.setFillColor(colors.HexColor("#F7FAFF"))
    canvas.rect(0, 0, page_width, page_height, stroke=0, fill=1)
    canvas.setFillColor(PCM_BLUE)
    canvas.rect(0, page_height - 38 * mm, page_width, 38 * mm, stroke=0, fill=1)
    canvas.setFillColor(PCM_VIOLET)
    canvas.rect(page_width - 72 * mm, page_height - 38 * mm, 72 * mm, 38 * mm, stroke=0, fill=1)
    canvas.setFillColor(PCM_RED)
    canvas.rect(0, 0, page_width, 12 * mm, stroke=0, fill=1)

    canvas.setStrokeColor(colors.HexColor("#E4EBF7"))
    canvas.line(doc.leftMargin, 24 * mm, page_width - doc.rightMargin, 24 * mm)
    canvas.setFillColor(PCM_SLATE)
    canvas.setFont(fonts["regular"], 8.5)
    canvas.drawString(doc.leftMargin, 17 * mm, "Public Campus Ministries impact reporting pack")
    canvas.drawRightString(
        page_width - doc.rightMargin,
        17 * mm,
        _truncate_canvas_text(
            canvas,
            update.reporting_period or "Reporting period not set",
            56 * mm,
            fonts["regular"],
            8.5,
        ),
    )
    canvas.restoreState()


def _resolve_attachment_rows(update: ProgramUpdate):
    parsed = []
    if update.attachments_json:
        try:
            loaded = json.loads(update.attachments_json)
            if isinstance(loaded, list):
                parsed = loaded
        except json.JSONDecodeError:
            parsed = []

    resolved_rows = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        stored_name = item.get("stored_name") or item.get("path")
        if not stored_name:
            continue
        file_path = Path(settings.upload_dir) / stored_name
        if not file_path.exists():
            continue
        row = {
            "name": item.get("name") or stored_name,
            "path": file_path,
            "content_type": item.get("content_type"),
            "size_bytes": item.get("size_bytes"),
            "category": item.get("category"),
            "meeting_date": item.get("meeting_date"),
            "venue": item.get("venue"),
            "notes": item.get("notes"),
        }
        resolved_rows.append(row)
    return resolved_rows


def _resolve_attachments(update: ProgramUpdate):
    image_rows = []
    document_rows = []
    for row in _resolve_attachment_rows(update):
        if _is_image_attachment(row["name"], row["content_type"]):
            image_rows.append(row)
        else:
            document_rows.append(row)
    return image_rows, document_rows


def _resolve_minutes_attachments(update: ProgramUpdate) -> list[dict]:
    return [row for row in _resolve_attachment_rows(update) if row.get("category") == "minutes"]


def _logo_path() -> Path | None:
    for candidate in LOGO_PATHS:
        if candidate.exists():
            return candidate
    return None


def _ensure_pdf_fonts() -> dict[str, str]:
    global PDF_FONT_REGISTRATION_ATTEMPTED
    if PDF_FONT_REGISTRATION_ATTEMPTED:
        return PDF_FONT_NAMES

    resolved_paths = {key: _first_existing_path(candidates) for key, candidates in FONT_CANDIDATES.items()}
    if not all(resolved_paths.values()):
        PDF_FONT_REGISTRATION_ATTEMPTED = True
        return PDF_FONT_NAMES

    registered_names = set(pdfmetrics.getRegisteredFontNames())
    font_map = {
        "regular": ("Poppins", resolved_paths["regular"]),
        "semibold": ("Poppins-SemiBold", resolved_paths["semibold"]),
        "bold": ("Poppins-Bold", resolved_paths["bold"]),
    }

    try:
        for _, (font_name, font_path) in font_map.items():
            if font_name not in registered_names:
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
        pdfmetrics.registerFontFamily("Poppins", normal="Poppins", bold="Poppins-Bold")
        PDF_FONT_NAMES.update({key: value[0] for key, value in font_map.items()})
    except Exception:
        pass

    PDF_FONT_REGISTRATION_ATTEMPTED = True
    return PDF_FONT_NAMES


def _first_existing_path(candidates: tuple[Path, ...]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _collect_report_metrics(update: ProgramUpdate) -> dict:
    expected = max(int(update.program.target_beneficiaries or 0), 0) if update.program else 0
    actual = max(int(update.beneficiaries_reached or 0), 0)
    volunteers = max(int(update.volunteers_involved or 0), 0)
    funds_used = update.funds_used
    variance = actual - expected if expected else None
    achievement_rate = ((actual / expected) * 100) if expected else None
    attendees_per_volunteer = (actual / volunteers) if volunteers else None
    return {
        "expected": expected,
        "actual": actual,
        "volunteers": volunteers,
        "funds_used": funds_used,
        "variance": variance,
        "achievement_rate": achievement_rate,
        "attendees_per_volunteer": attendees_per_volunteer,
    }


def _build_cover_metric_items(metrics: dict) -> list[dict]:
    items = [
        {
            "label": "Expected reach",
            "value": _format_number(metrics["expected"]) if metrics["expected"] else "Not set",
            "helper": "Planned from the linked ministry program.",
            "background": colors.HexColor("#EDF4FF"),
        },
        {
            "label": "Actual reach",
            "value": _format_number(metrics["actual"]),
            "helper": "Reported visitors or participation.",
            "background": colors.HexColor("#FFF1F2"),
        },
        {
            "label": "Missionaries",
            "value": _format_number(metrics["volunteers"]),
            "helper": _volunteer_helper_text(metrics),
            "background": colors.HexColor("#F3EEFF"),
        },
    ]

    if metrics["achievement_rate"] is not None:
        items.append(
            {
                "label": "Achievement",
                "value": _format_percent(metrics["achievement_rate"]),
                "helper": _variance_helper_text(metrics),
                "background": colors.HexColor("#EFFAF5"),
            }
        )
    elif metrics["attendees_per_volunteer"] is not None:
        items.append(
            {
                "label": "Missionary coverage",
                "value": _format_coverage(metrics["attendees_per_volunteer"]),
                "helper": "Missionaries relative to reported visitors.",
                "background": colors.HexColor("#EFFAF5"),
            }
        )
    else:
        items.append(
            {
                "label": "Funds used",
                "value": _format_currency(metrics["funds_used"]) if metrics["funds_used"] is not None else "Not reported",
                "helper": "Reported spend for this update.",
                "background": colors.HexColor("#FFF7E8"),
            }
        )
    return items


def _build_detailed_metric_items(metrics: dict) -> list[dict]:
    items = [
        {
            "label": "Expected",
            "value": _format_number(metrics["expected"]) if metrics["expected"] else "Not set",
            "helper": "Planned visitors or reach.",
            "background": colors.HexColor("#EDF4FF"),
        },
        {
            "label": "Actual",
            "value": _format_number(metrics["actual"]),
            "helper": "Reported visitors captured in the update.",
            "background": colors.HexColor("#FFF1F2"),
        },
        {
            "label": "Missionaries",
            "value": _format_number(metrics["volunteers"]),
            "helper": _volunteer_helper_text(metrics),
            "background": colors.HexColor("#F3EEFF"),
        },
    ]

    if metrics["variance"] is not None:
        items.append(
            {
                "label": "Variance",
                "value": _format_signed_number(metrics["variance"]),
                "helper": _variance_helper_text(metrics),
                "background": colors.HexColor("#EFFAF5"),
            }
        )
        items.append(
            {
                "label": "Achievement",
                "value": _format_percent(metrics["achievement_rate"]),
                "helper": "Actual reach as a share of plan.",
                "background": colors.HexColor("#EEF7FF"),
            }
        )

    if metrics["attendees_per_volunteer"] is not None:
        items.append(
            {
                "label": "Coverage",
                "value": _format_coverage(metrics["attendees_per_volunteer"]),
                "helper": "Average visitors supported by each missionary.",
                "background": colors.HexColor("#FFF8E7"),
            }
        )

    if metrics["funds_used"] is not None:
        items.append(
            {
                "label": "Funds used",
                "value": _format_currency(metrics["funds_used"]),
                "helper": "Reported expenditure for this activity.",
                "background": colors.HexColor("#FFF7E8"),
            }
        )

    return items


def _build_metric_grid(items: list[dict], styles, columns: int) -> Table:
    gap = 4 * mm
    card_width = (CONTENT_WIDTH - (gap * (columns - 1))) / columns
    rows = []
    for start in range(0, len(items), columns):
        chunk = items[start:start + columns]
        row = [_build_metric_card(item, styles, card_width) for item in chunk]
        if len(row) < columns:
            row.extend([Spacer(1, 1)] * (columns - len(row)))
        rows.append(row)

    table = Table(rows, colWidths=[card_width] * columns, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _build_metric_card(item: dict, styles, width: float) -> Table:
    helper_text = item.get("helper") or " "
    card = Table(
        [
            [Paragraph(escape(item["label"]), styles["metricLabel"])],
            [Paragraph(escape(item["value"]), styles["metricValue"])],
            [Paragraph(_safe_text(helper_text), styles["metricHelper"])],
        ],
        colWidths=[width],
    )
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), item["background"]),
                ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return card


def _safe_text(value: str) -> str:
    return escape(value).replace("\n", "<br/>")


def _display_event_name(update: ProgramUpdate) -> str:
    if update.event_detail:
        return f"{update.event_name}: {update.event_detail}"
    return update.event_name or update.title or "Impact update"


def _program_schedule(update: ProgramUpdate) -> str:
    if update.program and update.program.start_date and update.program.end_date:
        if update.program.start_date == update.program.end_date:
            return update.program.start_date.strftime("%d %b %Y")
        return f"{update.program.start_date.strftime('%d %b %Y')} to {update.program.end_date.strftime('%d %b %Y')}"
    if update.program and update.program.start_date:
        return update.program.start_date.strftime("%d %b %Y")
    return "Date not scheduled"


def _format_duration(duration_weeks: float | None) -> str:
    if duration_weeks is None:
        return "Not recorded"
    if duration_weeks < 1:
        days = max(1, round(duration_weeks * 7))
        return f"{days} day{'s' if days != 1 else ''}"
    if float(duration_weeks).is_integer():
        weeks = int(duration_weeks)
        return f"{weeks} week{'s' if weeks != 1 else ''}"
    return f"{duration_weeks:.1f} weeks"


def _format_number(value: int | float | None) -> str:
    return f"{int(value or 0):,}"


def _format_signed_number(value: int | float | None) -> str:
    numeric = int(value or 0)
    if numeric > 0:
        return f"+{numeric:,}"
    return f"{numeric:,}"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "Not set"
    return f"{value:.0f}%"


def _format_coverage(value: float | None) -> str:
    if value is None:
        return "Not set"
    rounded = round(value, 1)
    if float(rounded).is_integer():
        return f"1 : {int(rounded)}"
    return f"1 : {rounded:.1f}"


def _format_currency(value: int | float | None) -> str:
    return f"${value or 0:,.0f}"


def _format_datetime(value) -> str:
    if not value:
        return "No date"
    return value.strftime("%d %b %Y, %H:%M")


def _format_date(value) -> str:
    if not value:
        return "No date"
    return value.strftime("%d %b %Y")


def _format_file_size(size_bytes: int | None) -> str:
    if not size_bytes:
        return ""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes} B"


def _report_title(update: ProgramUpdate) -> str:
    university_name = update.university.short_code if update.university and update.university.short_code else (update.university.name if update.university else "network")
    return f"{university_name}_{update.reporting_period}_{_display_event_name(update)}"


def _meeting_report_title(update: ProgramUpdate) -> str:
    university_name = update.university.short_code if update.university and update.university.short_code else (update.university.name if update.university else "network")
    return f"{university_name}_{update.reporting_period}_meeting_minutes"


def _slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "impact_report"


def _is_meeting_update(update: ProgramUpdate) -> bool:
    return (update.event_name or update.title or "").strip().lower() == "meeting"


def _meeting_date_value(update: ProgramUpdate, minute_document: dict | None = None):
    if minute_document and minute_document.get("meeting_date"):
        try:
            return date.fromisoformat(str(minute_document["meeting_date"]))
        except ValueError:
            pass
    return update.reporting_date


def _uploaded_by_label(update: ProgramUpdate) -> str:
    if getattr(update, "submitter", None) and update.submitter.name:
        return update.submitter.name
    return "PCM system"


def _build_meeting_minutes_content(update: ProgramUpdate, styles, minute_documents: list[dict]):
    if not minute_documents:
        return [
            Paragraph("Minutes content", styles["section"]),
            Paragraph("No readable meeting-minutes attachment was found for this update.", styles["bodyMuted"]),
        ]

    content = [Paragraph("Original minutes content", styles["section"])]
    for index, document in enumerate(minute_documents):
        content.append(Paragraph(_safe_text(document["name"]), styles["docName"]))
        content.append(
            Paragraph(
                _safe_text(
                    " | ".join(
                        part
                        for part in [
                            document.get("meeting_date") or _format_date(update.reporting_date),
                            document.get("venue") or "Venue not recorded",
                            document.get("content_type") or "Document",
                        ]
                        if part
                    )
                ),
                styles["docMeta"],
            )
        )
        content.append(Spacer(1, 6))
        if document.get("blocks"):
            content.extend(_build_meeting_minutes_structured_blocks(document["blocks"], styles))
        else:
            for page_number, page_text in enumerate(document.get("pages") or [], start=1):
                if page_number > 1:
                    content.append(Spacer(1, 8))
                content.append(Paragraph(f"Source page {page_number}", styles["tableLabel"]))
                content.append(Spacer(1, 4))
                content.extend(_build_meeting_minutes_text_blocks(page_text, styles))
                content.append(Spacer(1, 10))
        if index < len(minute_documents) - 1:
            content.append(PageBreak())
    return content


def _build_meeting_minutes_text_blocks(text: str, styles):
    normalized = _normalize_extracted_text(text)
    if not normalized:
        return [Paragraph("No readable text could be rendered for this source page.", styles["bodyMuted"])]
    return [
        Preformatted(
            normalized,
            styles["minutesContent"],
            maxLineLength=98,
        )
    ]


def _build_meeting_minutes_structured_blocks(blocks: list[dict], styles):
    flowables = []
    for block in blocks:
        built = _build_meeting_minutes_structured_block(block, styles)
        if not built:
            continue
        if isinstance(built, list):
            flowables.extend(built)
        else:
            flowables.append(built)
    return flowables


def _build_meeting_minutes_structured_block(block: dict, styles):
    block_type = block.get("type")
    if block_type == "heading":
        return [Paragraph(block["markup"], styles["minutesHeading"]), Spacer(1, 1)]
    if block_type == "bullet":
        return [
            Paragraph(
                block["markup"],
                _minutes_bullet_style(styles, block.get("level", 0)),
                bulletText="•",
            )
        ]
    if block_type == "table":
        return [_build_meeting_minutes_table(block, styles), Spacer(1, 8)]
    if block_type == "spacer":
        return [Spacer(1, 6)]
    if block_type == "paragraph":
        return [Paragraph(block["markup"], styles["minutesParagraph"])]
    return None


def _minutes_bullet_style(styles, level: int):
    level = max(int(level or 0), 0)
    base = styles["minutesBullet"]
    return ParagraphStyle(
        f"minutesBulletLevel{level}",
        parent=base,
        leftIndent=base.leftIndent + (level * 11),
        bulletIndent=base.bulletIndent + (level * 11),
    )


def _build_meeting_minutes_table(block: dict, styles):
    rows = _normalize_minutes_table_rows(block.get("rows") or [])
    if not rows:
        return Spacer(1, 0)

    column_count = len(rows[0])
    table_rows = []
    has_header = bool(block.get("header"))
    for row_index, row in enumerate(rows):
        cells = []
        for cell in row:
            paragraph_style = styles["minutesTableHeader"] if has_header and row_index == 0 else styles["minutesTableCell"]
            cells.append(Paragraph(cell["markup"], paragraph_style))
        table_rows.append(cells)

    column_width = CONTENT_WIDTH / max(column_count, 1)
    table = Table(
        table_rows,
        colWidths=[column_width] * column_count,
        repeatRows=1 if has_header else 0,
        splitByRow=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, PCM_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, PCM_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F7FF") if has_header else colors.white),
            ]
        )
    )
    return table


def _normalize_minutes_table_rows(rows: list[list[dict]]) -> list[list[dict]]:
    if not rows:
        return []

    column_count = max(len(row) for row in rows)
    normalized_rows = []
    for row in rows:
        normalized = list(row)
        while len(normalized) < column_count:
            normalized.append({"markup": "&nbsp;", "has_bold": False})
        normalized_rows.append(normalized)
    return normalized_rows


def _extract_meeting_minutes_documents(update: ProgramUpdate) -> list[dict]:
    documents = []
    for attachment in _resolve_minutes_attachments(update):
        path = attachment["path"]
        suffix = path.suffix.lower()
        blocks = []
        if suffix == ".docx" or _looks_like_docx(path):
            blocks = _extract_docx_blocks(path)
        elif suffix == ".doc":
            blocks = _extract_doc_blocks(path)

        if blocks:
            documents.append({**attachment, "blocks": blocks})
            continue

        pages = _extract_minutes_attachment_pages(attachment)
        documents.append({**attachment, "pages": pages})
    return documents


def _extract_minutes_attachment_pages(attachment: dict) -> list[str]:
    path = attachment["path"]
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            pages = _extract_pdf_pages(path)
        elif suffix == ".docx" or _looks_like_docx(path):
            pages = _extract_docx_pages(path)
        elif suffix == ".doc":
            pages = _extract_doc_pages(path)
        else:
            pages = []
    except Exception:
        pages = []

    if pages:
        return pages

    return [
        "\n".join(
            [
                f"Original file: {attachment['name']}",
                "PCM could not extract readable text from this minutes document.",
                "The original file remains stored in the system attachments.",
            ]
        )
    ]


def _extract_pdf_pages(path: Path) -> list[str]:
    pages = _extract_pdf_text_pages(path)
    if pages:
        return pages
    return _extract_pdf_ocr_pages(path)


def _extract_pdf_text_pages(path: Path) -> list[str]:
    reader_class = _load_pdf_reader_class()
    if reader_class is None:
        return []

    pages = []
    reader = reader_class(str(path))
    for page in reader.pages:
        text = _normalize_extracted_text(page.extract_text() or "")
        if text:
            pages.append(text)
    return pages


def _extract_pdf_ocr_pages(path: Path) -> list[str]:
    renderer_module = _load_pdf_renderer_module()
    ocr_engine = _load_ocr_engine()
    if renderer_module is None or ocr_engine is None:
        return []

    try:
        pdf_document = renderer_module.open(str(path))
    except Exception:
        return []

    pages = []
    try:
        matrix = renderer_module.Matrix(2, 2)
        for page in pdf_document:
            try:
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                page_text = _extract_ocr_text_from_png_bytes(pixmap.tobytes("png"), ocr_engine)
            except Exception:
                continue
            if page_text:
                pages.append(page_text)
    finally:
        try:
            pdf_document.close()
        except Exception:
            pass
    return pages


def _extract_docx_blocks(path: Path) -> list[dict]:
    try:
        with ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (KeyError, BadZipFile):
        return []

    root = ElementTree.fromstring(xml_bytes)
    body = root.find(f"{WORDPROCESSING_NS}body")
    if body is None:
        return []

    blocks = []
    for child in body:
        if child.tag == f"{WORDPROCESSING_NS}p":
            block = _extract_docx_paragraph_block(child)
        elif child.tag == f"{WORDPROCESSING_NS}tbl":
            block = _extract_docx_table_block(child)
        else:
            block = None
        if block:
            blocks.append(block)
    return blocks


def _extract_docx_pages(path: Path) -> list[str]:
    try:
        with ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (KeyError, BadZipFile):
        return []

    root = ElementTree.fromstring(xml_bytes)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t")).strip()
        if text:
            paragraphs.append(text)
    return _chunk_minutes_paragraphs(paragraphs)


def _extract_doc_blocks(path: Path) -> list[dict]:
    if not (shutil.which("soffice") or shutil.which("libreoffice")):
        return []

    converted_docx = _convert_doc_to_docx(path)
    if converted_docx is None:
        return []
    try:
        return _extract_docx_blocks(converted_docx)
    finally:
        _cleanup_temp_path(converted_docx)


def _extract_doc_pages(path: Path) -> list[str]:
    extracted_text = _run_legacy_doc_extractor(path)
    if extracted_text:
        return _chunk_plain_text(extracted_text)

    if shutil.which("soffice") or shutil.which("libreoffice"):
        converted_docx = _convert_doc_to_docx(path)
        if converted_docx is not None:
            try:
                return _extract_docx_pages(converted_docx)
            finally:
                _cleanup_temp_path(converted_docx)
    return []


def _extract_docx_paragraph_block(paragraph) -> dict | None:
    fragments = _docx_paragraph_fragments(paragraph)
    plain_text = "".join(fragment["text"] for fragment in fragments).strip()
    if not plain_text:
        return {"type": "spacer"}

    markup = _docx_fragments_to_markup(fragments)
    if not markup:
        return {"type": "spacer"}

    list_level = _docx_list_level(paragraph)
    if list_level is not None:
        return {"type": "bullet", "level": list_level, "markup": markup}
    if _docx_paragraph_is_heading(paragraph, fragments, plain_text):
        return {"type": "heading", "markup": markup}
    return {"type": "paragraph", "markup": markup}


def _docx_paragraph_fragments(paragraph) -> list[dict]:
    fragments: list[dict] = []
    for child in paragraph:
        if child.tag == f"{WORDPROCESSING_NS}r":
            _append_docx_run_fragments(fragments, child)
        elif child.tag == f"{WORDPROCESSING_NS}hyperlink":
            for run in child.findall(f"{WORDPROCESSING_NS}r"):
                _append_docx_run_fragments(fragments, run)
    return fragments


def _append_docx_run_fragments(fragments: list[dict], run) -> None:
    text_parts = []
    for node in run:
        if node.tag == f"{WORDPROCESSING_NS}t":
            text_parts.append(node.text or "")
        elif node.tag == f"{WORDPROCESSING_NS}tab":
            text_parts.append("\t")
        elif node.tag in {f"{WORDPROCESSING_NS}br", f"{WORDPROCESSING_NS}cr"}:
            text_parts.append("\n")
    text = "".join(text_parts)
    if not text:
        return

    is_bold = run.find(f"{WORDPROCESSING_NS}rPr/{WORDPROCESSING_NS}b") is not None or run.find(
        f"{WORDPROCESSING_NS}rPr/{WORDPROCESSING_NS}bCs"
    ) is not None
    if fragments and fragments[-1]["bold"] == is_bold:
        fragments[-1]["text"] += text
    else:
        fragments.append({"text": text, "bold": is_bold})


def _docx_list_level(paragraph) -> int | None:
    level = paragraph.find(f"{WORDPROCESSING_NS}pPr/{WORDPROCESSING_NS}numPr/{WORDPROCESSING_NS}ilvl")
    if level is None:
        return None
    try:
        return int(level.get(f"{WORDPROCESSING_NS}val") or 0)
    except (TypeError, ValueError):
        return 0


def _docx_paragraph_is_heading(paragraph, fragments: list[dict], plain_text: str) -> bool:
    style_id = _docx_paragraph_style_id(paragraph)
    if style_id and any(token in style_id.lower() for token in ("heading", "title", "subtitle")):
        return True
    if len(plain_text) > 120:
        return False
    bold_fragments = [fragment for fragment in fragments if fragment["text"].strip()]
    return bool(bold_fragments) and all(fragment["bold"] for fragment in bold_fragments)


def _docx_paragraph_style_id(paragraph) -> str | None:
    style = paragraph.find(f"{WORDPROCESSING_NS}pPr/{WORDPROCESSING_NS}pStyle")
    if style is None:
        return None
    return style.get(f"{WORDPROCESSING_NS}val")


def _docx_fragments_to_markup(fragments: list[dict]) -> str:
    markup_parts = []
    for fragment in fragments:
        if not fragment["text"]:
            continue
        escaped_text = _escape_minutes_markup_text(fragment["text"])
        if fragment["bold"]:
            markup_parts.append(f"<b>{escaped_text}</b>")
        else:
            markup_parts.append(escaped_text)
    return "".join(markup_parts).strip()


def _escape_minutes_markup_text(value: str) -> str:
    escaped_value = escape(value.replace("\t", "    "))
    while "  " in escaped_value:
        escaped_value = escaped_value.replace("  ", "&nbsp; ")
    return escaped_value.replace("\n", "<br/>")


def _extract_docx_table_block(table) -> dict | None:
    rows = []
    for row in table.findall(f"{WORDPROCESSING_NS}tr"):
        cells = []
        for cell in row.findall(f"{WORDPROCESSING_NS}tc"):
            markup, has_bold = _extract_docx_cell_markup(cell)
            cells.append({"markup": markup or "&nbsp;", "has_bold": has_bold})
        if any(cell["markup"].strip() != "&nbsp;" for cell in cells):
            rows.append(cells)
    if not rows:
        return None

    first_row = rows[0]
    header_cells = [cell for cell in first_row if cell["markup"].strip() != "&nbsp;"]
    header = bool(header_cells) and all(cell["has_bold"] for cell in header_cells)
    return {"type": "table", "rows": rows, "header": header}


def _extract_docx_cell_markup(cell) -> tuple[str, bool]:
    paragraphs = []
    has_bold = False
    for paragraph in cell.findall(f"{WORDPROCESSING_NS}p"):
        fragments = _docx_paragraph_fragments(paragraph)
        if not fragments:
            continue
        markup = _docx_fragments_to_markup(fragments)
        if markup:
            paragraphs.append(markup)
            has_bold = has_bold or any(fragment["bold"] for fragment in fragments if fragment["text"].strip())
    return "<br/><br/>".join(paragraphs), has_bold


def _chunk_minutes_paragraphs(paragraphs: list[str], char_limit: int = 2800) -> list[str]:
    if not paragraphs:
        return []

    chunks = []
    current: list[str] = []
    current_length = 0
    for paragraph in paragraphs:
        addition = len(paragraph) + (2 if current else 0)
        if current and current_length + addition > char_limit:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_length = len(paragraph)
        else:
            current.append(paragraph)
            current_length += addition
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _chunk_plain_text(text: str, char_limit: int = 2800) -> list[str]:
    normalized = _normalize_extracted_text(text)
    if not normalized:
        return []
    paragraphs = [paragraph.strip() for paragraph in normalized.split("\n\n") if paragraph.strip()]
    return _chunk_minutes_paragraphs(paragraphs, char_limit=char_limit)


def _normalize_extracted_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r", "\n").split("\n")]
    cleaned = []
    previous_blank = False
    for line in lines:
        normalized = line.strip()
        if not normalized:
            if not previous_blank:
                cleaned.append("")
            previous_blank = True
            continue
        cleaned.append(normalized)
        previous_blank = False
    return "\n".join(cleaned).strip()


def _looks_like_docx(path: Path) -> bool:
    try:
        with ZipFile(path) as archive:
            return "word/document.xml" in archive.namelist()
    except BadZipFile:
        return False


def _load_pdf_reader_class():
    for module_name in ("pypdf", "PyPDF2"):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        reader_class = getattr(module, "PdfReader", None)
        if reader_class is not None:
            return reader_class
    return None


def _load_pdf_renderer_module():
    for module_name in ("pymupdf", "fitz"):
        try:
            return importlib.import_module(module_name)
        except ImportError:
            continue
    return None


def _load_ocr_engine():
    global OCR_ENGINE, OCR_ENGINE_ATTEMPTED
    if OCR_ENGINE_ATTEMPTED:
        return OCR_ENGINE

    OCR_ENGINE_ATTEMPTED = True
    try:
        rapidocr_module = importlib.import_module("rapidocr_onnxruntime")
    except ImportError:
        OCR_ENGINE = None
        return OCR_ENGINE

    engine_class = getattr(rapidocr_module, "RapidOCR", None)
    if engine_class is None:
        OCR_ENGINE = None
        return OCR_ENGINE

    try:
        OCR_ENGINE = engine_class()
    except Exception:
        OCR_ENGINE = None
    return OCR_ENGINE


def _extract_ocr_text_from_png_bytes(image_bytes: bytes, ocr_engine) -> str:
    pil_image_module = importlib.import_module("PIL.Image")
    numpy_module = importlib.import_module("numpy")

    image = pil_image_module.open(BytesIO(image_bytes)).convert("RGB")
    ocr_result, _ = ocr_engine(numpy_module.array(image))
    lines = []
    for row in ocr_result or []:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        text = str(row[1]).strip()
        if text:
            lines.append(text)
    return _normalize_extracted_text("\n".join(lines))


def _run_legacy_doc_extractor(path: Path) -> str | None:
    commands = [
        ["antiword", "-w", "0", str(path)],
        ["catdoc", str(path)],
    ]
    for command in commands:
        if not shutil.which(command[0]):
            continue
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError:
            continue
        if result.returncode != 0:
            continue
        normalized = _normalize_extracted_text(result.stdout)
        if normalized:
            return normalized
    return None


def _convert_doc_to_docx(path: Path) -> Path | None:
    office_binary = shutil.which("soffice") or shutil.which("libreoffice")
    if not office_binary:
        return None

    with tempfile.TemporaryDirectory() as temp_dir:
        target_dir = Path(temp_dir)
        try:
            result = subprocess.run(
                [
                    office_binary,
                    "--headless",
                    "--convert-to",
                    "docx",
                    "--outdir",
                    str(target_dir),
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if result.returncode != 0:
            return None

        converted_path = target_dir / f"{path.stem}.docx"
        if not converted_path.exists():
            return None

        converted_bytes = converted_path.read_bytes()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
        temp_file.write(converted_bytes)
        persistent_path = Path(temp_file.name)
    try:
        return persistent_path
    except OSError:
        return None


def _cleanup_temp_path(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _scaled_image(path: Path, max_width: float, max_height: float):
    try:
        image_reader = ImageReader(str(path))
        width, height = image_reader.getSize()
    except Exception:
        return None
    if not width or not height:
        return None
    scale = min(max_width / width, max_height / height)
    scale = min(scale, 1)
    image = Image(str(path), width=width * scale, height=height * scale)
    image.hAlign = "CENTER"
    return image


def _is_image_attachment(name: str, content_type: str | None) -> bool:
    if content_type and content_type.startswith("image/"):
        return True
    suffix = Path(name).suffix.lower()
    return suffix in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def _build_report_insight(metrics: dict, include_funds: bool = True) -> str:
    parts = []
    if metrics["achievement_rate"] is not None:
        variance = metrics["variance"] or 0
        if variance > 0:
            parts.append(
                f"Actual participation exceeded the target by {_format_number(variance)}, delivering {_format_percent(metrics['achievement_rate'])} of plan."
            )
        elif variance < 0:
            parts.append(
                f"Actual participation reached {_format_percent(metrics['achievement_rate'])} of target, finishing {_format_number(abs(variance))} below plan."
            )
        else:
            parts.append("Actual participation matched the planned target exactly at 100% achievement.")
    else:
        parts.append(
            f"{_format_number(metrics['actual'])} participants were reported for this activity."
        )

    if metrics["volunteers"]:
        parts.append(_volunteer_helper_text(metrics))

    if include_funds and metrics["funds_used"] is not None:
        parts.append(f"Reported spend was {_format_currency(metrics['funds_used'])}.")

    return " ".join(parts)


def _volunteer_helper_text(metrics: dict) -> str:
    if metrics["attendees_per_volunteer"] is None:
        return "No missionaries were recorded for this update."
    rounded = round(metrics["attendees_per_volunteer"], 1)
    if float(rounded).is_integer():
        ratio_value = str(int(rounded))
    else:
        ratio_value = f"{rounded:.1f}"
    return f"About 1 missionary supported every {ratio_value} visitors."


def _variance_helper_text(metrics: dict) -> str:
    if metrics["variance"] is None:
        return "No target was configured for this activity."
    variance = metrics["variance"]
    if variance > 0:
        return f"{_format_number(variance)} above target."
    if variance < 0:
        return f"{_format_number(abs(variance))} below target."
    return "Matched the planned target exactly."


def _truncate_canvas_text(canvas, value: str, max_width: float, font_name: str, font_size: float) -> str:
    if canvas.stringWidth(value, font_name, font_size) <= max_width:
        return value

    ellipsis = "..."
    clipped = value
    while clipped and canvas.stringWidth(f"{clipped}{ellipsis}", font_name, font_size) > max_width:
        clipped = clipped[:-1]
    clipped = clipped.rstrip(" _-:,.;/")
    return f"{clipped}{ellipsis}" if clipped else ellipsis


def _wrap_text(value: str, limit: int) -> list[str]:
    if len(value) <= limit:
        return [value]
    words = value.split()
    lines = []
    current = ""
    for word in words:
        tentative = f"{current} {word}".strip()
        if len(tentative) <= limit:
            current = tentative
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines[:4]
