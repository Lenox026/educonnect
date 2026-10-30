#!/usr/bin/env bash
# Local data-engineering demo. Run from the project root with Docker up
# and the project virtualenv active. Stops on the first failure.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -z "${VIRTUAL_ENV:-}" && -x .venv/bin/python ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "== Docker"
docker compose up -d

echo "== Generate"
python src/generator/produce_events.py

echo "== Quality"
python src/quality/check_events.py

echo "== Load PostgreSQL"
python src/loader/load_events.py

echo "== Spark weekly attendance"
python src/batch/weekly_attendance.py

echo "== Spark grade distribution"
python src/batch/grade_distribution.py

echo "== Lake export"
python src/batch/export_lake.py
ls -la data/lake/raw-events/*/*/*/

echo
echo "Core files are ready. In another terminal keep this running:"
echo "  python -m uvicorn api:app --app-dir src --port 8000"
echo "In a third terminal:"
echo "  python src/listen_attendance.py"
echo "Then post the sample:"
echo "  curl -X POST http://127.0.0.1:8000/attendance -H 'Content-Type: application/json' -d @data/samples/attendance_event.json"
echo
echo "Airflow (optional):"
echo "  export AIRFLOW_HOME=\"\$PWD/.airflow\""
echo "  export AIRFLOW__CORE__DAGS_FOLDER=\"\$PWD/dags\""
echo "  export AIRFLOW__CORE__LOAD_EXAMPLES=false"
echo "  airflow dags test educonnect_nightly 2026-10-15"
