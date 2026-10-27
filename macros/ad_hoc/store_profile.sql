{% macro store_profile(
    profile_table,
    profile_database=none,
    profile_schema=none,
    profile_include_columns=none,
    profile_exclude_columns=none,
    profile_where_clause=none,
    profile_group_by=none,
    adhoc_database=none,
    adhoc_schema=none,
    adhoc_table=none
) %}

{%- set profile_database = profile_database or target.database -%}
{%- set profile_schema = profile_schema or target.schema -%}
{%- set include_columns = profile_include_columns or [] -%}
{%- set exclude_columns = profile_exclude_columns or [] -%}
{%- set where_clause = profile_where_clause -%}
{%- set group_by = profile_group_by or [] -%}

{%- set output_database = adhoc_database or profile_database -%}
{%- set output_schema = adhoc_schema or profile_schema -%}
{%- set output_table = adhoc_table or ('profile_' ~ profile_table) -%}

{%- if not profile_table -%}
{{ exceptions.raise_compiler_error("Missing required arg: profile_table") }}
{%- endif -%}

{%- if include_columns and exclude_columns -%}
{{ exceptions.raise_compiler_error("Both profile_include_columns and profile_exclude_columns were provided. Only one is allowed.") }}
{%- endif -%}

{% set existing_target_relation = adapter.get_relation(
    database=profile_database,
    schema=profile_schema,
    identifier=profile_table
) %}

{% if existing_target_relation is none %}
  {{ exceptions.raise_compiler_error(
      "Profile target relation not found: " ~ profile_database ~ "." ~ profile_schema ~ "." ~ profile_table
  ) }}
{% endif %}

{% set relation_columns = adapter.get_columns_in_relation(existing_target_relation) %}
{% set selected_columns = [] %}
{% set include_columns_lc = include_columns | map('lower') | list %}
{% set exclude_columns_lc = exclude_columns | map('lower') | list %}

{% for col in relation_columns %}
{% if include_columns %}
{% if col.name | lower in include_columns_lc %}
      {% do selected_columns.append(col) %}
    {% endif %}
  {% elif exclude_columns %}
{% if col.name | lower not in exclude_columns_lc %}
      {% do selected_columns.append(col) %}
    {% endif %}
  {% else %}
{% do selected_columns.append(col) %}
{% endif %}
{% endfor %}

{% if selected_columns | length == 0 %}
  {{ exceptions.raise_compiler_error(
    "No columns selected for profiling in relation " ~ existing_target_relation ~
    ". Check profile_include_columns/profile_exclude_columns values and case sensitivity."
  ) }}
{% endif %}

{% set profile_columns = group_by + ['column_name', 'data_type', 'row_count', 'not_null_proportion', 'distinct_proportion', 'distinct_count', 'is_unique', 'min', 'max', 'avg', 'median', 'std_dev_population', 'std_dev_sample'] %}

{% set profile_sql %}
with source_data as (
    select *
    from {{ existing_target_relation }}
{% if where_clause %}
    where {{ where_clause }}
{% endif %}
),

column_profiles as (
    {% for col in selected_columns %}
{% set col_name = col.name %}
{% set data_type = (col.data_type or '') | lower %}
    {% set is_numeric = (
        'int' in data_type
        or 'number' in data_type
        or 'numeric' in data_type
        or 'decimal' in data_type
        or 'float' in data_type
        or 'double' in data_type
        or 'real' in data_type
    ) %}
    select
{%- for group_col in group_by %}
{{ group_col }},
{%- endfor %}
        lower('{{ col_name }}') as column_name,
        nullif('{{ data_type }}', '') as data_type,
        count(*) as row_count,
        count({{ adapter.quote(col_name) }})::float / nullif(count(*), 0) as not_null_proportion,
        count(distinct {{ adapter.quote(col_name) }})::float / nullif(count(*), 0) as distinct_proportion,
        count(distinct {{ adapter.quote(col_name) }}) as distinct_count,
        (count(*) = count(distinct {{ adapter.quote(col_name) }})) as is_unique,
        min(cast({{ adapter.quote(col_name) }} as varchar)) as min,
        max(cast({{ adapter.quote(col_name) }} as varchar)) as max,
        {% if is_numeric %}
        avg({{ adapter.quote(col_name) }}) as avg,
        percentile_cont(0.5) within group (order by {{ adapter.quote(col_name) }}) as median,
        stddev_pop({{ adapter.quote(col_name) }}) as std_dev_population,
        stddev_samp({{ adapter.quote(col_name) }}) as std_dev_sample,
        {% else %}
        cast(null as double precision) as avg,
        cast(null as double precision) as median,
        cast(null as double precision) as std_dev_population,
        cast(null as double precision) as std_dev_sample,
        {% endif %}
        cast(current_timestamp as varchar) as profiled_at,
        {{ loop.index }} as _column_position
    from source_data
    {% if group_by %}
    group by {{ group_by | join(', ') }}
{% endif %}
{% if not loop.last %}
    union all
    {% endif %}
{% endfor %}
)

select
{%- for group_col in group_by %}
{{ group_col }},
{%- endfor %}
    column_name,
    data_type,
    row_count,
    not_null_proportion,
    distinct_proportion,
    distinct_count,
    is_unique,
    min,
    max,
    avg,
    median,
    std_dev_population,
    std_dev_sample,
    profiled_at
from column_profiles
order by {% if group_by %}{{ group_by | join(', ') }}, {% endif %}_column_position asc
{% endset %}

{% set output_relation = api.Relation.create(
    database=output_database,
    schema=output_schema,
    identifier=output_table
) %}

{% do adapter.create_schema(output_relation) %}

{% set existing_output_relation = adapter.get_relation(
    database=output_database,
    schema=output_schema,
    identifier=output_table
) %}

{% if existing_output_relation is none %}
  {% set create_sql %}
  create table {{ output_relation }} as
  {{ profile_sql }}
  {% endset %}

  {% do run_query(create_sql) %}
{% else %}
{% set staged_profile_sql %}
  with current_profile as (
    {{ profile_sql }}
  ),
  latest_profile as (
    select *
    from (
      select
        *,
        row_number() over (
          partition by {% if group_by %}{{ group_by | join(', ') }}, {% endif %}column_name
          order by profiled_at desc
        ) as rn
      from {{ existing_output_relation }}
    ) existing_rows
    where rn = 1
  )
  select
    current_profile.*
  from current_profile
  left join latest_profile
    on {% if group_by %}
{% for group_col in group_by %}
      current_profile.{{ group_col }} is not distinct from latest_profile.{{ group_col }} and
      {% endfor %}
    {% endif %}
      current_profile.column_name = latest_profile.column_name
  where latest_profile.column_name is null
     or current_profile.data_type is distinct from latest_profile.data_type
     or current_profile.row_count is distinct from latest_profile.row_count
     or current_profile.not_null_proportion is distinct from latest_profile.not_null_proportion
     or current_profile.distinct_proportion is distinct from latest_profile.distinct_proportion
     or current_profile.distinct_count is distinct from latest_profile.distinct_count
     or current_profile.is_unique is distinct from latest_profile.is_unique
     or current_profile.min is distinct from latest_profile.min
     or current_profile.max is distinct from latest_profile.max
     or current_profile.avg is distinct from latest_profile.avg
     or current_profile.median is distinct from latest_profile.median
     or current_profile.std_dev_population is distinct from latest_profile.std_dev_population
     or current_profile.std_dev_sample is distinct from latest_profile.std_dev_sample
  {% endset %}

  {% set insert_sql %}
  insert into {{ output_relation }}
  select *
  from (
    {{ staged_profile_sql }}
  ) incremental_profile
  {% endset %}

  {% do run_query(insert_sql) %}
{% endif %}

{{ log("Created profile table: " ~ output_relation, info=True) }}
{{ return(output_relation) }}

{% endmacro %}


{% macro get_profile(args={}) %}

{%- if args is none -%}
{%- set args = {} -%}
{%- endif -%}

{{ return(store_profile(
    profile_table=args.get('profile_table'),
    profile_database=args.get('profile_database'),
    profile_schema=args.get('profile_schema'),
    profile_include_columns=args.get('profile_include_columns'),
    profile_exclude_columns=args.get('profile_exclude_columns'),
    profile_where_clause=args.get('profile_where_clause'),
    profile_group_by=args.get('profile_group_by'),
    adhoc_database=args.get('adhoc_database'),
    adhoc_schema=args.get('adhoc_schema'),
    adhoc_table=args.get('adhoc_table')
)) }}

{% endmacro %}


{% macro run_get_profile(args={}) %}

{%- if args is none -%}
  {%- set args = {} -%}
{%- endif -%}

{{ return(store_profile(
    profile_table=args.get('profile_table'),
    profile_database=args.get('profile_database'),
    profile_schema=args.get('profile_schema'),
    profile_include_columns=args.get('profile_include_columns'),
    profile_exclude_columns=args.get('profile_exclude_columns'),
    profile_where_clause=args.get('profile_where_clause'),
    profile_group_by=args.get('profile_group_by'),
    adhoc_database=args.get('adhoc_database'),
    adhoc_schema=args.get('adhoc_schema'),
    adhoc_table=args.get('adhoc_table')
)) }}

{% endmacro %}