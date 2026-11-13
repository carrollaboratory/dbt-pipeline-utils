{#-
  Profiling query group. Each macro returns a SELECT statement (it does not
  run anything), so call it from an analysis file, `dbt compile --inline` or
  `dbt show --inline`. Requires dbt_utils.
  Usage and how to read results: macros/profiling/docs/profiling_quickstart.md
-#}

{#- Columns of `relation` to profile: all columns, optionally limited by include / except (case-insensitive). -#}
{%- macro _profiling_columns(relation, include=none, except=none) -%}
  {%- set cols = dbt_utils.get_filtered_columns_in_relation(relation, except or []) -%}
  {%- if include -%}
    {%- set include_lc = include | map('lower') | list -%}
    {%- set kept = [] -%}
    {%- for c in cols if c | lower in include_lc -%}
      {%- do kept.append(c) -%}
    {%- endfor -%}
    {%- set cols = kept -%}
  {%- endif -%}
  {%- if execute and cols | length == 0 -%}
    {{ exceptions.raise_compiler_error("No columns selected from " ~ relation ~ ". Check include/except.") }}
  {%- endif -%}
  {{ return(cols) }}
{%- endmacro -%}

{%- macro _profiling_value(col, blank_as_null=false) -%}
  {%- if blank_as_null -%}
nullif(trim(cast({{ adapter.quote(col) }} as varchar)), '')
  {%- else -%}
{{ adapter.quote(col) }}
  {%- endif -%}
{%- endmacro -%}

{%- macro _profiling_list(value) -%}
  {{ return([] if value is none else ([value] if value is string else value)) }}
{%- endmacro -%}


{#-
  Which groups (e.g. datasets) populate which columns.
  measure: 'any' (1/0), 'count' (non-null rows) or 'proportion' (non-null share).
-#}
{%- macro profile_column_presence(relation, group_by='ingest_provenance', include=none, except=none, measure='any', blank_as_null=false) -%}
  {%- set group_cols = _profiling_list(group_by) -%}
  {%- set cols = _profiling_columns(relation, include, (except or []) + group_cols) -%}
  {%- if measure not in ['any', 'count', 'proportion'] -%}
    {{ exceptions.raise_compiler_error("measure must be 'any', 'count' or 'proportion'") }}
  {%- endif -%}
select
  {%- for g in group_cols %}
  {{ adapter.quote(g) }},
  {%- endfor %}
  count(*) as n_rows
  {%- for c in cols %},
  {%- set v = _profiling_value(c, blank_as_null) %}
  {%- if measure == 'any' %}
  max(case when {{ v }} is not null then 1 else 0 end) as {{ adapter.quote(c) }}
  {%- elif measure == 'count' %}
  count({{ v }}) as {{ adapter.quote(c) }}
  {%- else %}
  round(count({{ v }}) / count(*), 3) as {{ adapter.quote(c) }}
  {%- endif %}
  {%- endfor %}
from {{ relation }}
{%- if group_cols %}
group by all
order by all
{%- endif %}
{%- endmacro -%}


{#- Distinct non-null values per column, overall or per group. -#}
{%- macro profile_distinct_counts(relation, group_by=none, include=none, except=none, blank_as_null=false) -%}
  {%- set group_cols = _profiling_list(group_by) -%}
  {%- set cols = _profiling_columns(relation, include, (except or []) + group_cols) -%}
select
  {%- for g in group_cols %}
  {{ adapter.quote(g) }},
  {%- endfor %}
  count(*) as n_rows
  {%- for c in cols %},
  count(distinct {{ _profiling_value(c, blank_as_null) }}) as {{ adapter.quote(c) }}
  {%- endfor %}
from {{ relation }}
{%- if group_cols %}
group by all
order by all
{%- endif %}
{%- endmacro -%}


{#-
  Cardinality between every pair of `columns`: 1:1, 1:N, N:1 or N:N.
  Nulls count as a value, so "null" maps like any other value.
-#}
{%- macro profile_column_relationships(relation, columns=none, group_by=none, except=none) -%}
  {%- set group_cols = _profiling_list(group_by) -%}
  {%- set cols = _profiling_columns(relation, columns, (except or []) + group_cols) -%}
with counts as (
  select
    {%- for g in group_cols %}
    {{ adapter.quote(g) }},
    {%- endfor %}
    count(*) as n_rows
    {%- for c in cols %},
    count(distinct {{ dbt_utils.generate_surrogate_key([adapter.quote(c)]) }}) as n_{{ loop.index }}
    {%- endfor %}
    {%- for a in cols %}{%- set i = loop.index %}
    {%- for b in cols %}{%- if loop.index > i %},
    count(distinct {{ dbt_utils.generate_surrogate_key([adapter.quote(a), adapter.quote(b)]) }}) as n_{{ i }}_{{ loop.index }}
    {%- endif %}{%- endfor %}
    {%- endfor %}
  from {{ relation }}
  {%- if group_cols %}
  group by all
  {%- endif %}
),
pairs as (
  {%- set ns = namespace(first=true) %}
  {%- for a in cols %}{%- set i = loop.index %}
  {%- for b in cols %}{%- set j = loop.index %}{%- if j > i %}
  {%- if not ns.first %}
  union all
  {%- endif %}{%- set ns.first = false %}
  select
    {%- for g in group_cols %}
    {{ adapter.quote(g) }},
    {%- endfor %}
    n_rows,
    '{{ a }}' as column_a,
    '{{ b }}' as column_b,
    n_{{ i }} as distinct_a,
    n_{{ j }} as distinct_b,
    n_{{ i }}_{{ j }} as distinct_pairs
  from counts
  {%- endif %}{%- endfor %}
  {%- endfor %}
)
select
  *,
  case
    when distinct_pairs = distinct_a and distinct_pairs = distinct_b then '1:1'
    when distinct_pairs = distinct_a then 'N:1'
    when distinct_pairs = distinct_b then '1:N'
    else 'N:N'
  end as relationship,
  case
    when distinct_a = 1 or distinct_b = 1 then 'one column is constant'
    when distinct_a = n_rows and distinct_b = n_rows then 'both columns unique per row'
  end as note
from pairs
order by all
{%- endmacro -%}


{#-
  Drill-down for one pair: the values of column_a that map to more than one
  column_b value, and vice versa. Empty result = 1:1.
-#}
{%- macro profile_column_pair(relation, column_a, column_b, group_by=none, max_examples=10) -%}
  {%- set group_cols = _profiling_list(group_by) -%}
  {%- set a = adapter.quote(column_a) -%}
  {%- set b = adapter.quote(column_b) -%}
with pairs as (
  select distinct
    {%- for g in group_cols %}
    {{ adapter.quote(g) }},
    {%- endfor %}
    cast({{ a }} as varchar) as value_a,
    cast({{ b }} as varchar) as value_b
  from {{ relation }}
)
{%- for side in [('a', 'b', column_a, column_b), ('b', 'a', column_b, column_a)] %}
select
  {%- for g in group_cols %}
  {{ adapter.quote(g) }},
  {%- endfor %}
  '{{ side[2] }} -> {{ side[3] }}' as direction,
  value_{{ side[0] }} as value,
  count(*) as n_other_values,
  list(value_{{ side[1] }} order by value_{{ side[1] }})[1:{{ max_examples }}] as other_values
from pairs
group by all
having count(*) > 1
{%- if not loop.last %}
union all
{%- endif %}
{%- endfor %}
order by direction, n_other_values desc, value
{%- endmacro -%}


{#-
  Will `left join right on left_columns = right_columns` drop or duplicate rows?
  One row per check (or per group). See the profiling quickstart for the columns.
-#}
{%- macro profile_join_coverage(left_relation, right_relation, left_columns, right_columns=none, left_where=none, right_where=none, group_by=none, label=none) -%}
  {%- set left_cols = _profiling_list(left_columns) -%}
  {%- set right_cols = _profiling_list(right_columns) or left_cols -%}
  {%- set group_cols = _profiling_list(group_by) -%}
  {%- if left_cols | length != right_cols | length -%}
    {{ exceptions.raise_compiler_error("left_columns and right_columns must have the same length") }}
  {%- endif -%}
  {%- for g in group_cols if g not in left_cols -%}
    {{ exceptions.raise_compiler_error("group_by column '" ~ g ~ "' must be one of left_columns") }}
  {%- endfor -%}
select * from (
with l as (
  select
    {%- for c in left_cols %}
    {{ adapter.quote(c) }} as k_{{ loop.index }},
    {%- endfor %}
    count(*) as n_left
  from {{ left_relation }}
  {%- if left_where %}
  where {{ left_where }}
  {%- endif %}
  group by all
),
r as (
  select
    {%- for c in right_cols %}
    {{ adapter.quote(c) }} as k_{{ loop.index }},
    {%- endfor %}
    count(*) as n_right
  from {{ right_relation }}
  {%- if right_where %}
  where {{ right_where }}
  {%- endif %}
  group by all
),
keys as (
  select
    {%- for g in group_cols %}
    {%- set gi = left_cols.index(g) + 1 %}
    cast(coalesce(l.k_{{ gi }}, r.k_{{ gi }}) as varchar) as {{ adapter.quote(g) }},
    {%- endfor %}
    l.n_left,
    r.n_right,
    {%- for c in left_cols %}
    {{ 'l.k_' ~ loop.index }} is null{{ ' or' if not loop.last }}
    {%- endfor %} as left_key_has_null
  from l
  full outer join r
    on {% for c in left_cols -%}
    l.k_{{ loop.index }} = r.k_{{ loop.index }}{{ ' and ' if not loop.last }}
    {%- endfor %}
)
select
  {%- if label %}
  '{{ label }}' as check_name,
  {%- endif %}
  {%- for g in group_cols %}
  {{ adapter.quote(g) }},
  {%- endfor %}
  coalesce(sum(n_left), 0) as left_rows,
  count(n_left) as left_keys,
  count(n_left) filter (where n_right is not null) as left_keys_matched,
  coalesce(sum(n_left) filter (where n_right is null), 0) as left_rows_unmatched,
  coalesce(sum(n_left) filter (where n_right is null and left_key_has_null), 0) as left_rows_null_key,
  count(n_right) as right_keys,
  count(n_right) filter (where n_left is null) as right_keys_unmatched,
  max(n_left) as max_left_rows_per_key,
  coalesce(max(n_right) filter (where n_left is not null), 0) as max_right_rows_per_key,
  coalesce(sum(n_left * coalesce(n_right, 1)) filter (where n_left is not null), 0) as rows_after_left_join,
  coalesce(sum(n_left * coalesce(n_right, 1)) filter (where n_left is not null), 0)
    - coalesce(sum(n_left), 0) as rows_added_by_join
from keys
{%- if group_cols %}
group by all
order by all
{%- endif %}
)
{%- endmacro -%}
