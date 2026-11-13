"""
CSV validation and data cleaning module.
Validates uploaded CSV files, cleans data, detects duplicates,
and provides file information.
"""

import os
import pandas as pd

# Required columns in the uploaded CSV
REQUIRED_COLUMNS = [
    'student_id', 'student_name', 'age', 'gender', 'department',
    'semester', 'subject', 'internal_marks', 'external_marks',
    'total_marks', 'attendance_percentage', 'grade', 'result'
]


def validate_csv_file(filepath):
    """
    Validate that the CSV file exists, is readable, and contains
    all required columns.

    Returns:
        dict: {'valid': bool, 'errors': list, 'warnings': list}
    """
    result = {'valid': True, 'errors': [], 'warnings': []}

    # Check file exists
    if not os.path.exists(filepath):
        result['valid'] = False
        result['errors'].append(f"File not found: {filepath}")
        return result

    # Check file extension
    if not filepath.lower().endswith('.csv'):
        result['valid'] = False
        result['errors'].append("File must be a CSV (.csv) file.")
        return result

    # Try reading the file
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        result['valid'] = False
        result['errors'].append(f"Cannot read CSV file: {e}")
        return result

    if df.empty:
        result['valid'] = False
        result['errors'].append("CSV file is empty.")
        return result

    # Normalise column names
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

    # Check required columns
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        result['valid'] = False
        result['errors'].append(f"Missing required columns: {', '.join(missing)}")

    # Warnings for data issues
    if df.isnull().any().any():
        null_cols = df.columns[df.isnull().any()].tolist()
        result['warnings'].append(
            f"Columns with missing values: {', '.join(null_cols)}"
        )

    if 'student_id' in df.columns and df['student_id'].duplicated().any():
        result['warnings'].append(
            "Duplicate student_id entries detected (expected for multi-subject data)."
        )

    return result


def clean_data(df):
    """
    Clean a pandas DataFrame:
    - Strip whitespace from string columns
    - Fill missing numeric values with 0
    - Clamp marks to 0-100 range
    - Clamp attendance to 0-100 range
    - Recalculate total_marks, grade, result if necessary

    Args:
        df: pandas DataFrame with student data

    Returns:
        tuple: (cleaned_df, cleaning_report dict)
    """
    report = {
        'rows_before': len(df),
        'changes': [],
    }

    df = df.copy()
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

    # Strip string columns
    str_cols = df.select_dtypes(include='object').columns
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()

    # Fill missing numeric values
    numeric_cols = ['internal_marks', 'external_marks', 'total_marks',
                    'attendance_percentage', 'age', 'semester']
    for col in numeric_cols:
        if col in df.columns:
            missing = df[col].isnull().sum()
            if missing > 0:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                report['changes'].append(f"Filled {missing} missing values in {col}")

    # Clamp marks 0-100
    for col in ['internal_marks', 'external_marks']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            clamped = ((df[col] < 0) | (df[col] > 100)).sum()
            if clamped > 0:
                df[col] = df[col].clip(0, 100)
                report['changes'].append(f"Clamped {clamped} values in {col} to 0-100")

    # Recalculate total_marks
    if 'internal_marks' in df.columns and 'external_marks' in df.columns:
        df['total_marks'] = df['internal_marks'] + df['external_marks']

    # Clamp total_marks to 0-100 for display/grading (single-subject total)
    if 'total_marks' in df.columns:
        df['total_marks'] = pd.to_numeric(df['total_marks'], errors='coerce').fillna(0)

    # Clamp attendance 0-100
    if 'attendance_percentage' in df.columns:
        df['attendance_percentage'] = pd.to_numeric(
            df['attendance_percentage'], errors='coerce'
        ).fillna(0).clip(0, 100)

    # Recalculate grade
    def _grade(m):
        if m >= 90: return 'A+'
        if m >= 80: return 'A'
        if m >= 70: return 'B+'
        if m >= 60: return 'B'
        if m >= 50: return 'C'
        if m >= 40: return 'D'
        return 'F'

    if 'total_marks' in df.columns:
        df['grade'] = df['total_marks'].apply(_grade)
        df['result'] = df['total_marks'].apply(
            lambda m: 'Pass' if m >= 40 else 'Fail'
        )

    report['rows_after'] = len(df)
    return df, report


def detect_duplicates(df):
    """
    Detect fully duplicate rows and duplicate student+subject combinations.

    Returns:
        dict with counts and details of duplicates found.
    """
    df = df.copy()
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

    result = {
        'exact_duplicates': 0,
        'student_subject_duplicates': 0,
        'duplicate_details': []
    }

    # Exact duplicates
    exact = df.duplicated()
    result['exact_duplicates'] = int(exact.sum())

    # Student + subject duplicates
    if 'student_id' in df.columns and 'subject' in df.columns:
        dup_mask = df.duplicated(subset=['student_id', 'subject'], keep=False)
        dup_rows = df[dup_mask]
        result['student_subject_duplicates'] = len(dup_rows)
        if len(dup_rows) > 0:
            grouped = dup_rows.groupby(['student_id', 'subject']).size().reset_index(name='count')
            result['duplicate_details'] = grouped.to_dict('records')

    return result


def get_file_info(filepath):
    """
    Return summary information about a CSV file.

    Returns:
        dict: rows, columns, column names, missing values summary, preview rows
    """
    if not os.path.exists(filepath):
        return {'error': f"File not found: {filepath}"}

    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        return {'error': f"Cannot read file: {e}"}

    info = {
        'filename': os.path.basename(filepath),
        'file_size_kb': round(os.path.getsize(filepath) / 1024, 2),
        'rows': len(df),
        'columns': len(df.columns),
        'column_names': list(df.columns),
        'missing_values': {
            col: int(df[col].isnull().sum())
            for col in df.columns if df[col].isnull().any()
        },
        'preview': df.head(5).to_dict('records'),
        'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
    }
    return info
