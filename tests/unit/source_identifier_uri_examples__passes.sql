{%- set base = 'https://identifier.includedcc.org/source/sd-dbaknypgqp/' -%}
{%- set examples = [
    ('1234', base ~ '1234'),
    (' BP-001 ', base ~ 'BP-001'),
    ('a b/c?d#e%f', base ~ 'a%20b%2Fc%3Fd%23e%25f'),
    ('', none)
] -%}

with examples as (
{%- for value, expected in examples %}
    select
        '{{ value }}' as value_to_check,
        {{ source_identifier_uri("'" ~ value ~ "'", 'sd-dbaknypgqp') }} as actual,
        {% if expected is none %}cast(null as {{ dbt.type_string() }}){% else %}'{{ expected }}'{% endif %} as expected
    {% if not loop.last %}union all{% endif %}
{%- endfor %}
)

select *
from examples
where actual is distinct from expected
