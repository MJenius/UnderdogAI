with matches as (
    select * from {{ ref('stg_match_results') }}
),
rankings as (
    select * from {{ ref('stg_fifa_rankings') }}
),
home_ranks as (
    select
        m.match_id,
        r.rank as home_rank,
        r.total_points as home_total_points,
        r.rank_date as home_rank_date,
        row_number() over (partition by m.match_id order by r.rank_date desc) as rn
    from matches m
    left join rankings r
        on m.home_team = r.country_full
        and r.rank_date <= m.match_date
),
away_ranks as (
    select
        m.match_id,
        r.rank as away_rank,
        r.total_points as away_total_points,
        r.rank_date as away_rank_date,
        row_number() over (partition by m.match_id order by r.rank_date desc) as rn
    from matches m
    left join rankings r
        on m.away_team = r.country_full
        and r.rank_date <= m.match_date
)
select
    m.match_id,
    m.match_date,
    m.home_team,
    m.away_team,
    m.home_score,
    m.away_score,
    m.tournament,
    m.city,
    m.country,
    m.neutral,
    hr.home_rank,
    hr.home_total_points,
    hr.home_rank_date,
    ar.away_rank,
    ar.away_total_points,
    ar.away_rank_date
from matches m
left join home_ranks hr
    on m.match_id = hr.match_id
    and hr.rn = 1
left join away_ranks ar
    on m.match_id = ar.match_id
    and ar.rn = 1
