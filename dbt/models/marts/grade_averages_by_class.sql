-- Average percentage for each class. Same answer as the averages in grade_distribution.json.

select
    classes.class_id,
    classes.class_name,
    classes.subject,
    classes.grade_level,
    count(*) as grades,
    round(avg(stg_grades.percent), 1) as average_percent
from {{ ref('stg_grades') }} as stg_grades
join {{ source('educonnect', 'classes') }} as classes
    on classes.class_id = stg_grades.class_id
group by classes.class_id, classes.class_name, classes.subject, classes.grade_level
order by classes.class_id
