"""
Nightly EduConnect pipeline.

Order:
1. Check the generated events.
2. Build the weekly attendance report.
3. Build the grade distribution.
4. Copy those files into raw-events/YYYY/MM/DD/.

The DAG uses the project virtualenv, because that environment has Spark.
"""

from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "bin" / "python"

with DAG(
    dag_id="educonnect_nightly",
    description="Check events, run the Spark jobs, and export the date folder.",
    start_date=datetime(2026, 10, 1),
    schedule="0 2 * * *",
    catchup=False,
) as dag:
    check_events = BashOperator(
        task_id="check_events",
        bash_command=f'"{PYTHON}" src/quality/check_events.py',
        cwd=str(ROOT),
    )
    weekly_attendance = BashOperator(
        task_id="weekly_attendance",
        bash_command=f'"{PYTHON}" src/batch/weekly_attendance.py',
        cwd=str(ROOT),
    )
    grade_distribution = BashOperator(
        task_id="grade_distribution",
        bash_command=f'"{PYTHON}" src/batch/grade_distribution.py',
        cwd=str(ROOT),
    )
    export_lake = BashOperator(
        task_id="export_lake",
        bash_command=f'"{PYTHON}" src/batch/export_lake.py',
        cwd=str(ROOT),
    )

    check_events >> weekly_attendance >> grade_distribution >> export_lake
