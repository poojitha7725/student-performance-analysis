"""
SQLite database module for the Student Performance Analysis application.
Handles all database operations including CRUD for students, subjects,
and performance records.
"""

import sqlite3
import os
import csv
import pandas as pd

from config import DATABASE_PATH, PASS_MARK, GRADE_THRESHOLDS


# ── Helpers ─────────────────────────────────────────────────────────────────

def _calculate_grade(total_marks):
    """Return letter grade based on total marks."""
    if total_marks >= 90:
        return 'A+'
    elif total_marks >= 80:
        return 'A'
    elif total_marks >= 70:
        return 'B+'
    elif total_marks >= 60:
        return 'B'
    elif total_marks >= 50:
        return 'C'
    elif total_marks >= 40:
        return 'D'
    else:
        return 'F'


def _calculate_result(total_marks):
    """Return Pass or Fail based on total marks."""
    return 'Pass' if total_marks >= PASS_MARK else 'Fail'


# ── Connection ──────────────────────────────────────────────────────────────

def get_db_connection():
    """Create and return a database connection with Row factory."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Schema ──────────────────────────────────────────────────────────────────

def init_db():
    """Initialise the database schema (idempotent)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id   TEXT PRIMARY KEY,
            student_name TEXT NOT NULL,
            age          INTEGER,
            gender       TEXT,
            department   TEXT,
            semester     INTEGER
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id      TEXT NOT NULL,
            subject         TEXT NOT NULL,
            internal_marks  REAL,
            external_marks  REAL,
            total_marks     REAL,
            grade           TEXT,
            result          TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
                ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS performance_records (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id            TEXT NOT NULL,
            attendance_percentage REAL,
            average_marks         REAL,
            overall_grade         TEXT,
            risk_category         TEXT,
            recommendations       TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
                ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()
    return True


# ── Student CRUD ────────────────────────────────────────────────────────────

def insert_student(student_id, student_name, age, gender, department, semester):
    """Insert a single student record. Returns True on success."""
    conn = get_db_connection()
    try:
        conn.execute(
            '''INSERT OR REPLACE INTO students
               (student_id, student_name, age, gender, department, semester)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (student_id, student_name, age, gender, department, semester)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def update_student(student_id, **kwargs):
    """Update fields of an existing student record."""
    allowed = {'student_name', 'age', 'gender', 'department', 'semester'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return False

    set_clause = ', '.join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [student_id]

    conn = get_db_connection()
    try:
        conn.execute(
            f"UPDATE students SET {set_clause} WHERE student_id = ?", values
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def delete_student(student_id):
    """Delete a student and all related records (cascading)."""
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM subjects WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM performance_records WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_all_students():
    """Return a list of dicts for every student."""
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM students ORDER BY student_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_student_by_id(student_id):
    """Return a single student dict or None."""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM students WHERE student_id = ?", (student_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def search_students(query='', department=None, semester=None):
    """Search students by name/ID and optionally filter by department/semester."""
    conn = get_db_connection()
    sql = "SELECT * FROM students WHERE 1=1"
    params = []

    if query:
        sql += " AND (student_id LIKE ? OR student_name LIKE ?)"
        params.extend([f'%{query}%', f'%{query}%'])
    if department:
        sql += " AND department = ?"
        params.append(department)
    if semester is not None:
        sql += " AND semester = ?"
        params.append(int(semester))

    sql += " ORDER BY student_id"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Subject records ─────────────────────────────────────────────────────────

def insert_subject_record(student_id, subject, internal_marks, external_marks,
                          total_marks=None, grade=None, result=None):
    """Insert a subject record for a student."""
    if total_marks is None:
        total_marks = float(internal_marks) + float(external_marks)
    if grade is None:
        grade = _calculate_grade(total_marks)
    if result is None:
        result = _calculate_result(total_marks)

    conn = get_db_connection()
    try:
        conn.execute(
            '''INSERT INTO subjects
               (student_id, subject, internal_marks, external_marks,
                total_marks, grade, result)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (student_id, subject, internal_marks, external_marks,
             total_marks, grade, result)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_student_subjects(student_id):
    """Return all subject records for a given student."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM subjects WHERE student_id = ? ORDER BY subject",
        (student_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Bulk CSV import ─────────────────────────────────────────────────────────

def bulk_insert_from_csv(filepath):
    """
    Read a CSV file and insert students + subject records into the database.
    Expected columns: student_id, student_name, age, gender, department,
                      semester, subject, internal_marks, external_marks,
                      total_marks, attendance_percentage, grade, result
    Returns dict with counts of inserted records.
    """
    df = pd.read_csv(filepath)
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

    students_inserted = 0
    subjects_inserted = 0
    errors = []

    conn = get_db_connection()
    try:
        for _, row in df.iterrows():
            try:
                # Upsert student
                conn.execute(
                    '''INSERT OR REPLACE INTO students
                       (student_id, student_name, age, gender, department, semester)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (str(row['student_id']), str(row['student_name']),
                     int(row['age']), str(row['gender']),
                     str(row['department']), int(row['semester']))
                )
                students_inserted += 1

                # Insert subject record
                total = float(row.get('total_marks', 0)) or (
                    float(row.get('internal_marks', 0)) + float(row.get('external_marks', 0))
                )
                grade = row.get('grade') or _calculate_grade(total)
                result = row.get('result') or _calculate_result(total)
                attendance = float(row.get('attendance_percentage', 0))

                conn.execute(
                    '''INSERT INTO subjects
                       (student_id, subject, internal_marks, external_marks,
                        total_marks, grade, result)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (str(row['student_id']), str(row['subject']),
                     float(row.get('internal_marks', 0)),
                     float(row.get('external_marks', 0)),
                     total, str(grade), str(result))
                )
                subjects_inserted += 1

                # Upsert performance record with attendance
                existing = conn.execute(
                    "SELECT id FROM performance_records WHERE student_id = ?",
                    (str(row['student_id']),)
                ).fetchone()
                if existing:
                    conn.execute(
                        '''UPDATE performance_records
                           SET attendance_percentage = ?
                           WHERE student_id = ?''',
                        (attendance, str(row['student_id']))
                    )
                else:
                    conn.execute(
                        '''INSERT INTO performance_records
                           (student_id, attendance_percentage, average_marks,
                            overall_grade, risk_category, recommendations)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (str(row['student_id']), attendance, total,
                         str(grade), '', '')
                    )

            except Exception as e:
                errors.append(f"Row error: {e}")

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

    return {
        'students_inserted': students_inserted,
        'subjects_inserted': subjects_inserted,
        'errors': errors
    }


# ── Dashboard statistics ───────────────────────────────────────────────────

def get_dashboard_stats():
    """Aggregate statistics for the dashboard."""
    conn = get_db_connection()

    stats = {}

    # Total students
    row = conn.execute("SELECT COUNT(*) as cnt FROM students").fetchone()
    stats['total_students'] = row['cnt'] if row else 0

    # Total subject entries
    row = conn.execute("SELECT COUNT(*) as cnt FROM subjects").fetchone()
    stats['total_subject_entries'] = row['cnt'] if row else 0

    # Average marks
    row = conn.execute("SELECT AVG(total_marks) as avg_marks FROM subjects").fetchone()
    stats['average_marks'] = round(row['avg_marks'], 2) if row and row['avg_marks'] else 0

    # Pass / fail counts
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM subjects WHERE result = 'Pass'"
    ).fetchone()
    stats['pass_count'] = row['cnt'] if row else 0

    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM subjects WHERE result = 'Fail'"
    ).fetchone()
    stats['fail_count'] = row['cnt'] if row else 0

    # Department-wise count
    rows = conn.execute(
        "SELECT department, COUNT(*) as cnt FROM students GROUP BY department"
    ).fetchall()
    stats['department_counts'] = {r['department']: r['cnt'] for r in rows}

    # Grade distribution
    rows = conn.execute(
        "SELECT grade, COUNT(*) as cnt FROM subjects GROUP BY grade ORDER BY grade"
    ).fetchall()
    stats['grade_distribution'] = {r['grade']: r['cnt'] for r in rows}

    conn.close()
    return stats
