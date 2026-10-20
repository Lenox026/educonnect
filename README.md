# EduConnect

EduConnect is a small school-data platform for the cloud computing and data engineering capstone. It turns fake attendance and grade events into tables, checks, and later into batch jobs and a serverless notification.

The project currently has these slices:

1. A database shape and a Python script that invents a school.
2. PostgreSQL in Docker, a loader for that school, and a small API that records attendance.
3. A Pandas quality report, and Redis for today's attendance.
4. Redpanda, so each attendance mark is also published to a stream.
5. Spark jobs for the weekly attendance rate of each class, and for grade distribution.
6. An Airflow DAG that runs the check, both Spark jobs, and the date-folder export.
7. An AWS attendance API, defined in SAM.

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

## Check data quality

```bash
python src/quality/check_events.py
```

This reads the generated events with Pandas and prints PASS or FAIL for three rules: every event has a `student_id`, attendance status is `present`, `absent`, or `late`, and each grade is between 0 and that assignment's maximum. Load the file after the report says PASS.

## Run the API

```bash
python -m uvicorn api:app --app-dir src --port 8000
```

Open http://127.0.0.1:8000/docs . `POST /attendance` accepts the same JSON as `data/samples/attendance_event.json`. Posting the same learner, class, and day again updates that mark.

Read one learner back from PostgreSQL:

```bash
curl http://127.0.0.1:8000/students/1001/attendance
```

Today's marks come from Redis, which `docker compose up -d` starts with PostgreSQL:

```bash
curl http://127.0.0.1:8000/attendance/today
curl "http://127.0.0.1:8000/attendance/today?student_id=1001"
```

`POST /attendance` writes the row to PostgreSQL, stores today's mark in Redis, and publishes the event to Redpanda.

Watch the stream in a second terminal:

```bash
python src/listen_attendance.py
```

Post an attendance mark, and that terminal prints the learner, class, and status.

## Weekly attendance

Spark runs on this laptop. It does not need a cluster. This job uses Spark 3.5, which needs Java 17. On this machine the script finds Java 17 by itself.

```bash
python src/batch/weekly_attendance.py
```

The script reads the generated events and writes `data/generated/weekly_attendance.json`. Present and late count as attended. Each row is one class for one week, and the week starts on Monday.

## Grade distribution

```bash
python src/batch/grade_distribution.py
```

Each score becomes a percentage of that assignment's maximum. The report lists the average percentage per class, and how many grades fall into `0-49`, `50-59`, `60-69`, `70-79`, and `80-100`. The file is `data/generated/grade_distribution.json`.

## Date folders for the data lake

```bash
python src/batch/export_lake.py
```

This copies the raw events and both Spark reports into `data/lake/raw-events/YYYY/MM/DD/`. That is the same layout the project will later use at `s3://educonnect-data-lake/raw-events/YYYY/MM/DD/`. The folder is gitignored.

## Nightly Airflow job

Airflow is installed beside the main packages, because it has its own dependency list.

```bash
python -m pip install -r requirements-airflow.txt
export AIRFLOW_HOME="$PWD/.airflow"
export AIRFLOW__CORE__DAGS_FOLDER="$PWD/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=false
airflow db migrate
airflow dags test educonnect_nightly 2026-10-15
```

The DAG `educonnect_nightly` runs four steps in order: the Pandas check, weekly attendance, grade distribution, then the date-folder export. It is scheduled for 02:00 every day. `dags test` runs that pipeline once, immediately, so you can show it without waiting until 02:00.

## AWS attendance API

This slice runs in an AWS account, not in Docker. The template creates a private S3 bucket, a DynamoDB table, an SNS email topic, one Lambda, and an HTTP API. There is no EC2, RDS, NAT gateway, or SMS.

From the project root, with the AWS CLI and SAM CLI logged into the account you will use for the demo:

```bash
sam build --template infra/template.yaml
sam deploy --guided --template infra/template.yaml --parameter-overrides AlertEmail=you@example.com
```

Use your own email. After the stack finishes, open the email from AWS and confirm the subscription. The region to choose in the guided deploy is `us-east-1` if the account does not offer Cape Town.

`POST /attendance` uses the same JSON as `data/samples/attendance_event.json`. The function writes the mark to DynamoDB. Status `absent` also sends one email. `GET /attendance/today` reads that table. The base URL is the `ApiUrl` output.

The S3 bucket is named `educonnect-data-lake-<account id>`. It stays private. Objects belong under `raw-events/YYYY/MM/DD/`, the same layout as `data/lake/` on the laptop.

Delete the stack after the demo. Empty the bucket first if you uploaded files:

```bash
sam delete --stack-name educonnect
```

## What to open first

| File | Why it is there |
| --- | --- |
| `sql/schema.sql` | PostgreSQL tables in third normal form. |
| `data/samples/attendance_event.json` | One attendance event in the shape the API accepts. |
| `src/generator/produce_events.py` | Builds a fake school and writes the JSON file. |
| `src/loader/load_events.py` | Checks the events and loads them into PostgreSQL. |
| `src/quality/check_events.py` | Pandas pass or fail report for the generated events. |
| `src/cache.py` | Stores today's attendance in Redis. |
| `src/stream.py` | Publishes one attendance event to the Redpanda topic. |
| `src/listen_attendance.py` | Prints events as they arrive on that topic. |
| `src/api.py` | Records a mark, caches today in Redis, and publishes the event. |
| `src/batch/weekly_attendance.py` | Spark job for the weekly attendance rate of each class. |
| `src/batch/grade_distribution.py` | Spark job for the grade distribution of each class. |
| `src/batch/export_lake.py` | Copies raw events and Spark reports into `raw-events/YYYY/MM/DD/`. |
| `dags/educonnect_nightly.py` | Airflow DAG that runs the check, both Spark jobs, and the export. |
| `infra/template.yaml` | SAM template for API Gateway, Lambda, DynamoDB, SNS, S3, and CloudWatch logs. |
| `src/aws/attendance_handler.py` | Lambda that stores a mark and emails an absence. |
| `docker-compose.yml` | Starts local PostgreSQL, Redis, and Redpanda. |
| `docs/data-model.md` | How an event becomes rows, in plain language. |

## What is next

Add Cognito in front of the API, a one-page site on S3 and CloudFront, and a CloudWatch alarm.
