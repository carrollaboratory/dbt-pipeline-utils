{#-
  Schema naming from a model's folder path, for a pipeline's generate_schema_name.
  Packages can't override generate_schema_name, so the pipeline keeps a
  one-line wrapper:
    {% macro generate_schema_name(custom_schema_name, node) -%}
      {{ return(dbt_pipeline_utils.schema_name_from_path(custom_schema_name, node)) }}
    {%- endmacro %}

  - explicit +schema config wins: <target.schema>_<custom_schema_name>
  - seeds: <target.schema>
  - models/<a>/x.sql: <target.schema>_<a>
  - models/<a>/<b>/.../<layer>/x.sql: <target.schema>_<a>_<b>... (last folder dropped)
  path_aliases renames the top folder, e.g. {'include': 'inc'}.
-#}
{%- macro schema_name_from_path(custom_schema_name, node, path_aliases={}) -%}
    {%- set default_schema = target.schema | trim -%}
    {%- if custom_schema_name is not none and custom_schema_name | trim != '' -%}
        {{ return(default_schema ~ '_' ~ (custom_schema_name | trim)) }}
    {%- endif -%}
    {%- if node.resource_type == 'seed' -%}
        {{ return(default_schema) }}
    {%- endif -%}

    {%- set folders = node.fqn[1:-1] -%}
    {%- if folders | length == 0 -%}
        {{ return(default_schema) }}
    {%- endif -%}
    {%- set parts = folders if folders | length == 1 else folders[:-1] -%}
    {%- set parts = [path_aliases.get(parts[0], parts[0])] + parts[1:] -%}
    {{ return(default_schema ~ '_' ~ (parts | join('_'))) }}
{%- endmacro -%}
