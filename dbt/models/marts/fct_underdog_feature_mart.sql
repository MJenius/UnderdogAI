with match_rankings as (
    select * from {{ ref('int_match_historical_rankings') }}
),
fifa_rankings as (
    select * from {{ ref('stg_fifa_rankings') }}
),
ranking_volatility as (
    select
        country_full,
        rank_date,
        stddev(rank) over (
            partition by country_full
            order by rank_date
            rows between 11 preceding and current row
        ) as rank_vol_12m
    from fifa_rankings
),
team_matches as (
    select
        match_id,
        match_date,
        home_team as team,
        case
            when home_score > away_score then 3
            when home_score = away_score then 1
            else 0
        end as points_secured
    from match_rankings
    union all
    select
        match_id,
        match_date,
        away_team as team,
        case
            when away_score > home_score then 3
            when away_score = home_score then 1
            else 0
        end as points_secured
    from match_rankings
),
team_rolling as (
    select
        match_id,
        team,
        avg(points_secured) over (
            partition by team
            order by match_date
            rows between 5 preceding and 1 preceding
        ) as team_rolling_point_velocity_5
    from team_matches
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
    m.home_rank,
    m.away_rank,
    (coalesce(m.home_rank, 0) - coalesce(m.away_rank, 0)) as rank_differential,
    coalesce(h_roll.team_rolling_point_velocity_5, 0) as home_rolling_point_velocity_5,
    coalesce(a_roll.team_rolling_point_velocity_5, 0) as away_rolling_point_velocity_5,
    coalesce(h_vol.rank_vol_12m, 0) as home_rank_volatility_12m,
    coalesce(a_vol.rank_vol_12m, 0) as away_rank_volatility_12m,
    (coalesce(h_roll.team_rolling_point_velocity_5, 0) * coalesce(m.home_rank, 0)) as home_underdog_signal_score,
    (coalesce(a_roll.team_rolling_point_velocity_5, 0) * coalesce(m.away_rank, 0)) as away_underdog_signal_score
from match_rankings m
left join team_rolling h_roll
    on m.match_id = h_roll.match_id
    and m.home_team = h_roll.team
left join team_rolling a_roll
    on m.match_id = a_roll.match_id
    and m.away_team = a_roll.team
left join ranking_volatility h_vol
    on m.home_team = h_vol.country_full
    and m.home_rank_date = h_vol.rank_date
left join ranking_volatility a_vol
    on m.away_team = a_vol.country_full
    and m.away_rank_date = a_vol.rank_date
