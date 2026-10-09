"""
Write a file of fake EduConnect events.

Every name and number comes from Faker and the Python random module.
Nothing in the output is a real learner. The student IDs are made up for
this course. They are not national ID numbers.

From the project root:

    python -m pip install -r requirements.txt
    python src/generator/produce_events.py

The script writes data/generated/events.json. That folder is gitignored.
Load it afterwards with python src/loader/load_events.py.
Open data/samples/attendance_event.json to see the shape of one attendance event.
"""

import argparse
import json
import random
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from faker import Faker

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "data" / "generated" / "events.json"
TIMEZONE = ZoneInfo("Africa/Johannesburg")

SUBJECTS = (
    "Mathematics",
    "English",
    "Natural Sciences",
    "History",
    "Life Orientation",
)

ASSIGNMENT_TITLES = (
    "Quiz 1",
    "Quiz 2",
)

# Most learners are present. A few are late or absent, so the later
# attendance charts have something to show.
STATUS_WEIGHTS = (
    ("present", 82),
    ("late", 8),
    ("absent", 10),
)


def build_school(fake: Faker, student_count: int, school_days: int) -> dict:
    """Create a small high school and the events that school would emit."""
    teachers = build_teachers(fake)
    classes = build_classes(teachers)
    students = build_students(fake, student_count)
    enrollments = build_enrollments(students, classes)
    assignments = build_assignments(classes)
    events = []
    events.extend(build_attendance_events(enrollments, school_days))
    events.extend(build_grade_events(enrollments, assignments))
    events.sort(key=lambda event: event["event_time"])
    return {
        "synthetic": True,
        "description": "Fake EduConnect data for coursework. No real learners.",
        "students": students,
        "teachers": teachers,
        "classes": classes,
        "enrollments": enrollments,
        "assignments": assignments,
        "events": events,
    }


def build_teachers(fake: Faker) -> list[dict]:
    """One teacher per subject. The same person teaches that subject in every grade."""
    return [
        {"teacher_id": teacher_id, "teacher_name": fake.name()}
        for teacher_id, _subject in enumerate(SUBJECTS, start=1)
    ]


def build_classes(teachers: list[dict]) -> list[dict]:
    """Grades 10 and 11, five subjects each. class_id 10 is Grade 10 Mathematics."""
    classes = []
    class_id = 10
    for grade_level in (10, 11):
        for teacher, subject in zip(teachers, SUBJECTS):
            classes.append(
                {
                    "class_id": class_id,
                    "subject": subject,
                    "class_name": f"Grade {grade_level} {subject}",
                    "grade_level": grade_level,
                    "teacher_id": teacher["teacher_id"],
                }
            )
            class_id += 1
    return classes


def build_students(fake: Faker, student_count: int) -> list[dict]:
    """Split learners evenly between grade 10 and grade 11."""
    students = []
    for offset in range(student_count):
        grade_level = 10 if offset < student_count / 2 else 11
        students.append(
            {
                "student_id": 1001 + offset,
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "grade_level": grade_level,
            }
        )
    return students


def build_enrollments(students: list[dict], classes: list[dict]) -> list[dict]:
    """Each learner is enrolled in every subject for their own grade."""
    classes_by_grade: dict[int, list[int]] = {}
    for school_class in classes:
        classes_by_grade.setdefault(school_class["grade_level"], []).append(
            school_class["class_id"]
        )

    enrollments = []
    for student in students:
        for class_id in classes_by_grade[student["grade_level"]]:
            enrollments.append(
                {
                    "student_id": student["student_id"],
                    "class_id": class_id,
                }
            )
    return enrollments


def build_assignments(classes: list[dict]) -> list[dict]:
    """Two short quizzes per class. The maximum mark differs by subject."""
    max_score_by_subject = {
        "Mathematics": 25,
        "English": 40,
        "Natural Sciences": 30,
        "History": 50,
        "Life Orientation": 20,
    }
    assignments = []
    assignment_id = 501
    for school_class in classes:
        for title in ASSIGNMENT_TITLES:
            assignments.append(
                {
                    "assignment_id": assignment_id,
                    "class_id": school_class["class_id"],
                    "title": title,
                    "max_score": max_score_by_subject[school_class["subject"]],
                }
            )
            assignment_id += 1
    return assignments


def build_attendance_events(enrollments: list[dict], school_days: int) -> list[dict]:
    """One attendance event per enrollment on each weekday, counting back from today."""
    days = recent_weekdays(school_days)
    statuses = [status for status, _weight in STATUS_WEIGHTS]
    weights = [weight for _status, weight in STATUS_WEIGHTS]
    events = []

    for attendance_date in days:
        for enrollment in enrollments:
            recorded_at = datetime.combine(
                attendance_date,
                time(hour=7, minute=random.randint(30, 55)),
                tzinfo=TIMEZONE,
            )
            events.append(
                {
                    "event_id": new_event_id(),
                    "event_type": "attendance",
                    "event_time": recorded_at.isoformat(),
                    "student_id": enrollment["student_id"],
                    "class_id": enrollment["class_id"],
                    "attendance_date": attendance_date.isoformat(),
                    "status": random.choices(statuses, weights=weights, k=1)[0],
                }
            )
    return events


def build_grade_events(enrollments: list[dict], assignments: list[dict]) -> list[dict]:
    """One grade event per learner per assignment in their classes."""
    assignments_by_class: dict[int, list[dict]] = {}
    for assignment in assignments:
        assignments_by_class.setdefault(assignment["class_id"], []).append(assignment)

    graded_on = date.today()
    events = []
    for enrollment in enrollments:
        for assignment in assignments_by_class[enrollment["class_id"]]:
            graded_at = datetime.combine(
                graded_on,
                time(hour=15, minute=random.randint(0, 40)),
                tzinfo=TIMEZONE,
            )
            max_score = assignment["max_score"]
            # Cluster scores around 70 percent, then keep them inside 0..max_score.
            raw_score = int(random.triangular(0, max_score, max_score * 0.7))
            events.append(
                {
                    "event_id": new_event_id(),
                    "event_type": "grade",
                    "event_time": graded_at.isoformat(),
                    "student_id": enrollment["student_id"],
                    "class_id": enrollment["class_id"],
                    "assignment_id": assignment["assignment_id"],
                    "assignment_title": assignment["title"],
                    "score": raw_score,
                    "max_score": max_score,
                }
            )
    return events


def new_event_id() -> str:
    """A UUID drawn from the seeded random module, so --seed repeats the file."""
    return str(uuid.UUID(int=random.getrandbits(128), version=4))


def recent_weekdays(school_days: int) -> list[date]:
    """The last `school_days` weekdays, including today when today is a weekday."""
    days = []
    cursor = date.today()
    while len(days) < school_days:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    days.reverse()
    return days


def count_events(events: list[dict], event_type: str) -> int:
    return sum(1 for event in events if event["event_type"] == event_type)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write fake EduConnect events to JSON.")
    parser.add_argument("--students", type=int, default=40, help="How many fake learners.")
    parser.add_argument("--days", type=int, default=10, help="How many school days.")
    parser.add_argument("--seed", type=int, default=42, help="Makes the same file each run.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="JSON file to write.")
    args = parser.parse_args()

    if args.students < 2:
        raise SystemExit("--students must be at least 2 so both grades have learners.")
    if args.days < 1:
        raise SystemExit("--days must be at least 1.")

    random.seed(args.seed)
    fake = Faker()
    Faker.seed(args.seed)

    payload = build_school(fake, args.students, args.days)
    payload["seed"] = args.seed

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    events = payload["events"]
    print(f"Wrote {len(events)} events to {args.output}")
    print(f"  students: {len(payload['students'])}")
    print(f"  classes: {len(payload['classes'])}")
    print(f"  attendance events: {count_events(events, 'attendance')}")
    print(f"  grade events: {count_events(events, 'grade')}")


if __name__ == "__main__":
    main()
