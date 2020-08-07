with
const as (
  select
    '2020-07-24 19:00:00 -04:00' as start_date,
    '2020-07-28 19:00:00 -04:00' as end_date,
    60 as time_span,
    '7c08c3fb-31ad-4fc7-8253-cddbd9ad2359' as viewshed_name
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