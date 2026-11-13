"""
Individual student performance analysis module.
Provides functions for single-student analysis, filtered queries,
and cross-student comparisons.
"""

import sqlite3
from config import DATABASE_PATH, PASS_MARK


def _conn():
    """Return a new DB connection with Row factory."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_student_performance(student_id):
    """
    Comprehensive performance report for a single student.

    Returns dict with student info, subjects, averages, strengths/weaknesses.
    """
    conn = _conn()

    student = conn.execute(
        "SELECT * FROM students WHERE student_id = ?", (student_id,)
    ).fetchone()
    if not student:
        conn.close()
        return {'error': f'Student {student_id} not found'}

    student_dict = dict(student)

    # Subject records
    subjects = conn.execute(
        "SELECT * FROM subjects WHERE student_id = ? ORDER BY subject",
        (student_id,)
    ).fetchall()
    subjects_list = [dict(s) for s in subjects]

    # Performance record
    perf = conn.execute(
        "SELECT * FROM performance_records WHERE student_id = ?",
        (student_id,)
    ).fetchone()

    conn.close()

    # Compute averages
    if subjects_list:
        avg_total = sum(s['total_marks'] for s in subjects_list) / len(subjects_list)
        max_subj = max(subjects_list, key=lambda s: s['total_marks'])
        min_subj = min(subjects_list, key=lambda s: s['total_marks'])
        pass_count = sum(1 for s in subjects_list if s['result'] == 'Pass')
        fail_count = len(subjects_list) - pass_count
    else:
        avg_total = 0
        max_subj = min_subj = None
        pass_count = fail_count = 0

    result = {
        'student': student_dict,
        'subjects': subjects_list,
        'total_subjects': len(subjects_list),
        'average_marks': round(avg_total, 2),
        'highest_scoring_subject': dict(max_subj) if max_subj else None,
        'lowest_scoring_subject': dict(min_subj) if min_subj else None,
        'pass_count': pass_count,
        'fail_count': fail_count,
        'pass_percentage': round(pass_count / len(subjects_list) * 100, 2) if subjects_list else 0,
        'attendance_percentage': dict(perf).get('attendance_percentage', 0) if perf else 0,
    }
    return result


def get_filtered_performance(department=None, semester=None, subject=None):
    """
    Filter student performance by department, semester, and/or subject.

    Returns list of student performance summaries matching the filter.
    """
    conn = _conn()

    sql = '''
        SELECT s.student_id, s.student_name, s.department, s.semester,
               sub.subject, sub.total_marks, sub.grade, sub.result,
               COALESCE(pr.attendance_percentage, 0) as attendance_percentage
        FROM students s
        JOIN subjects sub ON s.student_id = sub.student_id
        LEFT JOIN performance_records pr ON s.student_id = pr.student_id
        WHERE 1=1
    '''
    params = []

    if department:
        sql += " AND s.department = ?"
        params.append(department)
    if semester is not None:
        sql += " AND s.semester = ?"
        params.append(int(semester))
    if subject:
        sql += " AND sub.subject = ?"
        params.append(subject)

    sql += " ORDER BY s.student_id, sub.subject"
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return [dict(r) for r in rows]


def compare_student_performance(student_ids):
    """
    Compare performance of multiple students side by side.

    Args:
        student_ids: list of student_id strings

    Returns:
        dict with per-student summaries and comparison metrics.
    """
    if not student_ids:
        return {'error': 'No student IDs provided'}

    comparisons = []
    for sid in student_ids:
        perf = get_student_performance(sid)
        if 'error' not in perf:
            comparisons.append({
                'student_id': sid,
                'student_name': perf['student']['student_name'],
                'department': perf['student']['department'],
                'semester': perf['student']['semester'],
                'average_marks': perf['average_marks'],
                'total_subjects': perf['total_subjects'],
                'pass_count': perf['pass_count'],
                'fail_count': perf['fail_count'],
                'pass_percentage': perf['pass_percentage'],
                'attendance_percentage': perf['attendance_percentage'],
                'highest_scoring_subject': perf['highest_scoring_subject'],
                'lowest_scoring_subject': perf['lowest_scoring_subject'],
            })

    if not comparisons:
        return {'error': 'No valid students found'}

    # Rankings
    by_marks = sorted(comparisons, key=lambda c: c['average_marks'], reverse=True)
    for rank, c in enumerate(by_marks, 1):
        c['rank_by_marks'] = rank

    return {
        'students_compared': len(comparisons),
        'comparisons': comparisons,
        'best_performer': by_marks[0]['student_id'] if by_marks else None,
        'class_average': round(
            sum(c['average_marks'] for c in comparisons) / len(comparisons), 2
        ) if comparisons else 0,
    }
