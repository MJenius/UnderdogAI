select *
from {{ ref('int_match_historical_rankings') }}
where home_rank_date > match_date
   or away_rank_date > match_date

