# generate_schema_name Quickstart

This is a dbt override macro used automatically by dbt when deciding schemas.

## Do I Call It Directly?

No. dbt calls it during compile/run.

## Behavior Summary

- Seeds:
  - default: <target_schema>
  - with custom schema: <target_schema>_<custom_schema>
- Models:
  - root-level folder: <target_schema>_<first_folder>
  - deeper folder structure: <target_schema>_<folder_path_except_last_segment>

## Example

A model under `models/include/brainpower/src/...` resolves to schema like:
- <target_schema>_include_brainpower

This behavior is why development schemas often include folder-based suffixes.
