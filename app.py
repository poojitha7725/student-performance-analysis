"""
Student Performance Analysis - Flask Application Entry Point
"""

import os
import io
import csv
import json
import sqlite3
import pandas as pd
from datetime import datetime
from flask import (
    Flask, render_template, request, jsonify, send_file,
    redirect, url_for, flash, abort, send_from_directory
)

import config
import database
from modules.data_cleaning import validate_csv_file, clean_data, get_file_info
from modules.performance_analysis import (
    get_student_performance, get_filtered_performance, compare_student_performance
)
from modules.risk_analysis import get_at_risk_students, calculate_risk_category
from modules.recommendations import generate_recommendations
from modules.report_generator import generate_pdf_report, generate_csv_report

# Initialize Flask app
app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# Ensure essential directories exist
os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(config.REPORTS_FOLDER, exist_ok=True)


# ── Database Sync & Seeding ──────────────────────────────────────────────────

def sync_performance_records():
    """Recalculate overall averages, grades, and risk levels for all students."""
    conn = database.get_db_connection()
    students = conn.execute("SELECT student_id FROM students").fetchall()

    for s in students:
        sid = s['student_id']
        sub_stats = conn.execute(
            '''SELECT AVG(total_marks) as avg_marks,
                      COUNT(id) as total_sub,
                      COUNT(CASE WHEN result = 'Fail' THEN 1 END) as fail_count
               FROM subjects WHERE student_id = ?''', (sid,)
        ).fetchone()

        avg_marks = round(sub_stats['avg_marks'], 2) if sub_stats and sub_stats['avg_marks'] is not None else 0.0
        overall_grade = database._calculate_grade(avg_marks)

        perf = conn.execute(
            "SELECT attendance_percentage FROM performance_records WHERE student_id = ?", (sid,)
        ).fetchone()
        att = perf['attendance_percentage'] if perf and perf['attendance_percentage'] is not None else 75.0
        risk = calculate_risk_category(avg_marks, att)

        if perf:
            conn.execute(
                '''UPDATE performance_records
                   SET average_marks = ?, overall_grade = ?, risk_category = ?
                   WHERE student_id = ?''',
                (avg_marks, overall_grade, risk, sid)
            )
        else:
            conn.execute(
                '''INSERT INTO performance_records
                   (student_id, attendance_percentage, average_marks, overall_grade, risk_category, recommendations)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (sid, att, avg_marks, overall_grade, risk, '')
            )
    conn.commit()
    conn.close()


def seed_sample_data_if_empty():
    """Populate database with sample student data if empty."""
    conn = database.get_db_connection()
    count = conn.execute("SELECT COUNT(*) as cnt FROM students").fetchone()['cnt']
    conn.close()

    if count > 0:
        return

    # Sample data generator
    sample_students = [
        ('STU1001', 'Aarav Sharma', 20, 'Male', 'Computer Science', 4, 88.5, [
            ('Data Structures', 27, 65), ('Database Systems', 26, 68),
            ('Computer Networks', 28, 67), ('Operating Systems', 29, 66)
        ]),
        ('STU1002', 'Diya Patel', 19, 'Female', 'Computer Science', 4, 94.0, [
            ('Data Structures', 30, 68), ('Database Systems', 29, 69),
            ('Computer Networks', 30, 67), ('Operating Systems', 28, 68)
        ]),
        ('STU1003', 'Rohan Verma', 21, 'Male', 'Electronics', 6, 72.0, [
            ('Digital Electronics', 22, 50), ('Circuit Theory', 20, 48),
            ('Mathematics', 24, 55), ('Microprocessors', 21, 52)
        ]),
        ('STU1004', 'Ananya Iyer', 20, 'Female', 'Electronics', 6, 64.0, [
            ('Digital Electronics', 15, 30), ('Circuit Theory', 12, 28),
            ('Mathematics', 18, 35), ('Microprocessors', 14, 32)
        ]),
        ('STU1005', 'Vikram Singh', 22, 'Male', 'Mechanical', 8, 48.0, [
            ('Thermodynamics', 10, 20), ('Machine Design', 12, 22),
            ('Fluid Mechanics', 11, 25), ('Heat Transfer', 14, 21)
        ]),
        ('STU1006', 'Sneha Kulkarni', 21, 'Female', 'Mechanical', 8, 86.0, [
            ('Thermodynamics', 26, 62), ('Machine Design', 25, 60),
            ('Fluid Mechanics', 27, 63), ('Heat Transfer', 28, 64)
        ]),
        ('STU1007', 'Rahul Nair', 19, 'Male', 'Civil', 2, 78.5, [
            ('Structural Analysis', 23, 56), ('Physics', 24, 58),
            ('Chemistry', 22, 54), ('Mathematics', 25, 60)
        ]),
        ('STU1008', 'Pooja Reddy', 20, 'Female', 'Civil', 2, 82.0, [
            ('Structural Analysis', 25, 60), ('Physics', 26, 62),
            ('Chemistry', 24, 59), ('Mathematics', 27, 63)
        ]),
        ('STU1009', 'Karthik Rao', 20, 'Male', 'Electrical', 4, 58.0, [
            ('Power Systems', 14, 32), ('Circuit Theory', 16, 36),
            ('Electrical Machines', 15, 34), ('Mathematics', 18, 40)
        ]),
        ('STU1010', 'Meera Joshi', 20, 'Female', 'Electrical', 4, 91.5, [
            ('Power Systems', 28, 67), ('Circuit Theory', 29, 68),
            ('Electrical Machines', 27, 65), ('Mathematics', 30, 69)
        ]),
        ('STU1011', 'Siddharth Roy', 21, 'Male', 'Computer Science', 6, 42.0, [
            ('Software Engineering', 11, 24), ('Computer Networks', 12, 22),
            ('Database Systems', 13, 26), ('Operating Systems', 10, 20)
        ]),
        ('STU1012', 'Tanvi Mehta', 19, 'Female', 'Computer Science', 2, 89.0, [
            ('Mathematics', 28, 65), ('Physics', 27, 63),
            ('Chemistry', 29, 67), ('Programming in C', 30, 68)
        ]),
        ('STU1013', 'Arjun Gupta', 20, 'Male', 'Electronics', 4, 76.0, [
            ('Digital Electronics', 24, 56), ('Circuit Theory', 22, 52),
            ('Mathematics', 25, 59), ('Signals & Systems', 23, 54)
        ]),
        ('STU1014', 'Kavya Pillai', 21, 'Female', 'Mechanical', 6, 81.0, [
            ('Thermodynamics', 25, 58), ('Machine Design', 24, 57),
            ('Manufacturing Processes', 26, 61), ('Dynamics of Machinery', 25, 59)
        ]),
        ('STU1015', 'Nikhil Deshmukh', 22, 'Male', 'Civil', 8, 38.0, [
            ('Structural Analysis', 10, 18), ('Surveying', 12, 20),
            ('Geotechnical Eng', 11, 19), ('Transportation Eng', 9, 17)
        ])
    ]

    conn = database.get_db_connection()
    for sid, name, age, gender, dept, sem, att, subjects in sample_students:
        conn.execute(
            '''INSERT INTO students (student_id, student_name, age, gender, department, semester)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (sid, name, age, gender, dept, sem)
        )
        for sub_name, internal, external in subjects:
            total = internal + external
            grade = database._calculate_grade(total)
            result = database._calculate_result(total)
            conn.execute(
                '''INSERT INTO subjects
                   (student_id, subject, internal_marks, external_marks, total_marks, grade, result)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (sid, sub_name, internal, external, total, grade, result)
            )

        conn.execute(
            '''INSERT INTO performance_records
               (student_id, attendance_percentage, average_marks, overall_grade, risk_category, recommendations)
               VALUES (?, ?, 0, '', '', '')''',
            (sid, att)
        )
    conn.commit()
    conn.close()
    sync_performance_records()


# ── Page Routes ─────────────────────────────────────────────────────────────

@app.route('/')
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@app.route('/students')
def students():
    department = request.args.get('department', '')
    semester = request.args.get('semester', '')
    search = request.args.get('search', '')

    sem_val = int(semester) if semester.isdigit() else None
    student_list = database.search_students(query=search, department=department or None, semester=sem_val)

    # Attach performance summaries
    conn = database.get_db_connection()
    enriched = []
    for s in student_list:
        sid = s['student_id']
        stats = conn.execute(
            '''SELECT AVG(total_marks) as avg_marks,
                      COUNT(id) as total_subjects,
                      COUNT(CASE WHEN result = 'Pass' THEN 1 END) as pass_count,
                      COUNT(CASE WHEN result = 'Fail' THEN 1 END) as fail_count
               FROM subjects WHERE student_id = ?''', (sid,)
        ).fetchone()

        perf = conn.execute(
            "SELECT attendance_percentage, overall_grade, risk_category FROM performance_records WHERE student_id = ?",
            (sid,)
        ).fetchone()

        avg_m = round(stats['avg_marks'], 1) if stats and stats['avg_marks'] is not None else 0.0
        enriched.append({
            **s,
            'avg_marks': avg_m,
            'total_subjects': stats['total_subjects'] if stats else 0,
            'pass_count': stats['pass_count'] if stats else 0,
            'fail_count': stats['fail_count'] if stats else 0,
            'attendance': round(perf['attendance_percentage'], 1) if perf and perf['attendance_percentage'] else 0.0,
            'overall_grade': perf['overall_grade'] if perf else database._calculate_grade(avg_m),
            'risk_category': perf['risk_category'] if perf else 'Low Risk'
        })
    conn.close()

    return render_template(
        'students.html',
        students=enriched,
        departments=config.DEPARTMENTS,
        semesters=config.SEMESTERS,
        selected_dept=department,
        selected_sem=semester,
        search_query=search
    )


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    upload_result = None
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected.', 'danger')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)

        if not file.filename.lower().endswith('.csv'):
            flash('Only CSV (.csv) files are supported.', 'danger')
            return redirect(request.url)

        filepath = os.path.join(config.UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        # Validate CSV
        validation = validate_csv_file(filepath)
        if not validation['valid']:
            flash(f"Validation failed: {', '.join(validation['errors'])}", 'danger')
            return render_template('upload.html', validation=validation)

        # Clean CSV
        try:
            raw_df = pd.read_csv(filepath)
            cleaned_df, cleaning_report = clean_data(raw_df)
            cleaned_filepath = os.path.join(config.UPLOAD_FOLDER, 'cleaned_' + file.filename)
            cleaned_df.to_csv(cleaned_filepath, index=False)

            # Insert into database
            insert_result = database.bulk_insert_from_csv(cleaned_filepath)
            sync_performance_records()

            upload_result = {
                'filename': file.filename,
                'rows_processed': len(cleaned_df),
                'students_inserted': insert_result['students_inserted'],
                'subjects_inserted': insert_result['subjects_inserted'],
                'warnings': validation.get('warnings', []),
                'cleaning_changes': cleaning_report.get('changes', []),
                'errors': insert_result.get('errors', [])
            }
            flash('Dataset uploaded and processed successfully!', 'success')
        except Exception as e:
            flash(f"Error processing CSV: {str(e)}", 'danger')

    return render_template('upload.html', result=upload_result)


@app.route('/performance')
def performance():
    department = request.args.get('department', '')
    semester = request.args.get('semester', '')
    subject = request.args.get('subject', '')

    sem_val = int(semester) if semester.isdigit() else None
    records = get_filtered_performance(
        department=department or None,
        semester=sem_val,
        subject=subject or None
    )

    all_students = database.get_all_students()

    return render_template(
        'performance.html',
        records=records,
        students=all_students,
        departments=config.DEPARTMENTS,
        semesters=config.SEMESTERS,
        subjects=config.SUBJECTS,
        selected_dept=department,
        selected_sem=semester,
        selected_subj=subject
    )


@app.route('/top-performers')
def top_performers():
    conn = database.get_db_connection()

    # Overall top performers
    overall = conn.execute('''
        SELECT s.student_id, s.student_name, s.department, s.semester, s.gender,
               ROUND(AVG(sub.total_marks), 2) as average_marks,
               ROUND(pr.attendance_percentage, 1) as attendance_percentage,
               pr.overall_grade
        FROM students s
        JOIN subjects sub ON s.student_id = sub.student_id
        LEFT JOIN performance_records pr ON s.student_id = pr.student_id
        GROUP BY s.student_id
        ORDER BY average_marks DESC
        LIMIT 10
    ''').fetchall()

    # Department toppers
    dept_toppers = {}
    for dept in config.DEPARTMENTS:
        row = conn.execute('''
            SELECT s.student_id, s.student_name, s.department, s.semester,
                   ROUND(AVG(sub.total_marks), 2) as average_marks,
                   ROUND(pr.attendance_percentage, 1) as attendance_percentage,
                   pr.overall_grade
            FROM students s
            JOIN subjects sub ON s.student_id = sub.student_id
            LEFT JOIN performance_records pr ON s.student_id = pr.student_id
            WHERE s.department = ?
            GROUP BY s.student_id
            ORDER BY average_marks DESC
            LIMIT 1
        ''', (dept,)).fetchone()
        if row:
            dept_toppers[dept] = dict(row)

    conn.close()

    return render_template(
        'top_performers.html',
        overall=[dict(r) for r in overall],
        dept_toppers=dept_toppers
    )


@app.route('/at-risk')
def at_risk():
    at_risk_list = get_at_risk_students()
    high_risk_count = sum(1 for s in at_risk_list if s.get('risk_category') == 'High Risk')
    medium_risk_count = sum(1 for s in at_risk_list if s.get('risk_category') == 'Medium Risk')

    return render_template(
        'at_risk.html',
        students=at_risk_list,
        high_risk_count=high_risk_count,
        medium_risk_count=medium_risk_count,
        total_risk=len(at_risk_list)
    )


@app.route('/attendance')
def attendance():
    conn = database.get_db_connection()
    rows = conn.execute('''
        SELECT s.student_id, s.student_name, s.department, s.semester,
               COALESCE(pr.attendance_percentage, 0) as attendance,
               COALESCE(AVG(sub.total_marks), 0) as avg_marks
        FROM students s
        LEFT JOIN performance_records pr ON s.student_id = pr.student_id
        LEFT JOIN subjects sub ON s.student_id = sub.student_id
        GROUP BY s.student_id
        ORDER BY attendance ASC
    ''').fetchall()
    conn.close()

    students_att = [dict(r) for r in rows]

    high_att = [s for s in students_att if s['attendance'] >= 75]
    medium_att = [s for s in students_att if 65 <= s['attendance'] < 75]
    low_att = [s for s in students_att if s['attendance'] < 65]

    return render_template(
        'attendance.html',
        students=students_att,
        high_count=len(high_att),
        medium_count=len(medium_att),
        low_count=len(low_att),
        low_students=low_att
    )


@app.route('/reports')
def reports():
    # List generated reports
    generated_files = []
    if os.path.exists(config.REPORTS_FOLDER):
        for f in os.listdir(config.REPORTS_FOLDER):
            if f.endswith('.pdf') or f.endswith('.csv'):
                path = os.path.join(config.REPORTS_FOLDER, f)
                generated_files.append({
                    'name': f,
                    'size': f"{os.path.getsize(path) / 1024:.1f} KB",
                    'type': 'PDF' if f.endswith('.pdf') else 'CSV',
                    'created': datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S')
                })
        generated_files.sort(key=lambda x: x['created'], reverse=True)

    return render_template('reports.html', files=generated_files)


@app.route('/recommendations')
def recommendations():
    student_id = request.args.get('student_id', '')
    rec_data = None
    if student_id:
        rec_data = generate_recommendations(student_id)

    students = database.get_all_students()
    return render_template('recommendations.html', students=students, selected_id=student_id, rec=rec_data)


@app.route('/about')
def about():
    return render_template('about.html')


# ── API Endpoints ───────────────────────────────────────────────────────────

@app.route('/api/dashboard/stats')
def api_dashboard_stats():
    conn = database.get_db_connection()

    total_stu = conn.execute("SELECT COUNT(*) as c FROM students").fetchone()['c']
    avg_m = conn.execute("SELECT AVG(total_marks) as avg FROM subjects").fetchone()['avg']
    avg_att = conn.execute("SELECT AVG(attendance_percentage) as avg FROM performance_records").fetchone()['avg']

    pass_cnt = conn.execute("SELECT COUNT(*) as c FROM subjects WHERE result = 'Pass'").fetchone()['c']
    total_sub = conn.execute("SELECT COUNT(*) as c FROM subjects").fetchone()['c']

    top_row = conn.execute('''
        SELECT s.student_name, AVG(sub.total_marks) as avg_m
        FROM students s
        JOIN subjects sub ON s.student_id = sub.student_id
        GROUP BY s.student_id
        ORDER BY avg_m DESC
        LIMIT 1
    ''').fetchone()

    conn.close()

    pass_pct = round((pass_cnt / total_sub) * 100, 1) if total_sub > 0 else 0
    fail_pct = round(100 - pass_pct, 1) if total_sub > 0 else 0

    top_performer = f"{top_row['student_name']} ({top_row['avg_m']:.1f}%)" if top_row and top_row['student_name'] else "N/A"

    return jsonify({
        'success': True,
        'data': {
            'total_students': total_stu,
            'average_marks': round(avg_m, 1) if avg_m else 0,
            'pass_percentage': pass_pct,
            'fail_percentage': fail_pct,
            'average_attendance': round(avg_att, 1) if avg_att else 0,
            'top_performer': top_performer
        }
    })


@app.route('/api/dashboard/charts')
def api_dashboard_charts():
    conn = database.get_db_connection()

    # Subject-wise
    sub_rows = conn.execute('''
        SELECT subject, ROUND(AVG(total_marks), 1) as avg
        FROM subjects
        GROUP BY subject
        ORDER BY avg DESC
    ''').fetchall()
    subject_wise = {r['subject']: r['avg'] for r in sub_rows}

    # Department-wise
    dept_rows = conn.execute('''
        SELECT s.department, ROUND(AVG(sub.total_marks), 1) as avg
        FROM students s
        JOIN subjects sub ON s.student_id = sub.student_id
        GROUP BY s.department
        ORDER BY avg DESC
    ''').fetchall()
    department_wise = {r['department']: r['avg'] for r in dept_rows}

    # Gender-wise
    gender_rows = conn.execute('''
        SELECT s.gender, ROUND(AVG(sub.total_marks), 1) as avg
        FROM students s
        JOIN subjects sub ON s.student_id = sub.student_id
        WHERE s.gender IS NOT NULL AND s.gender != ''
        GROUP BY s.gender
    ''').fetchall()
    gender_wise = {r['gender']: r['avg'] for r in gender_rows}

    # Semester-wise
    sem_rows = conn.execute('''
        SELECT s.semester, ROUND(AVG(sub.total_marks), 1) as avg
        FROM students s
        JOIN subjects sub ON s.student_id = sub.student_id
        GROUP BY s.semester
        ORDER BY s.semester ASC
    ''').fetchall()
    semester_wise = {str(r['semester']): r['avg'] for r in sem_rows}

    # Pass / Fail
    pass_cnt = conn.execute("SELECT COUNT(*) as c FROM subjects WHERE result = 'Pass'").fetchone()['c']
    fail_cnt = conn.execute("SELECT COUNT(*) as c FROM subjects WHERE result = 'Fail'").fetchone()['c']

    # Scatter: Attendance vs Marks
    scatter_rows = conn.execute('''
        SELECT s.student_name,
               ROUND(pr.attendance_percentage, 1) as attendance,
               ROUND(AVG(sub.total_marks), 1) as marks
        FROM students s
        JOIN subjects sub ON s.student_id = sub.student_id
        LEFT JOIN performance_records pr ON s.student_id = pr.student_id
        GROUP BY s.student_id
    ''').fetchall()
    attendance_vs_marks = [
        {'student_name': r['student_name'], 'attendance': r['attendance'] or 0, 'marks': r['marks'] or 0}
        for r in scatter_rows
    ]

    # Grade distribution
    grade_rows = conn.execute('''
        SELECT grade, COUNT(*) as cnt
        FROM subjects
        GROUP BY grade
    ''').fetchall()
    grade_dist = {r['grade']: r['cnt'] for r in grade_rows}

    conn.close()

    return jsonify({
        'success': True,
        'data': {
            'subject_wise': subject_wise,
            'department_wise': department_wise,
            'gender_wise': gender_wise,
            'semester_wise': semester_wise,
            'pass_fail': {'pass': pass_cnt, 'fail': fail_cnt},
            'attendance_vs_marks': attendance_vs_marks,
            'grade_distribution': grade_dist
        }
    })


@app.route('/api/students', methods=['GET', 'POST'])
def api_students():
    if request.method == 'GET':
        query = request.args.get('query', '')
        department = request.args.get('department', None)
        semester = request.args.get('semester', None)
        sem_val = int(semester) if semester and semester.isdigit() else None
        students = database.search_students(query=query, department=department, semester=sem_val)
        return jsonify({'success': True, 'data': students})

    elif request.method == 'POST':
        data = request.get_json() or request.form
        student_id = data.get('student_id', '').strip()
        student_name = data.get('student_name', '').strip()
        age = int(data.get('age', 18))
        gender = data.get('gender', 'Male')
        department = data.get('department', 'Computer Science')
        semester = int(data.get('semester', 1))

        if not student_id or not student_name:
            return jsonify({'success': False, 'error': 'Student ID and Name are required.'}), 400

        try:
            database.insert_student(student_id, student_name, age, gender, department, semester)
            # Default performance record
            conn = database.get_db_connection()
            conn.execute(
                '''INSERT OR IGNORE INTO performance_records
                   (student_id, attendance_percentage, average_marks, overall_grade, risk_category, recommendations)
                   VALUES (?, 75.0, 0, 'F', 'Low Risk', '')''', (student_id,)
            )
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'Student added successfully!'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/students/<student_id>', methods=['GET', 'PUT', 'DELETE'])
def api_student_detail(student_id):
    if request.method == 'GET':
        perf = get_student_performance(student_id)
        if 'error' in perf:
            return jsonify({'success': False, 'error': perf['error']}), 404
        return jsonify({'success': True, 'data': perf})

    elif request.method == 'PUT':
        data = request.get_json() or {}
        success = database.update_student(student_id, **data)
        if success:
            sync_performance_records()
            return jsonify({'success': True, 'message': 'Student updated successfully.'})
        return jsonify({'success': False, 'error': 'Update failed.'}), 400

    elif request.method == 'DELETE':
        success = database.delete_student(student_id)
        return jsonify({'success': success, 'message': 'Student deleted successfully.'})


@app.route('/api/students/<student_id>/subjects', methods=['GET', 'POST'])
def api_student_subjects(student_id):
    if request.method == 'GET':
        subjects = database.get_student_subjects(student_id)
        return jsonify({'success': True, 'data': subjects})

    elif request.method == 'POST':
        data = request.get_json() or request.form
        subject = data.get('subject')
        internal = float(data.get('internal_marks', 0))
        external = float(data.get('external_marks', 0))

        if not subject:
            return jsonify({'success': False, 'error': 'Subject is required.'}), 400

        database.insert_subject_record(student_id, subject, internal, external)
        sync_performance_records()
        return jsonify({'success': True, 'message': 'Subject record saved.'})


@app.route('/api/performance/compare', methods=['POST'])
def api_compare_performance():
    data = request.get_json() or {}
    student_ids = data.get('student_ids', [])
    if not student_ids or len(student_ids) < 2:
        return jsonify({'success': False, 'error': 'Please select at least 2 students to compare.'}), 400

    res = compare_student_performance(student_ids)
    return jsonify({'success': True, 'data': res})


@app.route('/api/reports/generate', methods=['POST'])
def api_generate_report():
    data = request.get_json() or request.form
    report_type = data.get('report_type', 'complete_data')
    format_type = data.get('format', 'pdf').lower()

    conn = database.get_db_connection()
    if report_type == 'complete_data':
        rows = conn.execute('''
            SELECT s.student_id, s.student_name, s.department, s.semester,
                   sub.subject, sub.internal_marks, sub.external_marks,
                   sub.total_marks, sub.grade, sub.result
            FROM students s
            JOIN subjects sub ON s.student_id = sub.student_id
            ORDER BY s.student_id, sub.subject
        ''').fetchall()
        report_data = [dict(r) for r in rows]

    elif report_type == 'top_performers':
        rows = conn.execute('''
            SELECT s.student_id, s.student_name, s.department, s.semester,
                   ROUND(AVG(sub.total_marks), 2) as average_marks,
                   ROUND(pr.attendance_percentage, 1) as attendance_percentage,
                   pr.overall_grade
            FROM students s
            JOIN subjects sub ON s.student_id = sub.student_id
            LEFT JOIN performance_records pr ON s.student_id = pr.student_id
            GROUP BY s.student_id
            ORDER BY average_marks DESC
        ''').fetchall()
        report_data = [dict(r) for r in rows]

    elif report_type == 'at_risk_students':
        report_data = get_at_risk_students()

    else:  # performance_analysis
        rows = conn.execute('''
            SELECT s.student_id, s.student_name, s.department, s.semester,
                   ROUND(AVG(sub.total_marks), 2) as average_marks,
                   ROUND(pr.attendance_percentage, 1) as attendance_percentage,
                   pr.overall_grade,
                   ROUND(CAST(COUNT(CASE WHEN sub.result = 'Pass' THEN 1 END) AS FLOAT) / COUNT(sub.id) * 100, 1) as pass_percentage
            FROM students s
            JOIN subjects sub ON s.student_id = sub.student_id
            LEFT JOIN performance_records pr ON s.student_id = pr.student_id
            GROUP BY s.student_id
            ORDER BY s.student_id
        ''').fetchall()
        report_data = [dict(r) for r in rows]

    conn.close()

    try:
        if format_type == 'pdf':
            filepath = generate_pdf_report(report_type, report_data)
        else:
            filepath = generate_csv_report(report_type, report_data)

        filename = os.path.basename(filepath)
        return jsonify({
            'success': True,
            'filename': filename,
            'download_url': url_for('download_report', filename=filename)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/reports/download/<filename>')
def download_report(filename):
    return send_from_directory(config.REPORTS_FOLDER, filename, as_attachment=True)


@app.route('/api/sample-csv')
def download_sample_csv():
    """Generate and return a clean sample CSV for user testing."""
    sample_rows = [
        ['student_id', 'student_name', 'age', 'gender', 'department', 'semester',
         'subject', 'internal_marks', 'external_marks', 'total_marks', 'attendance_percentage', 'grade', 'result'],
        ['STU2001', 'Aditya Nair', '20', 'Male', 'Computer Science', '4', 'Data Structures', '28', '64', '92', '85.5', 'A+', 'Pass'],
        ['STU2001', 'Aditya Nair', '20', 'Male', 'Computer Science', '4', 'Database Systems', '25', '60', '85', '85.5', 'A', 'Pass'],
        ['STU2002', 'Bhavna Sen', '21', 'Female', 'Electronics', '6', 'Digital Electronics', '14', '22', '36', '45.0', 'F', 'Fail'],
        ['STU2002', 'Bhavna Sen', '21', 'Female', 'Electronics', '6', 'Circuit Theory', '12', '20', '32', '45.0', 'F', 'Fail'],
        ['STU2003', 'Chirag Sethi', '19', 'Male', 'Mechanical', '2', 'Thermodynamics', '22', '48', '70', '78.0', 'B+', 'Pass'],
        ['STU2004', 'Deepa Menon', '20', 'Female', 'Civil', '4', 'Structural Analysis', '27', '61', '88', '92.0', 'A', 'Pass'],
        ['STU2005', 'Eshan Khan', '22', 'Male', 'Electrical', '8', 'Power Systems', '10', '18', '28', '40.0', 'F', 'Fail']
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(sample_rows)
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='sample_student_dataset.csv'
    )


# ── Initialization Hook ─────────────────────────────────────────────────────

database.init_db()
seed_sample_data_if_empty()

if __name__ == '__main__':
    # Default port 5000, host 127.0.0.1
    port = int(os.environ.get('PORT', 5000))
    print(f" * Student Performance Analysis System running on http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, debug=True)
