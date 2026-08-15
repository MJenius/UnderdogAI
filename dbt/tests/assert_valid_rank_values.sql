select *
from {{ ref('stg_fifa_rankings') }}
where rank < 1
   or total_points < 0
   or rank_date > current_date

