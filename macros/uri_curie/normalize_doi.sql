{% macro normalize_doi(column_name) %}
    nullif(trim(cast({{ column_name }} as {{ dbt.type_string() }})), '')
{% endmacro %}
