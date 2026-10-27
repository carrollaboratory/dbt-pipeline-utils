{%- macro _normalize_descriptor_part(
    expr,
    delimiter=',',
    escape_char='/',
    trim_whitespace=true,
    collapse_whitespace=true,
    keep_case=true,
    null_if_blank=true,
    escape_delimiter=true
) -%}

    {%- if expr is none or expr | trim == '' -%}
        {%- do exceptions.raise_compiler_error("normalize_descriptors requires each descriptor entry to include a non-empty expression") -%}
    {%- endif -%}

    {%- set normalized_expr = "cast(" ~ expr ~ " as text)" -%}

    {%- if trim_whitespace -%}
        {%- set normalized_expr = "trim(" ~ normalized_expr ~ ")" -%}
    {%- endif -%}

    {%- if collapse_whitespace -%}
        {%- set normalized_expr = "regexp_replace(" ~ normalized_expr ~ ", '\\s+', ' ', 'g')" -%}
    {%- endif -%}

    {%- if not keep_case -%}
        {%- set normalized_expr = "lower(" ~ normalized_expr ~ ")" -%}
    {%- endif -%}

    {%- if escape_delimiter and delimiter != '' -%}
        {%- set escaped_delimiter = delimiter | replace("'", "''") -%}
        {%- set escaped_replacement = (escape_char ~ delimiter) | replace("'", "''") -%}
        {%- set normalized_expr = "replace(" ~ normalized_expr ~ ", '" ~ escaped_delimiter ~ "', '" ~ escaped_replacement ~ "')" -%}
    {%- endif -%}

    {%- if null_if_blank -%}
        {%- set normalized_expr = "nullif(" ~ normalized_expr ~ ", '')" -%}
    {%- endif -%}

    {{ return(normalized_expr) }}

{%- endmacro -%}
{%- macro normalize_descriptors(descriptor_cols=[], descriptor_str='', delimiter=',', default_options={}, descriptor_str_options={}) -%}

    {%- set parts = [] -%}
    {%- set default_trim_whitespace = default_options.get('trim_whitespace', true) -%}
    {%- set default_collapse_whitespace = default_options.get('collapse_whitespace', true) -%}
    {%- set default_keep_case = default_options.get('keep_case', true) -%}
    {%- set default_null_if_blank = default_options.get('null_if_blank', true) -%}
    {%- set default_escape_delimiter = default_options.get('escape_delimiter', true) -%}
    {%- set default_escape_char = default_options.get('escape_char', '/') -%}

    {%- if descriptor_cols | length == 0 and descriptor_str | trim == '' -%}
        {%- do exceptions.raise_compiler_error("normalize_descriptors requires at least one descriptor entry or a non-empty descriptor_str") -%}
    {%- endif -%}

    {%- for descriptor_entry in descriptor_cols -%}
        {%- if descriptor_entry is mapping -%}
            {%- set expr = descriptor_entry.get('expr') -%}
            {%- set trim_whitespace = descriptor_entry.get('trim_whitespace', default_trim_whitespace) -%}
            {%- set collapse_whitespace = descriptor_entry.get('collapse_whitespace', default_collapse_whitespace) -%}
            {%- set keep_case = descriptor_entry.get('keep_case', default_keep_case) -%}
            {%- set null_if_blank = descriptor_entry.get('null_if_blank', default_null_if_blank) -%}
            {%- set escape_delimiter = descriptor_entry.get('escape_delimiter', default_escape_delimiter) -%}
            {%- set escape_char = descriptor_entry.get('escape_char', default_escape_char) -%}
        {%- else -%}
            {%- set expr = descriptor_entry -%}
            {%- set trim_whitespace = default_trim_whitespace -%}
            {%- set collapse_whitespace = default_collapse_whitespace -%}
            {%- set keep_case = default_keep_case -%}
            {%- set null_if_blank = default_null_if_blank -%}
            {%- set escape_delimiter = default_escape_delimiter -%}
            {%- set escape_char = default_escape_char -%}
        {%- endif -%}

        {%- do parts.append(_normalize_descriptor_part(
            expr=expr,
            delimiter=delimiter,
            escape_char=escape_char,
            trim_whitespace=trim_whitespace,
            collapse_whitespace=collapse_whitespace,
            keep_case=keep_case,
            null_if_blank=null_if_blank,
            escape_delimiter=escape_delimiter
        )) -%}
    {%- endfor -%}

    {%- if descriptor_str | trim != '' -%}
        {%- set descriptor_str_sql = "'" ~ (descriptor_str | replace("'", "''")) ~ "'" -%}
        {%- do parts.append(_normalize_descriptor_part(
            expr=descriptor_str_sql,
            delimiter=delimiter,
            escape_char=descriptor_str_options.get('escape_char', default_escape_char),
            trim_whitespace=descriptor_str_options.get('trim_whitespace', default_trim_whitespace),
            collapse_whitespace=descriptor_str_options.get('collapse_whitespace', default_collapse_whitespace),
            keep_case=descriptor_str_options.get('keep_case', default_keep_case),
            null_if_blank=descriptor_str_options.get('null_if_blank', default_null_if_blank),
            escape_delimiter=descriptor_str_options.get('escape_delimiter', default_escape_delimiter)
        )) -%}
    {%- endif -%}

    {{ return("concat_ws('" ~ (delimiter | replace("'", "''")) ~ "', " ~ (parts | join(', ')) ~ ")") }}

{%- endmacro -%}