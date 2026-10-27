# combined_stb_relations Quickstart

Use this macro to build a list of study-specific STB relations for one table.

## When To Use

Use in combined models where each study has a model like:
- <study>_stb_<table_name>

## Basic Usage

```jinja
{% set rels = combined_stb_relations(table_name='patient') %}
```

The study list comes from var `combined_studies` by default.
Program models commonly pass `inc_studies` or `kf_studies`.

## Override Study Var Name

```jinja
{% set rels = combined_stb_relations(table_name='patient', studies_var='my_studies_var') %}
```

## What You Get

A relation list you can pass to union helpers such as `dbt_utils.union_relations`.

## Common Error

If your studies var is empty, the macro raises an error.
Set a non-empty list in vars before compile/run.
