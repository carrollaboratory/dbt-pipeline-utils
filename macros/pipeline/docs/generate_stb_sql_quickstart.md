# generate_stb_sql Quickstart

Use this macro to join descriptor-based source rows to global IDs (GIDs).

## Required Input

- base_source: model name or relation for base rows

## Optional Input

- gid_lookup: model name or relation for GID table
- descriptor_sources: list of resource names to include

## Basic Usage

```jinja
{{ generate_stb_sql(
    gid_lookup='inc_brainpower_int_global_ids',
    base_source='inc_brainpower_int_accesspolicy',
    descriptor_sources=[
      'AccessPolicy',
      'Patient'
    ]
) }}
```

## Supported Resource Keys

- AccessPolicy
- ActivityDefinition
- Patient

Only supported keys are used to build joins.

## Output Shape

Returns base columns plus mapped `<resource>_id` columns from the lookup.
