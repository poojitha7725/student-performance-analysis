"""
At-risk student identification and analysis module.
Identifies students who need attention based on marks and attendance,
provides risk reasons and improvement recommendations.
"""

import sqlite3
from config import DATABASE_PATH, PASS_MARK


def _conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def calculate_risk_category(avg_marks, attendance):
    """
    Determine risk category based on average marks and attendance.

    Returns:
        str: 'High Risk', 'Medium Risk', or 'Low Risk'
    """
    if avg_marks is None:
        avg_marks = 0
    if attendance is None:
        attendance = 0

    # High Risk: very low marks OR very low attendance, or both below threshold
    if avg_marks < 35 or attendance < 50:
        return 'High Risk'
    elif avg_marks < 50 or attendance < 65:
        return 'Medium Risk'
    else:
        return 'Low Risk'


def get_at_risk_students():
    """
    Analyse all students and return those categorised as High or Medium Risk.

    Returns:
        list of dicts with student info, risk category, and reasons.
    """
    conn = _conn()

    rows = conn.execute('''
        SELECT s.student_id, s.student_name, s.department, s.semester, s.gender,
               COALESCE(AVG(sub.total_marks), 0)             AS avg_marks,
               COALESCE(pr.attendance_percentage, 0)         AS attendance,
               COUNT(CASE WHEN sub.result = 'Fail' THEN 1 END) AS fail_count,
               COUNT(sub.id)                                  AS total_subjects
        FROM students s
        LEFT JOIN subjects sub ON s.student_id = sub.student_id
        LEFT JOIN performance_records pr ON s.student_id = pr.student_id
        GROUP BY s.student_id
    ''').fetchall()
    conn.close()

    at_risk = []
    for r in rows:
        row = dict(r)
        avg = round(row['avg_marks'], 2)
        att = round(row['attendance'], 2)
        category = calculate_risk_category(avg, att)

        if category in ('High Risk', 'Medium Risk'):
            row['average_marks'] = avg
            row['attendance_percentage'] = att
            row['risk_category'] = category
            row['risk_reasons'] = get_risk_reasons(row)
            row['recommendations'] = get_improvement_recommendations(row)
            at_risk.append(row)

    # Sort: High Risk first, then by average marks ascending
    at_risk.sort(key=lambda x: (0 if x['risk_category'] == 'High Risk' else 1,
                                 x['average_marks']))
    return at_risk


def get_risk_reasons(student):
    """
    Explain why a student is at risk.

    Args:
        student: dict with keys avg_marks / average_marks, attendance / attendance_percentage, fail_count

    Returns:
        list of reason strings
    """
    reasons = []
    avg = student.get('average_marks', student.get('avg_marks', 0))
    att = student.get('attendance_percentage', student.get('attendance', 0))
    fails = student.get('fail_count', 0)

    if avg < 35:
        reasons.append(f"Very low average marks ({avg:.1f}%) — well below pass mark of {PASS_MARK}%")
    elif avg < 50:
        reasons.append(f"Below-average marks ({avg:.1f}%) — needs improvement")

    if att < 50:
        reasons.append(f"Critically low attendance ({att:.1f}%) — below 50%")
    elif att < 65:
        reasons.append(f"Low attendance ({att:.1f}%) — below recommended 65%")

    if fails and fails > 0:
        reasons.append(f"Failed in {fails} subject(s)")

    if not reasons:
        reasons.append("Borderline performance — monitor closely")

    return reasons


def get_improvement_recommendations(student):
    """
    Provide specific improvement recommendations for an at-risk student.

    Args:
        student: dict with performance data

    Returns:
        list of recommendation strings
    """
    recommendations = []
    avg = student.get('average_marks', student.get('avg_marks', 0))
    att = student.get('attendance_percentage', student.get('attendance', 0))
    fails = student.get('fail_count', 0)

    # Attendance recommendations
    if att < 50:
        recommendations.append("URGENT: Attend all classes immediately. Meet with academic advisor about attendance policy.")
        recommendations.append("Set up daily reminders and study schedule to ensure regular class attendance.")
    elif att < 65:
        recommendations.append("Improve attendance to at least 75%. Attend all remaining classes this semester.")

    # Marks recommendations
    if avg < 35:
        recommendations.append("URGENT: Seek extra tutoring and attend remedial classes for failed subjects.")
        recommendations.append("Form a study group with peers and dedicate at least 3 hours daily to self-study.")
        recommendations.append("Meet with subject teachers for personalised guidance on weak areas.")
    elif avg < 50:
        recommendations.append("Focus on weaker subjects — allocate more revision time to subjects below pass mark.")
        recommendations.append("Practice previous year question papers and take mock tests regularly.")

    # Fail-specific
    if fails and fails > 0:
        recommendations.append(f"Prioritize the {fails} failed subject(s) for immediate revision.")
        recommendations.append("Consider enrolling in supplementary coaching for failed subjects.")

    # General
    recommendations.append("Maintain a consistent study timetable and track weekly progress.")
    if att >= 65 and avg >= 50:
        recommendations.append("Performance is acceptable but can be improved with focused effort.")

    return recommendations
