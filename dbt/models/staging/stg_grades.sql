-- One row per grade, turned into a percentage of that assignment's maximum.
-- The percentage is rounded to one decimal place first and the band is chosen
-- from the rounded number, exactly like src/batch/grade_distribution.py.

with graded as (
    select
        grades.grade_id,
        grades.student_id,
        assignments.class_id,
        grades.assignment_id,
        grades.score,
        assignments.max_score,
        round(100.0 * grades.score / assignments.max_score, 1) as percent
    from {{ source('educonnect', 'grades') }} as grades
    join {{ source('educonnect', 'assignments') }} as assignments
        on assignments.assignment_id = grades.assignment_id
)

select
    *,
    case
        when percent < 50 then '0-49'
        when percent < 60 then '50-59'
        when percent < 70 then '60-69'
        when percent < 80 then '70-79'
        else '80-100'
    end as band
from graded
