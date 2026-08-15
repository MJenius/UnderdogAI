select *
from {{ ref('stg_match_results') }}
where match_date > current_date
   or home_score < 0
   or away_score < 0
   or home_team = away_team

