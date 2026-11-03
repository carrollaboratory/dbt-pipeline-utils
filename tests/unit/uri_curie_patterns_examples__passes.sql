{%- set patterns = uri_curie_patterns() -%}
{%- set examples = [
    ('https://www.example.org', 'http_uri', true),
    ('https://kidsfirstdrc.org/studies/sd-1nns3k8v?tab=data#top', 'http_uri', true),
    ('http://sub.example.co.uk:8080/a%20b', 'http_uri', true),
    ('HTTPS://example.org', 'http_uri', false),
    ('https://', 'http_uri', false),
    ('https:///path', 'http_uri', false),
    ('ftp://example.org', 'http_uri', false),
    ('www.example.org', 'http_uri', false),
    ('https://example.org/a b', 'http_uri', false),
    (' https://example.org', 'http_uri', false),

    ('10.5072/example.11111', 'doi', true),
    ('10.1234/abc.def-123', 'doi', true),
    ('10.123/abc', 'doi', false),
    ('10.1234567890/abc', 'doi', false),
    ('10.1234/', 'doi', false),
    ('10.1234/a b', 'doi', false),
    ('doi:10.1234/abc', 'doi', false),

    ('https://www.ncbi.nlm.nih.gov/gap/?term=phs001', 'uri', true),
    ('ftp://ftp.ncbi.nlm.nih.gov/pub', 'uri', true),
    ('http://purl.obolibrary.org/obo/HP_0000118', 'uri', true),
    ('urn:uuid:123e4567-e89b-12d3-a456-426614174000', 'uri', true),
    ('dbgap:phs001', 'uri', false),
    ('HTTP://example.org', 'uri', false),
    ('https://', 'uri', false),
    ('file:///tmp/x', 'uri', false),
    ('', 'uri', false),

    ('dbgap:phs001138.v1.p1', 'curie', true),
    ('HP:0000118', 'curie', true),
    ('hp:0000118', 'curie', true),
    ('NCIT:C12345', 'curie', true),
    ('ncit:C12345', 'curie', true),
    ('obo:GO_0008150', 'curie', true),
    ('_x:abc', 'curie', true),
    ('duo:0000042#x', 'curie', true),
    ('dbgap:', 'curie', false),
    (':phs001', 'curie', false),
    ('1abc:phs001', 'curie', false),
    ('db gap:phs001', 'curie', false),
    ('dbgap:phs 001', 'curie', false),
    ('dbgap:/phs001', 'curie', false),
    ('https://example.org', 'curie', false),
    ('phs001', 'curie', false),

    ('dbgap', 'curie_prefix', true),
    ('NCIT', 'curie_prefix', true),
    ('ncit', 'curie_prefix', true),
    ('obo.go-x_1', 'curie_prefix', true),
    ('1abc', 'curie_prefix', false),
    ('db:gap', 'curie_prefix', false),
    ('', 'curie_prefix', false)
] -%}

with examples as (
{%- for value, pattern_name, expected in examples %}
    select
        '{{ pattern_name }}' as pattern_name,
        '{{ value }}' as value_to_check,
        coalesce({{ regex_match("'" ~ value ~ "'", patterns[pattern_name]) }}, false) as actual,
        {{ expected }} as expected
    {% if not loop.last %}union all{% endif %}
{%- endfor %}
)

select *
from examples
where actual <> expected
