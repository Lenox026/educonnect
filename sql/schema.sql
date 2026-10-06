-- EduConnect database schema (PostgreSQL, third normal form).
--
-- Every row loaded from this project is synthetic. Do not put real learner
-- names, South African ID numbers, or parent contact details in these tables.
--
-- Re-run this file safely: it drops the tables first, then creates them again.
-- Drop order follows foreign keys, children before parents.

DROP TABLE IF EXISTS grades;
DROP TABLE IF EXISTS attendance;
DROP TABLE IF EXISTS assignments;
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS classes;
DROP TABLE IF EXISTS teachers;
DROP TABLE IF EXISTS students;

-- Who teaches. The name lives here once, and classes point at teacher_id.
CREATE TABLE teachers (
    teacher_id    INTEGER PRIMARY KEY,
    teacher_name  TEXT NOT NULL
);

-- Who learns. grade_level is a property of the learner, so it stays on this table.
CREATE TABLE students (
    student_id   INTEGER PRIMARY KEY,
    first_name   TEXT NOT NULL,
    last_name    TEXT NOT NULL,
    grade_level  INTEGER NOT NULL CHECK (grade_level BETWEEN 8 AND 12)
);

-- A subject group for one grade, taught by one teacher.
-- class_name is stored here, not copied onto every attendance or grade row.
CREATE TABLE classes (
    class_id      INTEGER PRIMARY KEY,
    subject       TEXT NOT NULL,
    class_name    TEXT NOT NULL,
    grade_level   INTEGER NOT NULL CHECK (grade_level BETWEEN 8 AND 12),
    teacher_id    INTEGER NOT NULL REFERENCES teachers (teacher_id)
);

-- Which learners sit in which classes.
-- The key is the pair (student_id, class_id). There is no extra column that
-- would depend on only one half of that pair.
CREATE TABLE enrollments (
    student_id  INTEGER NOT NULL REFERENCES students (student_id),
    class_id    INTEGER NOT NULL REFERENCES classes (class_id),
    PRIMARY KEY (student_id, class_id)
);

-- Work set by a class. max_score belongs to the assignment itself.
-- It is not stored again on each learner's grade.
CREATE TABLE assignments (
    assignment_id  INTEGER PRIMARY KEY,
    class_id       INTEGER NOT NULL REFERENCES classes (class_id),
    title          TEXT NOT NULL,
    max_score      INTEGER NOT NULL CHECK (max_score > 0),
    UNIQUE (class_id, title)
);

-- One attendance mark per learner, per class, per calendar day.
CREATE TABLE attendance (
    attendance_id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id       INTEGER NOT NULL REFERENCES students (student_id),
    class_id         INTEGER NOT NULL REFERENCES classes (class_id),
    attendance_date  DATE NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('present', 'absent', 'late')),
    recorded_at      TIMESTAMPTZ NOT NULL,
    UNIQUE (student_id, class_id, attendance_date)
);

-- One score per learner per assignment.
-- score >= 0 is checked here. score <= assignments.max_score is checked
-- by the Python validation step, because a CHECK cannot read another table.
CREATE TABLE grades (
    grade_id       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id     INTEGER NOT NULL REFERENCES students (student_id),
    assignment_id  INTEGER NOT NULL REFERENCES assignments (assignment_id),
    score          INTEGER NOT NULL CHECK (score >= 0),
    graded_at      TIMESTAMPTZ NOT NULL,
    UNIQUE (student_id, assignment_id)
);

CREATE INDEX attendance_by_date ON attendance (attendance_date);
CREATE INDEX grades_by_student ON grades (student_id);
