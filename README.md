# EduConnect

EduConnect is a small school-data platform for the cloud computing and data engineering capstone. It turns fake attendance and grade events into tables, checks, and later into batch jobs and a serverless notification.

This repository currently contains the first slice: the database shape, one example attendance event, and a Python script that invents a school.

Learner names in this project come from Faker. Do not replace them with real pupils, parents, or ID numbers.

## Run the generator

From the project root:

```bash
python -m pip install -r requirements.txt
python src/generator/produce_events.py
```

That writes `data/generated/events.json`. The file holds teachers, learners, classes, enrollments, assignments, and the events. The same command with the same seed writes the same school. Generated files stay on your machine; they are listed in `.gitignore`.

Useful options:

```bash
python src/generator/produce_events.py --students 20 --days 5 --seed 42
```

## What to open first

| File | Why it is there |
| --- | --- |
| `sql/schema.sql` | PostgreSQL tables in third normal form. |
| `data/samples/attendance_event.json` | One attendance event in the shape the rest of the pipeline will use. |
| `src/generator/produce_events.py` | Builds a fake school and writes the JSON file. |
| `docs/data-model.md` | How an event becomes rows, in plain language. |

## What is next

Load this JSON into PostgreSQL, then add a small FastAPI service that accepts one attendance event and inserts a row.
