"""
Recommendation engine module.
Generates personalised recommendations for students based on their
marks, attendance, and subject-wise performance.
"""

import sqlite3
from config import DATABASE_PATH, PASS_MARK


def _conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def generate_recommendations(student_id):
    """
    Generate comprehensive recommendations for a student based on all
    available performance data.

    Returns:
        dict with student info and categorised recommendations
    """
    conn = _conn()

    # Fetch student
    student = conn.execute(
        "SELECT * FROM students WHERE student_id = ?", (student_id,)
    ).fetchone()
    if not student:
        conn.close()
        return {'error': f'Student {student_id} not found'}
    student = dict(student)

    # Fetch subjects
    subjects = conn.execute(
        "SELECT * FROM subjects WHERE student_id = ? ORDER BY subject",
        (student_id,)
    ).fetchall()
    subjects = [dict(s) for s in subjects]

    # Fetch performance record
    perf = conn.execute(
        "SELECT * FROM performance_records WHERE student_id = ?",
        (student_id,)
    ).fetchone()
    attendance = dict(perf).get('attendance_percentage', 0) if perf else 0

    conn.close()

    # Build recommendations
    recs = {
        'student_id': student_id,
        'student_name': student['student_name'],
        'department': student['department'],
        'semester': student['semester'],
        'subject_recommendations': [],
        'attendance_recommendations': get_attendance_recommendations(attendance),
        'overall_recommendations': [],
    }

    # Per-subject recommendations
    for sub in subjects:
        sub_rec = get_subject_recommendations(sub['subject'], sub['total_marks'])
        recs['subject_recommendations'].append({
            'subject': sub['subject'],
            'marks': sub['total_marks'],
            'grade': sub['grade'],
            'result': sub['result'],
            'recommendations': sub_rec,
        })

    # Overall
    student_data = {
        'subjects': subjects,
        'attendance': attendance,
        'student': student,
    }
    recs['overall_recommendations'] = get_overall_recommendations(student_data)

    return recs


def get_subject_recommendations(subject, marks):
    """
    Provide recommendations for a specific subject based on marks scored.

    Args:
        subject: subject name string
        marks: total marks obtained (0-100 scale)

    Returns:
        list of recommendation strings
    """
    marks = float(marks) if marks else 0
    recs = []

    if marks >= 90:
        recs.append(f"Excellent performance in {subject}! Consider mentoring peers.")
        recs.append(f"Explore advanced topics and competitive exams related to {subject}.")
    elif marks >= 80:
        recs.append(f"Very good performance in {subject}. Aim for 90+ with focused revision.")
    elif marks >= 70:
        recs.append(f"Good performance in {subject}. Identify specific weak chapters and revise them.")
    elif marks >= 60:
        recs.append(f"Above average in {subject}. Increase practice with problems and past papers.")
    elif marks >= 50:
        recs.append(f"Average performance in {subject}. Needs more dedicated study time.")
        recs.append(f"Join study groups or seek tutoring for {subject}.")
    elif marks >= 40:
        recs.append(f"Barely passing {subject}. Significantly increase study hours.")
        recs.append(f"Attend all {subject} classes and complete every assignment.")
        recs.append(f"Consider supplementary coaching for {subject}.")
    else:
        recs.append(f"FAILED {subject}. Immediate remedial action required.")
        recs.append(f"Meet {subject} instructor for a recovery plan.")
        recs.append(f"Dedicate at least 2 hours daily exclusively to {subject} revision.")
        recs.append(f"Practice fundamental concepts before attempting advanced problems.")

    return recs


def get_attendance_recommendations(attendance):
    """
    Provide recommendations based on attendance percentage.

    Args:
        attendance: attendance percentage (0-100)

    Returns:
        list of recommendation strings
    """
    attendance = float(attendance) if attendance else 0
    recs = []

    if attendance >= 90:
        recs.append("Outstanding attendance! Keep it up.")
    elif attendance >= 75:
        recs.append("Good attendance. Try to reach 90%+ for the best learning outcomes.")
    elif attendance >= 65:
        recs.append("Attendance is below optimal. Aim for at least 75% to stay on track.")
        recs.append("Missing classes leads to gaps in understanding — attend regularly.")
    elif attendance >= 50:
        recs.append("WARNING: Low attendance. Many universities require 75% minimum.")
        recs.append("Prioritize attending every remaining class this semester.")
        recs.append("If personal issues are affecting attendance, consult a counsellor.")
    else:
        recs.append("CRITICAL: Attendance is dangerously low and may result in detention.")
        recs.append("Meet with the Head of Department immediately to discuss your situation.")
        recs.append("Attend every single class from now on — no exceptions.")
        recs.append("Consider if external factors (health, personal) need professional support.")

    return recs


def get_overall_recommendations(student_data):
    """
    Generate holistic recommendations based on combined student performance.

    Args:
        student_data: dict with keys 'subjects' (list), 'attendance' (float),
                      'student' (dict with name, department, semester)

    Returns:
        list of recommendation strings
    """
    subjects = student_data.get('subjects', [])
    attendance = float(student_data.get('attendance', 0))
    student = student_data.get('student', {})

    recs = []

    if not subjects:
        recs.append("No subject data available. Ensure records are uploaded.")
        return recs

    avg_marks = sum(s['total_marks'] for s in subjects) / len(subjects)
    fail_subjects = [s for s in subjects if s['result'] == 'Fail']
    pass_rate = ((len(subjects) - len(fail_subjects)) / len(subjects)) * 100

    # Overall performance tier
    if avg_marks >= 80 and attendance >= 80:
        recs.append("Excellent overall performance! Maintain this standard.")
        recs.append("Consider research projects, internships, or academic competitions.")
    elif avg_marks >= 60 and attendance >= 70:
        recs.append("Good performance overall. With focused effort, you can reach the top tier.")
        recs.append("Identify 1-2 weaker subjects and dedicate extra time to them.")
    elif avg_marks >= 40:
        recs.append("Performance needs improvement across the board.")
        recs.append("Create a structured study plan with daily goals.")
        recs.append("Seek help from professors during office hours.")
    else:
        recs.append("CRITICAL: Overall performance is below passing level.")
        recs.append("Immediate academic intervention is needed.")
        recs.append("Meet with your academic advisor to explore support options.")

    # Failed subjects
    if fail_subjects:
        failed_names = [s['subject'] for s in fail_subjects]
        recs.append(
            f"Failed {len(fail_subjects)} subject(s): {', '.join(failed_names)}. "
            f"Focus remedial effort on these immediately."
        )

    # Attendance impact
    if attendance < 65:
        recs.append(
            "Low attendance is likely contributing to poor marks. "
            "Improving attendance is the single most impactful change you can make."
        )

    # Semester-specific
    semester = student.get('semester', 0)
    if semester and int(semester) >= 7:
        recs.append(
            "You are in a senior semester — focus on maintaining GPA for placements "
            "and clear any backlogs urgently."
        )

    return recs
