from collections import Counter
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import ProgramUpdate
from .program_update_exports import (
    CONTENT_WIDTH,
    PCM_BLUE,
    PCM_BORDER,
    PCM_GOLD,
    PCM_RED,
    PCM_SKY,
    PCM_SLATE,
    PCM_SURFACE,
    PCM_VIOLET,
    _build_document_table,
    _build_gallery,
    _build_metric_grid,
    _build_report_insight,
    _build_styles,
    _ensure_pdf_fonts,
    _format_currency,
    _format_datetime,
    _format_duration,
    _format_number,
    _logo_path,
    _resolve_attachments,
    _safe_text,
    _scaled_image,
    _slugify,
    _truncate_canvas_text,
)

CONFERENCE_CHART_PALETTE = [
    PCM_BLUE,
    PCM_VIOLET,
    PCM_RED,
    PCM_SKY,
    PCM_GOLD,
    colors.HexColor("#2E8B57"),
]


def build_consolidated_program_update_pdf(updates: list[ProgramUpdate]) -> bytes:
    if not updates:
        raise ValueError("At least one program update is required")

    summary = _collect_consolidated_summary(updates)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=34 * mm,
        bottomMargin=16 * mm,
        title=summary["title"],
        author="Public Campus Ministries",
    )
    styles = _build_styles()

    story = [
        *_build_consolidated_cover_page(summary, styles),
        PageBreak(),
        _build_consolidated_hero(summary, styles),
        Spacer(1, 8),
        _build_consolidated_metric_cards(summary, styles),
        Spacer(1, 12),
        _build_consolidated_activity_chart(summary, styles),
        PageBreak(),
        _build_actual_reach_by_reporting_period_chart(summary, styles),
        Spacer(1, 10),
        _build_actual_reach_by_conference_chart(summary, styles),
        PageBreak(),
        _build_conference_distribution_chart(summary, styles),
        PageBreak(),
        Paragraph("Program context", styles["section"]),
        _build_consolidated_context_table(summary, styles),
        Spacer(1, 10),
        Paragraph("Narrative summary", styles["section"]),
        _build_consolidated_summary_callout(summary, styles),
        Spacer(1, 10),
    ]

    story.extend(_build_consolidated_narrative_sections(summary, styles))

    if summary["image_attachments"]:
        story.extend(
            [
                PageBreak(),
                Paragraph("Evidence gallery", styles["section"]),
                Paragraph(
                    "Images uploaded across the included campus reports are combined below as a single visual evidence gallery.",
                    styles["bodyMuted"],
                ),
                Spacer(1, 8),
                _build_gallery(summary["image_attachments"], styles),
            ]
        )

    if summary["document_attachments"]:
        story.extend(
            [
                Spacer(1, 12),
                Paragraph("Supporting documents", styles["section"]),
                Paragraph(
                    "Documents attached to the included campus reports are listed here as a consolidated reference set.",
                    styles["bodyMuted"],
                ),
                Spacer(1, 6),
                _build_document_table(summary["document_attachments"], styles),
            ]
        )

    doc.build(
        story,
        onFirstPage=lambda canvas, built_doc: _decorate_consolidated_cover_page(canvas, built_doc, summary),
        onLaterPages=lambda canvas, built_doc: _decorate_consolidated_page(canvas, built_doc, summary),
    )
    return buffer.getvalue()


def _collect_consolidated_summary(updates: list[ProgramUpdate]) -> dict:
    sorted_updates = sorted(updates, key=_update_timestamp, reverse=True)
    campus_names: set[str] = set()
    conference_counter: Counter[str] = Counter()
    conference_reach_counter: Counter[str] = Counter()
    union_names: set[str] = set()
    reporting_periods: set[str] = set()
    reporting_period_reach_counter: Counter[str] = Counter()
    event_names: set[str] = set()
    program_names: set[str] = set()
    audience_names: set[str] = set()
    image_attachments: list[dict] = []
    document_attachments: list[dict] = []
    section_entries = {
        "summary": [],
        "outcomes": [],
        "challenges": [],
        "next_steps": [],
    }

    expected_total = 0
    actual_total = 0
    volunteers_total = 0
    funds_total = 0.0
    seen_program_ids: set[int] = set()
    schedule_starts = []
    schedule_ends = []

    for update in sorted_updates:
        campus_name = update.university.name if update.university and update.university.name else "Campus not assigned"
        campus_names.add(campus_name)
        conference_name = (
            update.university.conference.name
            if update.university and update.university.conference and update.university.conference.name
            else "Unassigned conference"
        )
        conference_counter[conference_name] += 1
        if update.university and update.university.conference and update.university.conference.union_name:
            union_names.add(update.university.conference.union_name)
        if update.reporting_period:
            reporting_periods.add(update.reporting_period)

        event_label = _display_event_name(update)
        event_names.add(event_label)
        if update.program and update.program.name:
            program_names.add(update.program.name)
        if update.program and update.program.audience:
            audience_names.add(update.program.audience)
        else:
            audience_names.add("General")

        if update.program:
            program_identifier = getattr(update.program, "id", None)
            if program_identifier is None or program_identifier not in seen_program_ids:
                expected_total += max(int(update.program.target_beneficiaries or 0), 0)
                if program_identifier is not None:
                    seen_program_ids.add(program_identifier)
            program_start = update.program.start_date or update.program.end_date
            program_end = update.program.end_date or update.program.start_date
            if program_start:
                schedule_starts.append(program_start)
            if program_end:
                schedule_ends.append(program_end)

        actual_reach = max(int(update.beneficiaries_reached or 0), 0)
        actual_total += actual_reach
        volunteers_total += max(int(update.volunteers_involved or 0), 0)
        funds_total += float(update.funds_used or 0)
        conference_reach_counter[conference_name] += actual_reach
        reporting_period_label = update.reporting_period or "No reporting period"
        reporting_period_reach_counter[reporting_period_label] += actual_reach

        summary_meta = f"{event_label} | {reporting_period_label}"
        detailed_meta = f"{campus_name} | {event_label} | {reporting_period_label}"
        if update.summary:
            section_entries["summary"].append({"meta": summary_meta, "text": update.summary})
        if update.outcomes:
            section_entries["outcomes"].append({"meta": detailed_meta, "text": update.outcomes})
        if update.challenges:
            section_entries["challenges"].append({"meta": detailed_meta, "text": update.challenges})
        if update.next_steps:
            section_entries["next_steps"].append({"meta": detailed_meta, "text": update.next_steps})

        update_images, update_documents = _resolve_attachments(update)
        for attachment in update_images:
            image_attachments.append(
                {
                    **attachment,
                    "name": f"{campus_name} | {event_label} | {attachment['name']}",
                }
            )
        for attachment in update_documents:
            document_attachments.append(
                {
                    **attachment,
                    "name": f"{campus_name} | {event_label} | {attachment['name']}",
                }
            )

    metrics = _build_consolidated_metrics(expected_total, actual_total, volunteers_total, funds_total)
    scope_label = "All campuses" if len(campus_names) != 1 else next(iter(campus_names), "PCM network")
    conference_rows = _build_ranked_rows(conference_counter, limit=6, other_label="Other conferences")

    return {
        "title": "Consolidated Impact Report",
        "scope_label": scope_label,
        "campus_names": sorted(campus_names),
        "campus_count": len(campus_names),
        "conference_counter": conference_counter,
        "conference_rows": conference_rows,
        "conference_count": len(conference_counter),
        "conference_summary": _summarize_names([label for label, _ in conference_rows], empty_value="No conferences assigned"),
        "conference_reach_rows": _build_ranked_rows(conference_reach_counter, limit=6, other_label="Other conferences"),
        "union_summary": _summarize_names(sorted(union_names), empty_value="No union assigned"),
        "reporting_periods": sorted(reporting_periods),
        "reporting_period_label": _summarize_names(sorted(reporting_periods), empty_value="All reporting periods"),
        "reporting_period_reach_rows": _build_ranked_rows(reporting_period_reach_counter, limit=6, other_label="Other periods"),
        "event_names": sorted(event_names),
        "event_summary": _summarize_names(sorted(event_names), empty_value="Multiple event records"),
        "program_summary": _summarize_names(sorted(program_names), empty_value="Multiple linked and unlinked program records"),
        "audience_summary": _summarize_names(sorted(audience_names), empty_value="General"),
        "update_count": len(sorted_updates),
        "metrics": metrics,
        "schedule_label": _format_schedule_span(schedule_starts, schedule_ends),
        "generated_at": max((_update_timestamp(update) for update in sorted_updates), default=None),
        "summary_highlights": [
            f"{entry['meta']}: {_condense_text(entry['text'], 180)}"
            for entry in section_entries["summary"][:3]
        ],
        "section_entries": section_entries,
        "image_attachments": image_attachments,
        "document_attachments": document_attachments,
    }


def _build_consolidated_metrics(expected_total: int, actual_total: int, volunteers_total: int, funds_total: float) -> dict:
    variance = actual_total - expected_total if expected_total else None
    achievement_rate = ((actual_total / expected_total) * 100) if expected_total else None
    attendees_per_volunteer = (actual_total / volunteers_total) if volunteers_total else None
    return {
        "expected": expected_total,
        "actual": actual_total,
        "volunteers": volunteers_total,
        "funds_used": round(funds_total, 2),
        "variance": variance,
        "achievement_rate": achievement_rate,
        "attendees_per_volunteer": attendees_per_volunteer,
    }


def _build_consolidated_cover_page(summary: dict, styles):
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
            Paragraph("Consolidated Impact Report", styles["coverTitle"]),
            Spacer(1, 2 * mm),
            Paragraph(_safe_text(summary["scope_label"]), styles["coverSubtitle"]),
            Spacer(1, 8 * mm),
            _build_cover_identity_table(summary, styles),
            Spacer(1, 7 * mm),
            _build_cover_snapshot_table(summary, styles),
            Spacer(1, 7 * mm),
            _build_cover_summary_panel(summary, styles),
        ]
    )
    return cover_elements


def _build_cover_identity_table(summary: dict, styles):
    rows = [
        ("University / campus", summary["scope_label"]),
        ("Conference", summary["conference_summary"]),
        ("Union", summary["union_summary"]),
        ("Reporting period", summary["reporting_period_label"]),
        ("Schedule span", summary["schedule_label"]),
        ("Generated", _format_datetime(summary["generated_at"])),
    ]
    return _build_key_value_table(
        rows,
        styles,
        label_style_key="coverFactLabel",
        value_style_key="coverFactValue",
        label_width=58 * mm,
        value_width=112 * mm,
        align_right=True,
    )


def _build_cover_snapshot_table(summary: dict, styles):
    items = [
        {
            "label": "Updates combined",
            "value": _format_number(summary["update_count"]),
            "helper": "Narrative submissions included in this report.",
            "background": colors.HexColor("#EDF4FF"),
        },
        {
            "label": "Campuses included",
            "value": _format_number(summary["campus_count"]),
            "helper": "Universities or campuses represented in the dataset.",
            "background": colors.HexColor("#F3EEFF"),
        },
        {
            "label": "People reached",
            "value": _format_number(summary["metrics"]["actual"]),
            "helper": "Combined reach reported across all included updates.",
            "background": colors.HexColor("#FFF1F2"),
        },
        {
            "label": "Conferences covered",
            "value": _format_number(summary["conference_count"]),
            "helper": "Conference groups represented in the current scope.",
            "background": colors.HexColor("#EFFAF5"),
        },
    ]
    return _build_metric_grid(items, styles, columns=2)


def _build_cover_summary_panel(summary: dict, styles):
    intro = (
        f"This consolidated report combines {_format_number(summary['update_count'])} campus update"
        f"{'' if summary['update_count'] == 1 else 's'} from {_format_number(summary['campus_count'])} campus"
        f"{'' if summary['campus_count'] == 1 else 'es'}."
    )
    content_parts = [f"<b>Calculated insight:</b> {escape(_build_report_insight(summary['metrics']))}", intro]
    if summary["summary_highlights"]:
        content_parts.append(
            "<b>Recent highlights:</b><br/>" + "<br/>".join(f"- {escape(item)}" for item in summary["summary_highlights"])
        )

    content = Table([[Paragraph("<br/><br/>".join(content_parts), styles["callout"])]], colWidths=[CONTENT_WIDTH - (4 * mm)])
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


def _build_consolidated_hero(summary: dict, styles):
    title = f"{summary['scope_label']} consolidated impact report"
    right_note = "<br/>".join(
        [
            f"<b>Reporting period:</b> {escape(summary['reporting_period_label'])}",
            f"<b>Generated:</b> {_format_datetime(summary['generated_at'])}",
            f"<b>Audience:</b> {escape(summary['audience_summary'])}",
        ]
    )
    hero = Table(
        [[
            Paragraph(
                f"{escape(title)}<br/><font size='10'>{escape(summary['conference_summary'])} | {escape(summary['schedule_label'])}</font>",
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


def _build_consolidated_metric_cards(summary: dict, styles):
    items = [
        {
            "label": "Updates",
            "value": _format_number(summary["update_count"]),
            "helper": "Narrative submissions combined in this PDF.",
            "background": colors.HexColor("#EDF4FF"),
        },
        {
            "label": "Campuses",
            "value": _format_number(summary["campus_count"]),
            "helper": "Distinct campuses represented in the report scope.",
            "background": colors.HexColor("#F3EEFF"),
        },
        {
            "label": "Expected reach",
            "value": _format_number(summary["metrics"]["expected"]) if summary["metrics"]["expected"] else "Not set",
            "helper": "Combined target reach from linked ministry programs.",
            "background": colors.HexColor("#EEF7FF"),
        },
        {
            "label": "Actual reach",
            "value": _format_number(summary["metrics"]["actual"]),
            "helper": "Total beneficiaries reached across included updates.",
            "background": colors.HexColor("#FFF1F2"),
        },
        {
            "label": "Missionaries",
            "value": _format_number(summary["metrics"]["volunteers"]),
            "helper": "Combined missionary involvement recorded in reports.",
            "background": colors.HexColor("#EFFAF5"),
        },
        {
            "label": "Funds used",
            "value": _format_currency(summary["metrics"]["funds_used"]),
            "helper": "Reported spend captured across included updates.",
            "background": colors.HexColor("#FFF7E8"),
        },
    ]
    return _build_metric_grid(items, styles, columns=3)


def _build_consolidated_activity_chart(summary: dict, styles):
    fonts = _ensure_pdf_fonts()
    metrics = summary["metrics"]
    chart = Drawing(104 * mm, 48 * mm)

    baseline_y = 10 * mm
    chart_height = 26 * mm
    chart_width = 70 * mm
    origin_x = 10 * mm
    chart.add(
        Rect(origin_x - (1 * mm), baseline_y - (1 * mm), chart_width + (2 * mm), chart_height + (2 * mm), fillColor=colors.white, strokeColor=None)
    )
    chart.add(String(origin_x, baseline_y + chart_height + 9, "Combined totals", fontName=fonts["semibold"], fontSize=8.5, fillColor=PCM_SLATE))
    chart.add(Rect(origin_x, baseline_y, chart_width, 0.2 * mm, fillColor=PCM_BORDER, strokeColor=None))

    chart_series = [
        ("Expected", metrics["expected"], PCM_BLUE),
        ("Actual", metrics["actual"], PCM_RED),
        ("Missionaries", metrics["volunteers"], PCM_VIOLET),
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
                baseline_y + chart_height + 1.5 * mm,
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
                baseline_y - 4 * mm,
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
            [Paragraph(_safe_text(_build_report_insight(metrics)), styles["insightBody"])],
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
            [Paragraph("Reach and mobilization totals", styles["chartTitle"])],
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


def _build_actual_reach_by_reporting_period_chart(summary: dict, styles):
    return _build_actual_reach_bar_chart_card(
        title="Actual reach by reporting period",
        subtitle="Combined beneficiaries reached in each reporting period within the current scope.",
        rows=summary["reporting_period_reach_rows"],
        styles=styles,
        bar_color=PCM_SKY,
    )


def _build_actual_reach_by_conference_chart(summary: dict, styles):
    return _build_actual_reach_bar_chart_card(
        title="Actual reach by conference",
        subtitle="Combined beneficiaries reached by conference across the included campus reports.",
        rows=summary["conference_reach_rows"],
        styles=styles,
        bar_color=PCM_VIOLET,
    )


def _build_actual_reach_bar_chart_card(title: str, subtitle: str, rows: list[tuple[str, int]], styles, bar_color):
    fonts = _ensure_pdf_fonts()
    normalized_rows = rows or [("No data", 0)]
    label_width = 56 * mm
    bar_width = 82 * mm
    value_x = label_width + bar_width + (16 * mm)
    row_height = 8 * mm
    chart_height = max(26 * mm, (len(normalized_rows) * row_height) + (8 * mm))
    drawing = Drawing(CONTENT_WIDTH - (12 * mm), chart_height)
    maximum = max([value for _, value in normalized_rows] + [1])

    for index, (label, value) in enumerate(normalized_rows):
        y = chart_height - ((index + 1) * row_height)
        drawing.add(
            String(
                0,
                y + (2 * mm),
                _truncate_label(label, 26),
                fontName=fonts["regular"],
                fontSize=8,
                fillColor=PCM_SLATE,
            )
        )
        drawing.add(Rect(label_width, y + (1 * mm), bar_width, 3.8 * mm, fillColor=colors.HexColor("#E7EEF8"), strokeColor=None))
        fill_width = 0 if value <= 0 else bar_width * (value / maximum)
        drawing.add(Rect(label_width, y + (1 * mm), fill_width, 3.8 * mm, fillColor=bar_color, strokeColor=None))
        drawing.add(
            String(
                value_x,
                y + (2 * mm),
                _format_number(value),
                fontName=fonts["bold"],
                fontSize=8.5,
                fillColor=PCM_BLUE,
                textAnchor="end",
            )
        )

    card = Table(
        [
            [Paragraph(title, styles["chartTitle"])],
            [Paragraph(subtitle, styles["bodyMuted"])],
            [drawing],
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


def _build_conference_distribution_chart(summary: dict, styles):
    fonts = _ensure_pdf_fonts()
    rows = summary["conference_rows"] or [("Unassigned conference", summary["update_count"] or 1)]
    drawing = Drawing(72 * mm, 56 * mm)

    pie = Pie()
    pie.x = 3 * mm
    pie.y = 2 * mm
    pie.width = 48 * mm
    pie.height = 48 * mm
    pie.data = [value for _, value in rows]
    pie.labels = [_format_number(value) for _, value in rows]
    pie.simpleLabels = 0
    pie.sideLabels = 1
    pie.slices.strokeWidth = 0.8
    pie.slices.strokeColor = colors.white

    for index, (_, _) in enumerate(rows):
        pie.slices[index].fillColor = CONFERENCE_CHART_PALETTE[index % len(CONFERENCE_CHART_PALETTE)]
        pie.slices[index].popout = 3 if index == 0 else 0

    drawing.add(pie)

    legend_rows = []
    for index, (label, value) in enumerate(rows):
        swatch = Drawing(8 * mm, 4 * mm)
        swatch.add(Rect(0, 0, 7 * mm, 3 * mm, fillColor=CONFERENCE_CHART_PALETTE[index % len(CONFERENCE_CHART_PALETTE)], strokeColor=None))
        legend_rows.append(
            [
                swatch,
                Paragraph(escape(label), styles["body"]),
                Paragraph(_format_number(value), styles["valueRight"]),
            ]
        )

    legend_table = Table(legend_rows, colWidths=[10 * mm, 108 * mm, 20 * mm])
    legend_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.8, PCM_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    content = Table([[drawing, legend_table]], colWidths=[74 * mm, 100 * mm])
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
            [Paragraph("Distribution per conference", styles["chartTitle"])],
            [Paragraph("Share of included update submissions by conference.", styles["bodyMuted"])],
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


def _build_consolidated_context_table(summary: dict, styles):
    rows = [
        ("University / campus", summary["scope_label"]),
        ("Conferences covered", summary["conference_summary"]),
        ("Reporting period", summary["reporting_period_label"]),
        ("Schedule span", summary["schedule_label"]),
        ("Events covered", summary["event_summary"]),
        ("Linked ministry programs", summary["program_summary"]),
    ]
    return _build_key_value_table(
        rows,
        styles,
        label_style_key="tableLabel",
        value_style_key="tableValue",
        label_width=52 * mm,
        value_width=122 * mm,
        align_right=False,
    )


def _build_consolidated_summary_callout(summary: dict, styles):
    content_parts = [
        f"<b>Calculated insight:</b> {escape(_build_report_insight(summary['metrics']))}",
        (
            f"This report brings together {_format_number(summary['update_count'])} campus update"
            f"{'' if summary['update_count'] == 1 else 's'} across {_format_number(summary['conference_count'])} conference"
            f"{'' if summary['conference_count'] == 1 else 's'}."
        ),
    ]
    if summary["summary_highlights"]:
        content_parts.append(
            "<b>Combined highlights:</b><br/>" + "<br/>".join(f"- {escape(item)}" for item in summary["summary_highlights"])
        )
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


def _build_consolidated_narrative_sections(summary: dict, styles):
    sections = []
    section_definitions = [
        ("Narrative highlights", summary["section_entries"]["summary"], colors.HexColor("#EEF5FF")),
        ("Outcomes", summary["section_entries"]["outcomes"], colors.HexColor("#EFFAF5")),
        ("Challenges and problems", summary["section_entries"]["challenges"], colors.HexColor("#FFF4F4")),
        ("Next steps", summary["section_entries"]["next_steps"], colors.HexColor("#F4F0FF")),
    ]

    for heading, entries, background in section_definitions:
        if not entries:
            continue
        sections.extend(
            [
                Paragraph(heading, styles["section"]),
                Paragraph(
                    "Combined into a single list across all included university and campus reports.",
                    styles["bodyMuted"],
                ),
                Spacer(1, 6),
                _build_narrative_bullet_list_card(entries, styles, background),
                Spacer(1, 8),
            ]
        )

    if not sections:
        sections.append(Paragraph("No narrative fields were available across the selected campus reports.", styles["bodyMuted"]))
        sections.append(Spacer(1, 8))
    return sections


def _build_narrative_bullet_list_card(entries: list[dict], styles, background):
    bullet_style = styles["body"].clone("consolidatedNarrativeBullet")
    bullet_style.leftIndent = 12
    bullet_style.firstLineIndent = -10
    rows = [[Paragraph(f"&bull; {_safe_text(entry['text'])}", bullet_style)] for entry in entries]

    style_rules = [
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 1, PCM_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]
    if len(rows) > 1:
        style_rules.append(("LINEBELOW", (0, 0), (-1, -2), 0.6, PCM_BORDER))

    card = Table(rows, colWidths=[174 * mm])
    card.setStyle(TableStyle(style_rules))
    return card


def _build_key_value_table(
    rows: list[tuple[str, str]],
    styles,
    label_style_key: str,
    value_style_key: str,
    label_width: float,
    value_width: float,
    align_right: bool,
):
    table = Table(
        [
            [Paragraph(escape(label), styles[label_style_key]), Paragraph(_safe_text(value), styles[value_style_key])]
            for label, value in rows
        ],
        colWidths=[label_width, value_width],
    )
    style_rules = [
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
    if align_right:
        style_rules.append(("ALIGN", (1, 0), (1, -1), "RIGHT"))
    table.setStyle(TableStyle(style_rules))
    return table


def _decorate_consolidated_page(canvas, doc, summary: dict):
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
    canvas.drawString(header_x, page_height - 15.5 * mm, "Consolidated impact report")

    canvas.setStrokeColor(PCM_BORDER)
    canvas.line(doc.leftMargin, 14 * mm, page_width - doc.rightMargin, 14 * mm)
    canvas.setFillColor(PCM_SLATE)
    canvas.setFont(fonts["regular"], 8)
    canvas.drawString(
        doc.leftMargin,
        9.5 * mm,
        _truncate_canvas_text(
            canvas,
            _consolidated_report_filename_root(summary),
            page_width - doc.leftMargin - doc.rightMargin - (24 * mm),
            fonts["regular"],
            8,
        ),
    )
    canvas.drawRightString(page_width - doc.rightMargin, 9.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _decorate_consolidated_cover_page(canvas, doc, summary: dict):
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
    canvas.drawString(doc.leftMargin, 17 * mm, "Public Campus Ministries consolidated reporting pack")
    canvas.drawRightString(
        page_width - doc.rightMargin,
        17 * mm,
        _truncate_canvas_text(
            canvas,
            summary["reporting_period_label"],
            56 * mm,
            fonts["regular"],
            8.5,
        ),
    )
    canvas.restoreState()


def _display_event_name(update: ProgramUpdate) -> str:
    if update.event_detail:
        return f"{update.event_name}: {update.event_detail}"
    return update.event_name or update.title or "Impact update"


def _update_timestamp(update: ProgramUpdate):
    return update.updated_at or update.created_at


def _build_ranked_rows(counter: Counter[str], limit: int, other_label: str) -> list[tuple[str, int]]:
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    if len(ordered) <= limit:
        return ordered
    top_rows = ordered[: limit - 1]
    other_total = sum(value for _, value in ordered[limit - 1 :])
    return [*top_rows, (other_label, other_total)]


def _summarize_names(items: list[str], empty_value: str, limit: int = 4) -> str:
    normalized = [item for item in items if item]
    if not normalized:
        return empty_value
    if len(normalized) <= limit:
        return ", ".join(normalized)
    return f"{', '.join(normalized[:limit])} + {len(normalized) - limit} more"


def _condense_text(value: str | None, limit: int) -> str:
    normalized = " ".join((value or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


def _truncate_label(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1].rstrip()}…"


def _format_schedule_span(starts, ends) -> str:
    if not starts and not ends:
        return "Multiple schedules"
    start_date = min(starts) if starts else min(ends)
    end_date = max(ends) if ends else max(starts)
    if start_date == end_date:
        return start_date.strftime("%d %b %Y")
    return f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"


def _consolidated_report_filename_root(summary: dict) -> str:
    period_label = summary["reporting_period_label"] or "all_periods"
    return _slugify(f"{summary['scope_label']}_{period_label}_consolidated_impact_report")
