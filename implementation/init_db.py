import sqlite3
import os

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    cohort TEXT NOT NULL,
    score REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL DEFAULT 3
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    grade TEXT,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);
"""

SEED_SQL = """
INSERT OR IGNORE INTO students (name, email, cohort, score) VALUES
    ('Alice Nguyen', 'alice@example.com', 'A1', 85.5),
    ('Bob Tran', 'bob@example.com', 'A1', 72.0),
    ('Carol Le', 'carol@example.com', 'B2', 91.0),
    ('David Pham', 'david@example.com', 'B2', 68.5),
    ('Eva Hoang', 'eva@example.com', 'A1', 95.0);

INSERT OR IGNORE INTO courses (code, title, credits) VALUES
    ('CS101', 'Introduction to Programming', 4),
    ('CS201', 'Data Structures', 3),
    ('CS301', 'Database Systems', 3),
    ('MATH101', 'Calculus I', 4);

INSERT OR IGNORE INTO enrollments (student_id, course_id, grade) VALUES
    (1, 1, 'A'),
    (1, 2, 'B+'),
    (2, 1, 'B'),
    (3, 3, 'A'),
    (3, 4, 'A-'),
    (4, 2, 'C+'),
    (5, 1, 'A'),
    (5, 3, 'A+');
"""


def create_database(db_path: str | None = None) -> str:
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab.db")

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
        print(f"Database created at: {db_path}")
        return db_path
    finally:
        conn.close()


if __name__ == "__main__":
    create_database()
