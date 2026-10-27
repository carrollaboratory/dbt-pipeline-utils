
{%- macro generate_source_ref_from_current_model(prefix, strip_prefixes=none) -%}
    {%- if prefix is none or prefix | trim == '' -%}
        {{ exceptions.raise_compiler_error("Argument 'prefix' is required.") }}
    {%- endif -%}

    {%- if strip_prefixes is none -%}
        {%- set strip_prefixes = [
            'kf_access_',
            'inc_access_',
            'kf_common_',
            'inc_common_',
            'combined_common_',
            'access_',
            'combined_',
            'inc_program_',
            'kf_program_'
        ] -%}
    {%- endif -%}

    {%- set ns = namespace(table_name=model.name) -%}
    {%- for strip_prefix in strip_prefixes -%}
        {%- if ns.table_name.startswith(strip_prefix) -%}
            {%- set ns.table_name = ns.table_name.replace(strip_prefix, '', 1) -%}
        {%- endif -%}
    {%- endfor -%}

    {{- return(ref(prefix ~ '_' ~ ns.table_name)) -}}
{%- endmacro -%}