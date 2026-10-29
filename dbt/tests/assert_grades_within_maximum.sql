-- The rule the database cannot enforce with a CHECK: a score is never above its assignment's maximum.
select *
from {{ ref('stg_grades') }}
where score < 0 or score > max_score
