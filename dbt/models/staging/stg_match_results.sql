select
    cast(date as date) as match_date,
    trim(home_team) as home_team,
    trim(away_team) as away_team,
    cast(home_score as integer) as home_score,
    cast(away_score as integer) as away_score,
    cast(tournament as varchar(150)) as tournament,
    cast(city as varchar(100)) as city,
    cast(country as varchar(100)) as country,
    cast(neutral as boolean) as neutral,
    md5(concat(cast(date as varchar), trim(home_team), trim(away_team), cast(home_score as varchar), cast(away_score as varchar), coalesce(trim(city), ''))) as match_id
from {{ source('raw', 'raw_match_results') }}
where date is not null
  and home_team is not null
  and trim(home_team) != ''
  and away_team is not null
  and trim(away_team) != ''
  and home_score is not null
  and away_score is not null
