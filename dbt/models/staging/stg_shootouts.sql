select
    cast(date as date) as match_date,
    trim(home_team) as home_team,
    trim(away_team) as away_team,
    trim(winner) as winner,
    trim(first_shooter) as first_shooter,
    md5(concat(cast(date as varchar), trim(home_team), trim(away_team))) as shootout_match_key
from {{ source('raw', 'raw_shootouts') }}
where date is not null
  and home_team is not null
  and trim(home_team) != ''
  and away_team is not null
  and trim(away_team) != ''
  and winner is not null
  and trim(winner) != ''
