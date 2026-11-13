# normalize_descriptors Quickstart

## What This Macro Does

`normalize_descriptors` normalizes descriptor inputs and concatenates them safely.

Default behavior per descriptor entry:
- Trims leading and trailing whitespace
- Collapses repeated internal whitespace to a single space
- Preserves case
- Preserves special characters
- Escapes the selected delimiter when it appears in data
- Converts blank strings to null

## Most Common Usage

Use one or more SQL expressions:

```jinja
{{ normalize_descriptors(descriptor_cols=['id', 'study_code']) }}
```

## Add a Fixed String

Use `descriptor_str` when the descriptor includes a constant value:

```jinja
{{ normalize_descriptors(
    descriptor_cols=['id'],
    descriptor_str='brainpower,v2'
) }}
```

## Fallback Value When a Column Is Missing

Use `coalesce(...)` in `descriptor_cols`:

```jinja
{{ normalize_descriptors(
    descriptor_cols=["coalesce(study_id, 'brainpower,v2')"]
) }}
```

## Override Defaults for a Specific Entry

Pass a dictionary entry with `expr` plus only the options you need:

```jinja
{{ normalize_descriptors(
    descriptor_cols=[
      'id',
      {'expr': 'normalized_hpo_term', 'keep_case': false},
      {'expr': 'file_name', 'escape_delimiter': false}
    ],
    delimiter=';'
) }}
```

## Override Defaults for descriptor_str

Use `descriptor_str_options`:

```jinja
{{ normalize_descriptors(
    descriptor_str='brainpower,v2',
    descriptor_str_options={'escape_delimiter': false}
) }}
```

## Where To See Runnable Examples

- Analysis examples: `analyses/examples/normalize_descriptors_examples.sql`
- Validation test: `tests/examples/normalize_descriptors_examples__passes.sql`

Run the test:

```bash
dbt test --select normalize_descriptors_examples__passes
```

## When Not To Use This Macro

Do not use this macro as a substitute for semantic data cleaning.
- Unicode normalization should happen at import/ingest.
- Domain-specific case conventions (for example ontology code conventions) should be validated upstream.
