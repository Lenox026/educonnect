-- One row per attendance mark, with the Monday that starts its school week.
-- Present and late both count as attended, the same rule the Spark job uses.

select
    attendance_id,
    student_id,
    class_id,
    attendance_date,
    status,
    (status in ('present', 'late')) as attended,
    date_trunc('week', attendance_date)::date as week_start
from {{ source('educonnect', 'attendance') }}
