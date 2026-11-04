{% macro source_identifier_uri(column_name, study_id) %}
    {%- set segments = ['https://identifier.includedcc.org/source', study_id] -%}
    {%- set ns = namespace(sql="nullif(trim(cast(" ~ column_name ~ " as " ~ dbt.type_string() ~ ")), '')") -%}
    {%- for char, code in [('%', '%25'), (' ', '%20'), ('/', '%2F'), ('?', '%3F'), ('#', '%23')] -%}
        {%- set ns.sql = "replace(" ~ ns.sql ~ ", '" ~ char ~ "', '" ~ code ~ "')" -%}
    {%- endfor -%}
    '{{ segments | join('/') }}/' || {{ ns.sql }}
{% endmacro %}
