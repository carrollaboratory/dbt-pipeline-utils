# generate_descriptor_view_sql Quickstart

Use this macro to build a descriptor view from available int descriptor tables.
It returns unique descriptors that are missing from `inc_brainpower_raw.global_ids`
for the same `fhirResourceType` and study.

## Basic Usage

```jinja
{{ config(materialized='table') }}

{{ generate_descriptor_view_sql(
    table_prefix='inc_brainpower_int_',
    study_global_id='brainpower'
) }}
```

## Arguments

- table_prefix: prefix used to resolve descriptor source relations
- study_global_id: value matched to `global_ids.studyId`, and emitted as `studyGlobalId`

## Relation Resolution

The macro attempts each source as:

- `{table_prefix}accesspolicy`
- `{table_prefix}demographics`
- `{table_prefix}family`

If a relation does not exist, it is skipped automatically.

The macro automatically uses descriptor-source int models that exist and are
built; missing sources are skipped.
