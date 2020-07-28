//'MN-05-134168-L'
//'8671ac0a-3880-4b4b-883b-380d534e11c1' // ID
//'feb26c09-0879-4a9d-afdf-eda5942f67a7' // name
//

with
const as (
  select
    '2020-06-15' as start_date,
    '2020-06-22' as end_date,
    60 as time_span,
    'feb26c09-0879-4a9d-afdf-eda5942f67a7' as viewshed_name
)
,raw as (
  select
    observation:id:value as maid,
    trunc(observation:ts / const.time_span)::int as ts_cell
  from
    "SNOWPLOW_PROD"."L0"."OBSERVATIONEVENTS",
    const
  where
    concat(year, '-', month, '-', day)::timestamp >= const.start_date::timestamp
    and concat(year, '-', month, '-', day)::timestamp < const.end_date::timestamp
    and ARRAY_CONTAINS(const.viewshed_name::variant, viewsheds)
)
,ts_grid_range as (
  SELECT
    (extract(epoch from const.start_date::timestamp) / const.time_span + ROW_NUMBER() OVER (ORDER BY seq4()) - 1)::integer as ts_cell, const.*
  FROM
    const,
    TABLE(generator(rowcount => (extract(epoch from const.end_date::timestamp) - extract(epoch from const.start_date::timestamp)) / const.time_span))
)
,counts as (
  select
    ts_cell,
    count(distinct maid) as cnt
  from
    raw
  group by
    ts_cell
),
result as (
  select
    g.ts_cell * g.time_span as ts_cell,
    coalesce(c.cnt, 0) as cnt
  from
    ts_grid_range g
  left join
    counts c
  on
    g.ts_cell = c.ts_cell
  order by g.ts_cell
)
select * from result order by ts_cell