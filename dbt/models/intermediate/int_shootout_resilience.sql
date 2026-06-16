with shootout_data as (
    select * from {{ ref('stg_shootouts') }}
),
team_shootout_records as (
    select
        home_team as team,
        match_date,
        case when winner = home_team then 1 else 0 end as is_win,
        case when first_shooter = home_team then 1 else 0 end as is_first_shooter,
        case when first_shooter = home_team and winner = home_team then 1 else 0 end as first_shooter_win
    from shootout_data
    union all
    select
        away_team as team,
        match_date,
        case when winner = away_team then 1 else 0 end as is_win,
        case when first_shooter = away_team then 1 else 0 end as is_first_shooter,
        case when first_shooter = away_team and winner = away_team then 1 else 0 end as first_shooter_win
    from shootout_data
)
select
    team,
    count(*) as total_shootouts,
    sum(is_win) as shootout_wins,
    case when count(*) > 0
        then cast(sum(is_win) as numeric) / count(*)
        else 0.5
    end as shootout_win_rate,
    sum(is_first_shooter) as times_first_shooter,
    case when sum(is_first_shooter) > 0
        then cast(sum(first_shooter_win) as numeric) / sum(is_first_shooter)
        else 0.5
    end as first_shooter_advantage_rate,
    max(match_date) as latest_shootout_date
from team_shootout_records
group by team
