select 1
where (select max(date) from {{ source('raw', 'raw_match_results') }})
      < current_date - interval '18 months'

