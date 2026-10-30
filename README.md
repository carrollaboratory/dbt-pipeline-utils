# dbt-pipeline-utils

`dbt-pipeline-utils` is a collection of reusable tools for dbt pipeline
repositories. It provides:

- Python command-line tools that generate dbt YAML and SQL from data
  dictionaries.
- dbt macros for common pipeline tasks, including schema naming, descriptor
  normalization, combined models, and grants.

The package does not provide dbt models of its own. Use the Python tools
independently to generate project files, and install the dbt package when you
want to use its macros.

## Installation

### Python command-line tools

Install from this repository with pip:

```bash
pip install "git+https://github.com/carrollaboratory/dbt-pipeline-utils.git"
```

To install a particular branch, tag, or commit, add it after `@`:

```bash
pip install "git+https://github.com/carrollaboratory/dbt-pipeline-utils.git@<ref>"
```

The package requires Python newer than 3.10. Its dependencies are installed
automatically by pip.

To work on a local checkout, install it in editable mode:

```bash
git clone https://github.com/carrollaboratory/dbt-pipeline-utils.git
cd dbt-pipeline-utils
pip install -e .
```

### dbt macros

In the dbt project that will use the macros, add the package to `packages.yml`:

```yaml
packages:
  - git: "https://github.com/carrollaboratory/dbt-pipeline-utils.git"
    revision: <tag-or-commit>
```

Then install dbt dependencies from that project:

```bash
dbt deps
```

Call macros using the package name declared in its `dbt_project.yml`,
`dbt_pipeline_utils`, for example:

```sql
{{ dbt_pipeline_utils.generate_schema_name(custom_schema_name, node) }}
```

Some macros depend on `dbt_utils`. dbt does not install transitive package
dependencies, so declare `dbt-labs/dbt_utils` directly in your project's
`packages.yml` when using a macro that requires it.

## Data-dictionary inputs

The generation commands accept one or more local CSV or Excel data-dictionary
files and directories. When passing a directory, the tools discover files
whose names end in one of these suffixes:

- `_dd.csv`, `-dd.csv`, `_dd.xlsx`, `-dd.xlsx`
- `_dictionary.csv`, `-dictionary.csv`, `_dictionary.xlsx`,
  `-dictionary.xlsx`

Explicitly supplied file paths do not need to follow these naming conventions.
Unless a table name is otherwise specified, it is derived from the filename,
with a recognized data-dictionary suffix removed and the name normalized to
lowercase snake case.

The default dictionary format is `ftd_dd`. The other built-in formats are
`src_type1` and `pipeline_format`. Use `--dd-format` to select a format whose
column names match your files.

The generation commands can also read data dictionaries from GitHub release
assets. Release assets can be used alone or mixed with local files; ZIP assets
are expanded in memory to find matching data-dictionary files. Use
`--release REPOSITORY ASSET` for each asset. The repository can be a GitHub URL
or a supported preset alias such as `kf`, `inc`, or `common`. Use
`--release-tag` to select a tag, and `--release-token` for private
repositories. Add `--refresh` to bypass the in-process asset cache.

## Python commands

Install the package to make these commands available in your shell. Run a
command with `--help` to see its complete options.

### Generate dbt model YAML

`generate_models_yml` creates or updates a dbt model YAML file from one or more
dictionaries. By default, it merges changes into the existing file, preserving
the order of unchanged entries. It can also generate column documentation
blocks and dbt tests from a dictionary's `tests` column.

```bash
generate_models_yml \
  -i data_dictionaries/access \
  -o models/access/_models.yml \
  -d models/access/_column_descriptions.md
```

Use `--mode create`, `--mode overwrite`, or `--mode merge` to choose how the
output is written. Use `--no-tests` to skip dictionary-provided tests.

### Generate dbt source YAML

`generate_sources_yml` creates or updates tables under a named dbt source and
schema. It can also generate column documentation blocks.

```bash
generate_sources_yml \
  -i data_dictionaries/raw \
  -o models/staging/_sources.yml \
  --source-name raw_study_data \
  --schema raw \
  -d models/staging/_column_descriptions.md
```

### Generate SQL models

`generate_sql_models` creates one model SQL file per dictionary. It creates a
developer-owned model only if the file does not already exist, so hand-edited
models are preserved. It also refreshes a `<table>_generated.sql` reference
file with SQL derived from the current dictionary; compare the two files to
review dictionary changes.

```bash
generate_sql_models \
  -i data_dictionaries/int \
  -o models/int \
  --from-clause-template "{{ source('raw_study_data', '{table_name}') }}"
```

Use `--reference-dir` to put generated reference files in a separate
directory. Use `--int-descriptors` to generate zero-row intermediate model
templates with a descriptor column.

### Generate source SQL models

`generate_src_models` creates one source-facing SQL model per dictionary. The
models select the dictionary columns, cast values to text, normalize output
column names to lowercase snake case, and read from a dbt `source()`.

```bash
generate_src_models \
  -i data_dictionaries/raw \
  -o models/src \
  --source-name raw_study_data
```

### Generate STB combined-union SQL

`generate_stb_union_sql` creates one combined-union SQL model for each
dictionary source. The generated SQL calls the package macro
`combined_union_from_current_model`.

```bash
generate_stb_union_sql \
  -i data_dictionaries/stb \
  -o models/stb
```

### Work with GitHub release assets

The generation commands above accept repeatable `--release` arguments as
alternative or additional dictionary inputs. For example:

```bash
generate_models_yml \
  --release inc project-artifacts.zip \
  --release-tag v1.2.0 \
  -o models/access/_models.yml
```

The package also provides utilities for release assets:

- `list_release_assets REPOSITORY` lists assets attached to a GitHub release.
- `generate_models_yml_from_release_asset REPOSITORY ASSET -o OUTPUT` is a
  single-asset convenience command for model YAML generation.
- `extract_release_artifact_file REPOSITORY ASSET INTERNAL_PATH OUTPUT_PATH`
  extracts a file or directory from a ZIP release asset to disk.

These commands accept a release tag and, for private repositories, a GitHub
token. Run each with `--help` for exact argument details.

### Track dictionary revisions

The model YAML, source YAML, and SQL generation commands accept
`--version-log PATH`. This appends a CSV record when a model or table's
dictionary source, version, asset, or content hash changes; unchanged inputs
do not add duplicate records.

## dbt macros

The macros are under [`macros/`](macros/), grouped into:

- `pipeline/`: pipeline helpers for schema names, descriptor views, descriptor
  normalization, source references, combined models, and STB SQL.
- `grants/`: macros for granting developer or schema-role access.
- `ad_hoc/`: utilities for specific data-loading and profile tasks.

The [macro quickstarts](macros/pipeline/docs/) show examples for individual
macros, including [STB SQL generation](macros/pipeline/docs/generate_stb_sql_quickstart.md),
[schema naming](macros/pipeline/docs/generate_schema_name_quickstart.md), and
[descriptor normalization](macros/pipeline/docs/normalize_descriptors_quickstart.md).
