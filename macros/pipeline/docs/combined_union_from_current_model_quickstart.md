# combined_union_from_current_model Quickstart

Use this macro inside a program model to union study-specific STB models.

## Naming Convention

The current model should be named like one of:
- `inc_program_<table_name>`
- `kf_program_<table_name>`
- `combined_<table_name>` (backward compatible)

The macro removes one of those prefixes and looks for `<study>_stb_<table_name>`.

If `studies_var` is omitted, it is inferred from the model prefix:
- `inc_program_` -> `inc_studies`
- `kf_program_` -> `kf_studies`
- otherwise -> `combined_studies`

## Basic Usage

```jinja
{{ config(materialized='table') }}

{{ combined_union_from_current_model() }}
```

## Override Study Var Name

```jinja
{{ combined_union_from_current_model(studies_var='my_studies_var') }}
```

## Dependency

Requires `dbt_utils` because it uses `dbt_utils.union_relations`.
