-- A test passes when it returns no rows.
select *
from {{ ref('attendance_weekly_by_class') }}
where attendance_rate < 0 or attendance_rate > 1
