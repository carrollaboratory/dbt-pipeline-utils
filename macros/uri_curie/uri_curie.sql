{% macro regex_match(expression, pattern) %}
    {{ return(adapter.dispatch('regex_match', 'dbt_pipeline_utils')(expression, pattern)) }}
{% endmacro %}

{% macro default__regex_match(expression, pattern) %}
    (cast({{ expression }} as {{ dbt.type_string() }}) ~ '{{ pattern | replace("'", "''") }}')
{% endmacro %}

{% macro duckdb__regex_match(expression, pattern) %}
    regexp_matches(cast({{ expression }} as {{ dbt.type_string() }}), '{{ pattern | replace("'", "''") }}')
{% endmacro %}

{% macro uri_curie_patterns() %}
    {%- set prefix = "[A-Za-z_][A-Za-z0-9_.-]*" -%}

    {{ return({
        'uri': '^([a-z][a-z0-9+.-]*://[^\\s/][^\\s]*|urn:[^\\s]+)$',
        'http_uri': '^https?://[^\\s/$.?#][^\\s]*$',
        'doi': '^10[.][0-9]{4,9}/[^\\s]+$',
        'curie': '^' ~ prefix ~ ':[^\\s/][^\\s]*$',
        'curie_prefix': '^' ~ prefix ~ '$'
    }) }}
{% endmacro %}

{% macro normalize_curie(column_name, default_prefix=none, local_id_pattern=none, prefix_seed='curie_prefixes', prefix_column='prefix', alias_column='alias_prefix') %}
    {#- Accepts phs123456 and phs123456.v1.p1. -#}
    {%- set dbgap_pattern = '^phs[0-9]{6}([.]v[0-9]+[.]p[0-9]+)?$' -%}
    {%- set builtin_patterns = {
        'dbgap': dbgap_pattern
    } -%}
    {%- if default_prefix and not local_id_pattern -%}
        {%- set local_id_pattern = builtin_patterns.get(default_prefix | lower) -%}
    {%- endif -%}
    {%- if default_prefix and not local_id_pattern -%}
        {{ exceptions.raise_compiler_error("normalize_curie: unknown default_prefix '" ~ default_prefix ~ "'; provide local_id_pattern for custom prefixes.") }}
    {%- endif -%}
    {%- set value = "nullif(trim(cast(" ~ column_name ~ " as " ~ dbt.type_string() ~ ")), '')" -%}
    {%- set has_prefix = value ~ " like '%:%'" -%}
    {%- if default_prefix -%}
        {%- set src_prefix = "case when " ~ has_prefix ~ " then trim(split_part(" ~ value ~ ", ':', 1)) else '" ~ default_prefix ~ "' end" -%}
        {%- set local_id = "case when " ~ has_prefix ~ " then trim(substr(" ~ value ~ ", strpos(" ~ value ~ ", ':') + 1)) else " ~ value ~ " end" -%}
    {%- else -%}
        {%- set src_prefix = "trim(split_part(" ~ value ~ ", ':', 1))" -%}
        {%- set local_id = "trim(substr(" ~ value ~ ", strpos(" ~ value ~ ", ':') + 1))" -%}
    {%- endif -%}
    case
        when {{ value }} is null then null
        when {{ value }} like '%://%' or lower({{ value }}) like 'urn:%' then {{ value }}
{%- if default_prefix %}
        when not ({{ has_prefix }}) and not {{ dbt_pipeline_utils.regex_match(value, local_id_pattern) }} then {{ value }}
        {%- else %}
        when not ({{ has_prefix }}) then {{ value }}
{%- endif %}
        else coalesce(
            (
                select max(p.{{ prefix_column }})
                from {{ ref(prefix_seed) }} as p
                where lower(p.{{ prefix_column }}) = lower({{ src_prefix }})
                   or lower(p.{{ alias_column }}) = lower({{ src_prefix }})
            ),
            {{ src_prefix }}
        ) || ':' || {{ local_id }}
    end
{% endmacro %}

{% macro normalize_http_uri(column_name, default_scheme='https') %}
    {%- set value = "nullif(trim(cast(" ~ column_name ~ " as " ~ dbt.type_string() ~ ")), '')" -%}
    case
        when {{ value }} is null then null
        when lower({{ value }}) like 'http://%' or lower({{ value }}) like 'https://%'
            then lower(split_part({{ value }}, ':', 1)) || substr({{ value }}, strpos({{ value }}, ':'))
        when {{ dbt_pipeline_utils.regex_match(value, '^([A-Za-z0-9-]+[.])+[A-Za-z]{2,}([/?#][^\\s]*)?$') }}
            then '{{ default_scheme }}://' || {{ value }}
        else {{ value }}
    end
{% endmacro %}

{% test valid_uri_format(model, column_name) %}

select {{ column_name }} as value_to_check
from {{ model }}
where {{ column_name }} is not null
  and not {{ dbt_pipeline_utils.regex_match(column_name, dbt_pipeline_utils.uri_curie_patterns()['uri']) }}

{% endtest %}

{% test valid_http_uri(model, column_name) %}

select {{ column_name }} as value_to_check
from {{ model }}
where {{ column_name }} is not null
  and not {{ dbt_pipeline_utils.regex_match(column_name, dbt_pipeline_utils.uri_curie_patterns()['http_uri']) }}

{% endtest %}

{% test valid_doi_format(model, column_name) %}

select {{ column_name }} as value_to_check
from {{ model }}
where {{ column_name }} is not null
  and not {{ dbt_pipeline_utils.regex_match(column_name, dbt_pipeline_utils.uri_curie_patterns()['doi']) }}

{% endtest %}

{% test curie_format(model, column_name) %}

select {{ column_name }} as value_to_check
from {{ model }}
where {{ column_name }} is not null
  and not {{ dbt_pipeline_utils.regex_match(column_name, dbt_pipeline_utils.uri_curie_patterns()['curie']) }}

{% endtest %}

{% test uri_or_curie_format(model, column_name) %}

    {%- set patterns = dbt_pipeline_utils.uri_curie_patterns() %}

select {{ column_name }} as value_to_check
from {{ model }}
where {{ column_name }} is not null
  and not {{ dbt_pipeline_utils.regex_match(column_name, patterns['uri']) }}
  and not {{ dbt_pipeline_utils.regex_match(column_name, patterns['curie']) }}

{% endtest %}

{#- Pair with valid_curie_prefix; enum text has no colon so that test skips it. -#}
{% test accepted_values_or_uri_or_curie(model, column_name, values) %}

    {%- set patterns = dbt_pipeline_utils.uri_curie_patterns() %}

select {{ column_name }} as value_to_check
from {{ model }}
where {{ column_name }} is not null
  and cast({{ column_name }} as {{ dbt.type_string() }}) not in (
    {%- for value in values %}
    '{{ value | replace("'", "''") }}'{% if not loop.last %},{% endif %}
    {%- endfor %}
  )
  and not {{ dbt_pipeline_utils.regex_match(column_name, patterns['uri']) }}
  and not {{ dbt_pipeline_utils.regex_match(column_name, patterns['curie']) }}

{% endtest %}

{#- Only checks values that parse as CURIEs (not full URIs); format is enforced by uri_or_curie_format. -#}
{% test valid_curie_prefix(model, column_name, prefix_seed='curie_prefixes', prefix_column='prefix') %}

{%- set patterns = dbt_pipeline_utils.uri_curie_patterns() %}

with curies as (

    select
        {{ column_name }} as value_to_check,
        split_part(cast({{ column_name }} as {{ dbt.type_string() }}), ':', 1) as curie_prefix
    from {{ model }}
    where {{ column_name }} is not null
      and not {{ dbt_pipeline_utils.regex_match(column_name, patterns['uri']) }}
      and {{ dbt_pipeline_utils.regex_match(column_name, patterns['curie']) }}

)

select curies.*
from curies
where not exists (
    select 1
    from {{ ref(prefix_seed) }} as prefixes
    where prefixes.{{ prefix_column }} = curies.curie_prefix
)

{% endtest %}
