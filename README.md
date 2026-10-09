# EduConnect

EduConnect is a small school-data platform for the cloud computing and data engineering capstone. It turns fake attendance and grade events into tables, checks, and later into batch jobs and a serverless notification.

The project currently has two slices you can run on a laptop:

1. A database shape and a Python script that invents a school.
2. PostgreSQL in Docker, a loader for that school, and a small API that records attendance.

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

## Load the school into PostgreSQL

Docker Desktop or the Docker engine needs to be running.

```bash
docker compose up -d
python src/loader/load_events.py
```

The loader rebuilds the tables from `sql/schema.sql` and inserts the JSON file. Running it again replaces the rows. The database password in `docker-compose.yml` is for this local demo only.

Stop the database with `docker compose down`. Add `-v` when you also want to delete the saved data.

## Run the API

```bash
python -m uvicorn api:app --app-dir src --port 8000
```

Open http://127.0.0.1:8000/docs . `POST /attendance` accepts the same JSON as `data/samples/attendance_event.json`. Posting the same learner, class, and day again updates that mark.

Read one learner back:

```bash
curl http://127.0.0.1:8000/students/1001/attendance
```

## What to open first

| File | Why it is there |
| --- | --- |
| `sql/schema.sql` | PostgreSQL tables in third normal form. |
| `data/samples/attendance_event.json` | One attendance event in the shape the API accepts. |
| `src/generator/produce_events.py` | Builds a fake school and writes the JSON file. |
| `src/loader/load_events.py` | Checks the events and loads them into PostgreSQL. |
| `src/api.py` | Records one attendance mark and reads marks back. |
| `docker-compose.yml` | Starts the local PostgreSQL database. |
| `docs/data-model.md` | How an event becomes rows, in plain language. |

## What is next

Add a quality-check script and a fast lookup for today's attendance, then the Spark job and the Airflow export.
