-- Weekly attendance rate for each class. Same answer as weekly_attendance.json.

select
    stg_attendance.week_start,
    classes.class_id,
    classes.class_name,
    classes.subject,
    classes.grade_level,
    count(*) as marks,
    sum(stg_attendance.attended::int) as attended,
    round(sum(stg_attendance.attended::int)::numeric / count(*), 3) as attendance_rate
from {{ ref('stg_attendance') }} as stg_attendance
join {{ source('educonnect', 'classes') }} as classes
    on classes.class_id = stg_attendance.class_id
group by
    stg_attendance.week_start,
    classes.class_id,
    classes.class_name,
    classes.subject,
    classes.grade_level
order by stg_attendance.week_start, classes.class_id
