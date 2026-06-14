select
    cast(id as integer) as ranking_id,
    cast(rank as integer) as rank,
    trim(country_full) as country_full,
    trim(country_abrv) as country_abrv,
    cast(total_points as numeric) as total_points,
    cast(previous_points as numeric) as previous_points,
    cast(rank_change as integer) as rank_change,
    trim(confederation) as confederation,
    cast(rank_date as date) as rank_date
from {{ source('raw', 'raw_fifa_rankings') }}
where rank_date is not null
  and country_full is not null
  and trim(country_full) != ''
  and rank is not null
