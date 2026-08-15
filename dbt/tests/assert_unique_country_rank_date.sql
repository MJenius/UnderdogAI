select country_full, rank_date
from {{ ref('stg_fifa_rankings') }}
group by 1, 2
having count(*) > 1
