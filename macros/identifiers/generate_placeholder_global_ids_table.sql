{%- macro generate_placeholder_global_ids_table(schema_name='', table_name='global_ids') -%}

    {%- if schema_name | trim == '' -%}
        {{ exceptions.raise_compiler_error("generate_placeholder_global_ids_table requires schema_name") }}
    {%- endif -%}

    {%- if table_name | trim == '' -%}
        {{ exceptions.raise_compiler_error("generate_placeholder_global_ids_table requires table_name") }}
    {%- endif -%}

    {%- set schema_quoted = adapter.quote(schema_name) -%}
    {%- set table_quoted = adapter.quote(table_name) -%}
    {%- set create_schema_sql -%}
        create schema if not exists {{ schema_quoted }}
    {%- endset -%}

    {%- set drop_table_sql -%}
        drop table if exists {{ schema_quoted }}.{{ table_quoted }}
    {%- endset -%}

    {%- set create_table_sql -%}
        create table {{ schema_quoted }}.{{ table_quoted }} as
select
    cast(null as varchar) as "globalId",
    cast(null as varchar) as "studyGlobalId",
    cast(null as varchar) as "studyId",
    cast(null as varchar) as "studyName",
    cast(null as varchar) as "fhirResourceType",
    cast(null as varchar) as "descriptor",
    cast(null as varchar) as "descriptorState",
    cast(null as timestamp) as "globalIdCreatedAt",
    cast(null as varchar) as "globalIdCreatedBy",
    cast(null as timestamp) as "descriptorCreatedAt",
    cast(null as varchar) as "descriptorCreatedBy"
where 1 = 0
    {%- endset -%}

    {% do run_query(create_schema_sql) %}
    {% do run_query(drop_table_sql) %}
    {% do run_query(create_table_sql) %}

    {{ log("Created empty placeholder table " ~ schema_name ~ "." ~ table_name, info=True) }}

{%- endmacro -%}
