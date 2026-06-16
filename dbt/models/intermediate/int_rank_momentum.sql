with rankings as (
    select * from {{ ref('stg_fifa_rankings') }}
),
point_ema as (
    select
        country_full,
        rank_date,
        total_points,
        rank,
        rank_change,
        avg(total_points) over (
            partition by country_full
            order by rank_date
            rows between 2 preceding and current row
        ) as ema_3m,
        avg(total_points) over (
            partition by country_full
            order by rank_date
            rows between 11 preceding and current row
        ) as ema_12m,
        stddev(rank_change) over (
            partition by country_full
            order by rank_date
            rows between 11 preceding and current row
        ) as rank_change_volatility
    from rankings
)
select
    country_full,
    rank_date,
    total_points,
    rank,
    rank_change,
    ema_3m,
    ema_12m,
    coalesce(ema_3m - ema_12m, 0) as momentum_score,
    coalesce(rank_change_volatility, 0) as rank_change_volatility
from point_ema
