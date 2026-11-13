"""
Configuration settings for the Student Performance Analysis application.
"""

import os

# ── Base directory ──────────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ── Flask configuration ────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY', 'student-performance-analysis-secret-key-2024')
DATABASE_PATH = os.path.join(BASE_DIR, 'data', 'student_performance.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
REPORTS_FOLDER = os.path.join(BASE_DIR, 'reports')
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

# ── Java configuration (required for PySpark) ──────────────────────────────
JAVA_HOME = r'C:\Program Files\Java\jdk-27'
os.environ['JAVA_HOME'] = JAVA_HOME

# ── PySpark configuration ──────────────────────────────────────────────────
SPARK_APP_NAME = 'StudentPerformanceAnalysis'
SPARK_MASTER = 'local[*]'
SPARK_CONFIG = {
    'spark.driver.memory': '2g',
    'spark.sql.shuffle.partitions': '4',
    'spark.ui.showConsoleProgress': 'false',
    'spark.sql.execution.arrow.pyspark.enabled': 'false',
    'spark.log.level': 'WARN',
}

# ── Grade thresholds ───────────────────────────────────────────────────────
GRADE_THRESHOLDS = {
    'A+': 90,
    'A': 80,
    'B+': 70,
    'B': 60,
    'C': 50,
    'D': 40,
    'F': 0,
}

PASS_MARK = 40

# ── Departments and semesters ──────────────────────────────────────────────
DEPARTMENTS = [
    'Computer Science', 'Electronics', 'Mechanical', 'Civil', 'Electrical'
]
SEMESTERS = list(range(1, 9))

SUBJECTS = [
    'Mathematics', 'Physics', 'Chemistry', 'Data Structures',
    'Database Systems', 'Computer Networks', 'Operating Systems',
    'Software Engineering', 'Digital Electronics', 'Circuit Theory',
    'Thermodynamics', 'Structural Analysis', 'Power Systems', 'Machine Design'
]
