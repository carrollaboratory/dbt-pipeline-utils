{%- macro generate_alias_name(custom_alias_name=none, node=none) -%}
    {%- if custom_alias_name is not none -%}
        {{- custom_alias_name -}}
    {%- elif node is not none and node.original_file_path.startswith('models/cdm/') -%}
        {%- set prefixes = [
            'combined_common_',
            'inc_common_',
            'kf_common_',
            'inc_access_',
            'kf_access_'
        ] -%}
        {%- set ns = namespace(alias=node.name) -%}
        {%- for prefix in prefixes -%}
            {%- if ns.alias.startswith(prefix) -%}
                {%- set ns.alias = ns.alias[prefix | length:] -%}
            {%- endif -%}
        {%- endfor -%}
        {{- ns.alias -}}
    {%- else -%}
        {{- node.name -}}
    {%- endif -%}
{%- endmacro -%}
