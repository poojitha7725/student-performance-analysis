"""
Report generation module using ReportLab for PDF and csv module for CSV.
Generates professional reports for student performance data.
"""

import os
import csv
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, PageBreak
)

from config import REPORTS_FOLDER


def _ensure_reports_dir():
    os.makedirs(REPORTS_FOLDER, exist_ok=True)


def _timestamp():
    return datetime.now().strftime('%Y%m%d_%H%M%S')


# ── PDF generation ──────────────────────────────────────────────────────────

def generate_pdf_report(report_type, data):
    """
    Generate a professional PDF report.

    Args:
        report_type: one of 'complete_data', 'performance_analysis',
                     'top_performers', 'at_risk_students'
        data: list of dicts (rows of the report)

    Returns:
        str: absolute path of the generated PDF file
    """
    _ensure_reports_dir()
    filename = f"{report_type}_{_timestamp()}.pdf"
    filepath = os.path.join(REPORTS_FOLDER, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=landscape(A4),
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Title'],
        fontSize=20, spaceAfter=12, textColor=colors.HexColor('#1a237e')
    )
    subtitle_style = ParagraphStyle(
        'ReportSubtitle', parent=styles['Normal'],
        fontSize=11, spaceAfter=20, textColor=colors.grey
    )

    elements = []

    # ── Title section ──────────────────────────────────────────────────
    titles = {
        'complete_data': 'Complete Student Data Report',
        'performance_analysis': 'Performance Analysis Report',
        'top_performers': 'Top Performers Report',
        'at_risk_students': 'At-Risk Students Report',
    }
    title_text = titles.get(report_type, 'Student Performance Report')
    elements.append(Paragraph(title_text, title_style))
    elements.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}  |  "
        f"Total records: {len(data)}",
        subtitle_style
    ))
    elements.append(Spacer(1, 10))

    # ── Summary statistics ─────────────────────────────────────────────
    if data:
        summary = _build_summary(report_type, data)
        if summary:
            elements.append(Paragraph("Summary", styles['Heading2']))
            for line in summary:
                elements.append(Paragraph(f"• {line}", styles['Normal']))
            elements.append(Spacer(1, 15))

    # ── Data table ─────────────────────────────────────────────────────
    if data:
        table_data, col_widths = _prepare_table_data(report_type, data)
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
             [colors.white, colors.HexColor('#f5f5f5')]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No data available for this report.", styles['Normal']))

    doc.build(elements)
    return filepath


def _build_summary(report_type, data):
    """Build summary lines for the report."""
    lines = []
    if report_type == 'complete_data':
        student_ids = set()
        for r in data:
            sid = r.get('student_id', '')
            if sid:
                student_ids.add(sid)
        lines.append(f"Total unique students: {len(student_ids)}")
        lines.append(f"Total records: {len(data)}")
    elif report_type == 'top_performers':
        if data:
            lines.append(f"Top {len(data)} performers listed below")
            lines.append(f"Highest average: {data[0].get('average_marks', 'N/A')}")
    elif report_type == 'at_risk_students':
        high = sum(1 for r in data if r.get('risk_category') == 'High Risk')
        medium = sum(1 for r in data if r.get('risk_category') == 'Medium Risk')
        lines.append(f"High Risk students: {high}")
        lines.append(f"Medium Risk students: {medium}")
    elif report_type == 'performance_analysis':
        if data:
            marks = [r.get('average_marks', 0) or 0 for r in data]
            if marks:
                lines.append(f"Average marks: {sum(marks)/len(marks):.2f}")
                lines.append(f"Highest: {max(marks):.2f}")
                lines.append(f"Lowest: {min(marks):.2f}")
    return lines


def _prepare_table_data(report_type, data):
    """Convert data dicts to table rows with headers; return (rows, col_widths)."""
    if report_type == 'complete_data':
        headers = ['Student ID', 'Name', 'Dept', 'Sem', 'Subject',
                    'Internal', 'External', 'Total', 'Grade', 'Result']
        keys = ['student_id', 'student_name', 'department', 'semester',
                'subject', 'internal_marks', 'external_marks',
                'total_marks', 'grade', 'result']
        widths = [70, 100, 80, 35, 100, 50, 50, 45, 40, 40]
    elif report_type == 'top_performers':
        headers = ['Rank', 'Student ID', 'Name', 'Dept', 'Sem',
                    'Avg Marks', 'Attendance', 'Grade']
        keys = ['rank', 'student_id', 'student_name', 'department',
                'semester', 'average_marks', 'attendance_percentage',
                'overall_grade']
        widths = [35, 70, 110, 90, 35, 60, 70, 45]
        # Add rank if missing
        for i, row in enumerate(data):
            row.setdefault('rank', i + 1)
    elif report_type == 'at_risk_students':
        headers = ['Student ID', 'Name', 'Dept', 'Sem',
                    'Avg Marks', 'Attendance', 'Risk', 'Fails']
        keys = ['student_id', 'student_name', 'department', 'semester',
                'average_marks', 'attendance_percentage', 'risk_category',
                'fail_count']
        widths = [70, 100, 80, 35, 60, 70, 70, 40]
    else:  # performance_analysis
        headers = ['Student ID', 'Name', 'Dept', 'Sem',
                    'Avg Marks', 'Attendance', 'Grade', 'Pass%']
        keys = ['student_id', 'student_name', 'department', 'semester',
                'average_marks', 'attendance_percentage', 'overall_grade',
                'pass_percentage']
        widths = [70, 110, 80, 35, 60, 70, 45, 50]

    table_data = [headers]
    for row in data:
        table_row = []
        for k in keys:
            val = row.get(k, '')
            if isinstance(val, float):
                val = f"{val:.1f}"
            table_row.append(str(val) if val is not None else '')
        table_data.append(table_row)

    return table_data, widths


# ── CSV generation ──────────────────────────────────────────────────────────

def generate_csv_report(report_type, data):
    """
    Generate a CSV report file.

    Args:
        report_type: string identifier for the report
        data: list of dicts

    Returns:
        str: absolute path of the generated CSV file
    """
    _ensure_reports_dir()
    filename = f"{report_type}_{_timestamp()}.csv"
    filepath = os.path.join(REPORTS_FOLDER, filename)

    if not data:
        # Write empty file with message
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            f.write("No data available for this report.\n")
        return filepath

    fieldnames = list(data[0].keys())

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in data:
            # Flatten lists/dicts to strings for CSV
            clean_row = {}
            for k, v in row.items():
                if isinstance(v, (list, dict)):
                    clean_row[k] = str(v)
                else:
                    clean_row[k] = v
            writer.writerow(clean_row)

    return filepath
