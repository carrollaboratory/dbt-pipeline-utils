-- macros/generate_schema_name.sql
{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}

    {# Always honor explicit schema config first (e.g. +schema in dbt_project.yml). #}
    {%- if custom_schema_name is not none and custom_schema_name | trim != '' -%}
        {{ default_schema | trim }}_{{ custom_schema_name | trim }}
    {%- elif node.resource_type == 'seed' -%}
        {{ default_schema | trim }}
    {%- else -%}
        {# Fallback path-based behavior only when schema is not explicitly configured. #}
        {%- set fqn_parts = node.fqn[1:-1] -%}

        {%- if fqn_parts | length == 1 -%}
            {{ default_schema }}_{{ fqn_parts[0] }}
        {%- elif fqn_parts | length > 1 -%}
            {%- if fqn_parts[0] == 'include' -%}
                {%- set schema_path = (['inc'] + fqn_parts[1:-1]) | join('_') -%}
            {%- else -%}
                {%- set schema_path = fqn_parts[:-1] | join('_') -%}
            {%- endif -%}
            {{ default_schema }}_{{ schema_path }}
        {%- else -%}
            {{ default_schema }}
        {%- endif -%}
    {%- endif -%}

{%- endmacro %}