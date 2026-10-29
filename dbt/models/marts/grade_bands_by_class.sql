-- How many grades fall in each band for each class, and that band's share of the class.
-- Every class gets all five bands, including bands with zero grades, like grade_distribution.json.

with bands as (
    select * from (values
        ('0-49'),
        ('50-59'),
        ('60-69'),
        ('70-79'),
        ('80-100')
    ) as band_labels (band)
),

counted as (
    select class_id, band, count(*) as grades
    from {{ ref('stg_grades') }}
    group by class_id, band
),

per_class as (
    select class_id, count(*) as class_grades
    from {{ ref('stg_grades') }}
    group by class_id
)

select
    classes.class_id,
    classes.class_name,
    classes.subject,
    bands.band,
    coalesce(counted.grades, 0) as grades,
    round(coalesce(counted.grades, 0)::numeric / per_class.class_grades, 2) as share
from {{ source('educonnect', 'classes') }} as classes
cross join bands
left join counted
    on counted.class_id = classes.class_id and counted.band = bands.band
join per_class
    on per_class.class_id = classes.class_id
order by classes.class_id, bands.band
