{%- macro warn_slow_models() -%}
    {%- if execute and results is defined -%}
        {%- set threshold_seconds = var('model_runtime_warning_seconds', 10) | float -%}
        {%- for result in results -%}
            {%- if result.node.resource_type == 'model' and result.execution_time | float >= threshold_seconds -%}
                {%- set relation_name = result.node.schema ~ '.' ~ result.node.alias -%}
                {{ log(
                    'WARNING: model ' ~ relation_name ~ ' (' ~ result.node.name ~ ')' ~
                    ' took ' ~ ('%.1f' | format(result.execution_time | float)) ~
                    ' seconds, exceeding the ' ~ ('%.1f' | format(threshold_seconds)) ~
                    '-second runtime threshold; status=' ~ result.status,
                    info=True
                ) }}
            {%- endif -%}
        {%- endfor -%}
    {%- endif -%}
    {{- return('') -}}
{%- endmacro -%}
