
# pipeline-utils

Standalone, composable CLI tools for generating dbt files (`models.yml`, `sources.yml`, SQL models).

## Commands

All generators accept DD inputs from local files/directories and/or GitHub release assets in memory. Use `-i` for local DD paths and `--release` for release assets.

### generate_models_yml

Builds/updates a dbt `models.yml` from DDs. Merge mode preserves stable ordering and produces clean diffs.

| Argument | Required | Default | When to use |
|---|---|---|---|
| `-i`, `--dd-filepaths` | No* | `[]` | Use for one or more local DD files and/or directories. |
| `-o`, `--models-yml-output` | Yes | None | Path to output `models.yml`. |
| `-p`, `--table-prefix` | No | `None` | Prefix all model names for namespacing (`inc_access_*`, etc.). |
| `-f`, `--dd-format` | No | `ftd_dd` | Use when DD columns follow a non-default mapping. |
| `-d`, `--docs-output` | No | `None` | Append/update `_column_descriptions.md` docs blocks. |
| `--no-tests` | No | `False` | Skip dbt test generation from DD `tests` column. |
| `-m`, `--mode` | No | `merge` | `create` for first-time files, `overwrite` to replace file, `merge` for diff-friendly updates. |
| `--version-log` | No | `None` | Track source/version/hash changes per model in a CSV over time. |
| `--release REPO_URL ASSET_NAME` | No* | None | Pull DD assets from GitHub releases in memory (repeatable). |
| `--release-tag` | No | `latest` | Pin to a specific release tag/version. |
| `--release-token` | No | `None` | Required for private repositories. |
| `--refresh` | No | `False` | Force fresh GitHub pull; otherwise in-process in-memory cache is used. |

`*` You must provide at least one input source via `-i` or `--release`.

### generate_sources_yml

Builds/updates a dbt `sources.yml` block from DDs with the same merge semantics.

| Argument | Required | Default | When to use |
|---|---|---|---|
| `-i`, `--dd-filepaths` | No* | `[]` | Local DD files/directories. |
| `-o`, `--sources-yml-output` | Yes | None | Path to output `sources.yml`. |
| `-s`, `--source-name` | Yes | None | Target dbt source block name (`sources: - name:`). |
| `--schema` | Yes | None | Database schema for that source block. |
| `-p`, `--table-prefix` | No | `None` | Prefix all source table names. |
| `-f`, `--dd-format` | No | `ftd_dd` | Non-default DD column mapping. |
| `-d`, `--docs-output` | No | `None` | Append/update source column docs file. |
| `--version-log` | No | `None` | Track source/version/hash changes per table. |
| `--release REPO_URL ASSET_NAME` | No* | None | Add release DD asset(s) as in-memory inputs. |
| `--release-tag` | No | `latest` | Pull from a specific release tag. |
| `--release-token` | No | `None` | Private repo auth. |
| `--refresh` | No | `False` | Bypass in-memory cache and re-pull. |

### generate_sql_models

Generates dev-owned model SQL plus always-refreshed `_generated.sql` reference files.

| Argument | Required | Default | When to use |
|---|---|---|---|
| `-i`, `--dd-filepaths` | No* | `[]` | Local DD files/directories. |
| `-o`, `--output-dir` | Yes | None | Directory for hand-edited `<table>.sql` files. |
| `-p`, `--table-prefix` | No | `None` | Prefix output table/model names. |
| `-f`, `--dd-format` | No | `ftd_dd` | Non-default DD column mapping. |
| `--from-clause-template` | No | `None` | Emit `from` clauses (for example dbt `source(...)`) using `{table_name}` placeholder. |
| `--reference-dir` | No | Same as `--output-dir` | Write refreshed `<table>_generated.sql` files to a separate directory. |
| `--int-descriptors` | No | `False` | Create an empty table template with commented `*_id` columns, null values, and a null `<table>_descriptor` column. |
| `--version-log` | No | `None` | Track DD version/hash changes per table. |
| `--release REPO_URL ASSET_NAME` | No* | None | Use release DD asset(s) in memory. |
| `--release-tag` | No | `latest` | Pull from a specific release tag. |
| `--release-token` | No | `None` | Private repo auth. |
| `--refresh` | No | `False` | Force fresh pull instead of in-memory cache. |

Example diff workflow:

```bash
diff models/int/patients.sql models/int/patients_generated.sql
```

There's no notion of a "stage" baked into the code - int/exp/whatever are just different directories/output paths you choose per call. Use separate `just sql` invocations with different `DD_DIR`, `SQL_DIR`, `TABLE_PREFIX`, and `FROM_CLAUSE_TEMPLATE` values for multiple model sets.

## Release-backed Inputs

The `--release` argument is repeatable and can be combined with local `-i` paths. DD bytes are kept in memory and are not written to disk by the generators.

```bash
generate_models_yml \
    --release https://github.com/<owner>/<repo> patients_dd.csv \
    --release https://github.com/<owner>/<repo> labs_dd.csv \
    -o models/access/includes/__models.yml \
    -p inc_access
```

For `REPO_URL`, you can use a full URL or these aliases:

  - `kf` / `kf-access-model` -> `https://github.com/carrollaboratory/kf-access-model.git`
  - `include` / `inc` / `include-access-model` -> `https://github.com/include-dcc/include-access-model.git`
  - `common` / `common-access-model` -> `https://github.com/include-dcc/common-access-model.git`

### generate_models_yml_from_release_asset

Single-asset convenience CLI for `models.yml` generation.

| Argument | Required | Default | When to use |
|---|---|---|---|
| `repository_url` | Yes | None | Full GitHub URL for release source repo. |
| `asset_name` | Yes | None | Exact release asset filename. |
| `-o`, `--models-yml-output` | Yes | None | Output `models.yml` path. |
| `-t`, `--tag` | No | `latest` | Pull from specific release tag. |
| `--token` | No | `None` | Private repo auth. |
| `--refresh` | No | `False` | Force fresh pull (skip in-memory cache). |
| `-n`, `--table-name` | No | Derived from asset name | Override inferred model name. |
| `-p`, `--table-prefix` | No | `None` | Prefix model name. |
| `-f`, `--dd-format` | No | `ftd_dd` | Non-default DD column mapping. |
| `-d`, `--docs-output` | No | `None` | Append docs blocks. |
| `--no-tests` | No | `False` | Skip test generation from DD tests column. |
| `-m`, `--mode` | No | `merge` | `create`, `overwrite`, or `merge`. |
| `--version-log` | No | `None` | Append change rows to version log CSV. |

### list_release_assets

Lists all assets attached to a release so you can confirm exact asset names before pulling them.

| Argument | Required | Default | When to use |
|---|---|---|---|
| `repository_url` | Yes | None | Full GitHub URL or alias (`kf`, `include`, `inc`, `common`). |
| `-t`, `--tag` | No | `latest` | Inspect a specific release tag. |
| `--token` | No | `None` | Private repo auth. |
| `--refresh` | No | `False` | Force metadata refresh instead of in-memory cache. |

The pulled bytes are cached in memory per `(repository_url, asset_name, tag)`, so calling this again for the same version doesn't re-hit the network - pass `--refresh` to force a fresh pull (e.g. after re-publishing the same tag), or just point at a different tag to always fetch fresh.

From Python, `dbt_pipeline_utils.p_utils.dd_sources.pull_release_dd(repository_url, asset_name, tag=..., token=..., refresh=...)` returns an in-memory source object that can be passed directly (mixed freely with local paths) to `generate_models_yml`/`generate_sources_yml`/`generate_sql_models`.

## Tracking data dictionary versions

All four generators accept `--version-log <path>` (Python: `version_log=`), which appends one row per model/table to a CSV: `timestamp,model,source,version,asset,content_hash`. A row is only appended when that information differs from the last recorded row for that model, so re-running against unchanged data never grows the log - only real refreshes (a new release tag, a re-published asset, or an edited local CSV) do.

## Justfile Workflows

This repo now has three profiles that share common generator functions:

- `justfile` (basic): one stage at a time, lowest cognitive load
- `justfile.advanced` (advanced): explicit per-stage configuration and staged runs
- `justfile.access` (access model): refresh-only from GitHub release artifacts to local DD directories

When using local DD files, the workflow is:

1. Refresh data dictionaries once using `justfile.access` (`cdm_refresh`)
2. Generate files using `justfile` or `justfile.advanced`

You can instead generate directly from release DD assets in memory, without local DD files or existing SQL models.

### Quick validation

Check recipe availability before running generation:

```bash
just --list --unsorted
just -f justfile.advanced --list --unsorted
just -f justfile.access --list --unsorted
```

### Basic profile (`justfile`)

Generate a single stage run:

```bash
just STUDY_ID=brainpower PIPELINE_STAGE=src generate-stage
just STUDY_ID=brainpower PIPELINE_STAGE=int generate-stage
just STUDY_ID=brainpower PIPELINE_STAGE=program generate-stage
```

Stage behavior:

- `src` generates `sources.yml`, source column descriptions, and src SQL models.
- `int` generates `models.yml`, model column descriptions, and zero-row table SQL with null columns and a `<table>_descriptor` placeholder; `*_id` columns are commented out.
- `program` generates `models.yml`, model column descriptions, and regular model SQL files.

### Advanced profile (`justfile.advanced`)

To run from a new pipeline repository, install this Python package (`pip install -e /path/to/pipeline-utils`) and put `justfile.advanced` and `common.just` in that repository's root. Relative input and output paths then refer to the pipeline repository. For a pipeline with only `src` and `int`, use different releases for each stage:

```bash
just -f justfile.advanced \
  STUDY_ID=brainpower PIPELINE_STAGES='src int' \
  MODELS_STAGE_ROOT=models/include \
  SRC_DD_DIR='' INT_DD_DIR='' \
  SRC_RELEASE_ASSETS='inc|project-artifacts.zip' \
  INT_RELEASE_ASSETS='kf|project-artifacts.zip' \
  RELEASE_TAG=latest \
  generate-all-stages
```

Change `inc`/`kf` to release repo URLs or aliases and set `RELEASE_TAG=v1.2.0` to pin a version. Each stage also accepts several space-separated `repo|asset` pairs. Set `DD_FORMAT` if the release DD columns do not use `ftd_dd`. This creates SQL and YAML in `models/include/brainpower/src` and `models/include/brainpower/int`; no models need to exist beforehand. The ZIP must contain `*_dd.*`, `*-dd.*`, `*_dictionary.*`, or `*-dictionary.*` files. Each generator invocation fetches its own release bytes; the in-memory cache does not persist between separate commands.

Generate all configured stages or SQL-only pipeline targets:

```bash
just -f justfile.advanced STUDY_ID=brainpower generate-all-stages
just -f justfile.advanced generate-pipeline-sql
```

Generate one stage directly:

```bash
just -f justfile.advanced generate-stage src
just -f justfile.advanced generate-stage int
just -f justfile.advanced generate-stage program
```

`generate-all-stages` and `generate-stage` use the same stage behavior as the basic profile: `src` is source-facing, while `int` and `program` are model-facing.

### Access refresh profile (`justfile.access`)

Refresh DDs once from the three upstream models (`common`, `inc`, `kf`):

```bash
just -f justfile.access cdm_refresh
just -f justfile.access RELEASE_TAG=v1.2.0 cdm_refresh
```

To use this refresh in another repo, place `justfile.access` and `common.just` there and set `COMMON_DD_DIR`, `INC_DD_DIR`, and `KF_DD_DIR` to destinations in that repo. The first command pulls the latest release by default; the second pins a tag. This downloads DD files; it does not run `git pull` in local checkouts. Then point generation at those directories or use release assets in memory as shown above.

### Direct usage (compatibility wrappers)

Each generation profile also exposes the underlying generator recipes directly, for one-off runs outside the stage/study conventions:

```bash
just DD_DIR=utils_resources/data_dictionaries/access/kf_access MODELS_YML=/tmp/models.yml generate-models-yml
just DD_DIR=utils_resources/data_dictionaries/access/kf_access SOURCES_YML=/tmp/sources.yml SOURCE_NAME=raw SOURCE_SCHEMA=raw generate-sources-yml
just DD_DIR=utils_resources/data_dictionaries/access/kf_access SQL_DIR=/tmp/sql generate-model-sql
just DD_DIR=utils_resources/data_dictionaries/access/kf_access SRC_SQL_DIR=/tmp/src_sql SRC_SOURCE_NAME=raw generate-src-sql
```

The same recipes exist in `justfile.advanced` (add `-f justfile.advanced`); it also declares `DD_DIR` for this direct-usage path only, alongside its stage-specific `SRC_DD_DIR`/`INT_DD_DIR`/`PROGRAM_DD_DIR` variables.

### Notes

- Generation profiles accept local DD paths (`DD_DIR`/`SRC_DD_DIR`/etc.) and/or in-memory release assets (`RELEASE_ASSETS="repo|asset"`) - mix or match as needed.
- Set `VERSION_LOG=path/to/dd_versions.csv` on any run command to track DD source/version/hash changes over time.

## Extracting one file from a ZIP release artifact

Use `extract_release_artifact_file` to pull a ZIP release asset and extract either one file or a whole internal directory.

| Argument | Required | Default | When to use |
|---|---|---|---|
| `repository` | Yes | None | Full GitHub URL or preset alias (`kf`, `include`, `inc`, `common`, etc.). |
| `artifact_name` | Yes | None | ZIP release asset name (for example `project-artifacts.zip`). |
| `internal_path` | Yes | None | File path inside ZIP for single-file extraction, or directory prefix for subtree copy. |
| `output_path` | Yes | None | File destination for single-file extraction, or destination directory for subtree copy. |
| `-t`, `--tag` | No | `latest` | Pull from a specific release tag. |
| `--token` | No | `None` | Private repo auth. |
| `--refresh` | No | `False` | Force fresh pull; otherwise in-memory cache is reused. |

Single file example:

```bash
extract_release_artifact_file \
  kf \
  project-artifacts.zip \
  data_dictionaries/patients_dd.csv \
  /tmp/patients_dd.csv
```

Directory copy example:

```bash
extract_release_artifact_file \
  kf \
  project-artifacts.zip \
  project/data-dictionary \
  /tmp/data-dictionary
```

You can also use the `justfile` wrapper:

```bash
just -f justfile.access RELEASE_REPO=kf \
  RELEASE_ARTIFACT=project-artifacts.zip \
  RELEASE_INTERNAL_PATH=data_dictionaries/patients_dd.csv \
  RELEASE_OUTPUT_PATH=/tmp/patients_dd.csv \
  extract-release-file
```

For non-GitHub-release sources, a project-specific importer can still be supplied via `DDS_PULL_COMMAND` and run with `just DDS_PULL_COMMAND='...' pull-dd` to populate `DD_DIR` before generation.

## Shared dbt macros

This repo is itself importable as a dbt package, so macros in [`macros/`](macros/) (`grants/`, `ad_hoc/`, `pipeline/`) can be reused across pipeline repos instead of copy-pasted into each one. It has no models/seeds of its own - `dbt_project.yml` only declares `macro-paths`.

Add it to a pipeline repo's `packages.yml`:

```yaml
packages:
  - git: "https://github.com/NIH-NCPI/pipeline-utils.git"
    revision: main  # pin to a tag/commit for anything beyond local testing
  - package: dbt-labs/dbt_utils   # required directly by some pipeline macros (e.g. combined_union)
    version: [">=1.1.0", "<2.0.0"]
```

Then run `dbt deps` in the pipeline repo and call macros with the package's `name` from `dbt_project.yml` as the namespace, e.g. `{{ dbt_pipeline_utils.grant_devs_access(tag=..., users_role=...) }}`.

dbt packages don't resolve transitive dependencies - if a macro here uses `dbt_utils`, the pipeline repo importing this package must also declare `dbt-labs/dbt_utils` in its own `packages.yml`, as shown above.

## Development

Running the script locally or working on a branch?
Create and activate a virtual environment (recommended):
[Click here] for more on virtual environments.

** NOTE: SOME projects recommend pyenv. 
TODO: Give more info about pyenv

```
# Step 1: cd into the directory to store the venv

# Step 2: run this code. It will create the virtual env named utils_venv in the current directory.
python3 -m venv utils_venv

# Step 3: run this code. It will activate the utils_venv environment
source utils_venv/bin/activate # On Windows: venv\Scripts\activate

# You are ready for installations! 
# If you want to deactivate the venv run:
deactivate
```
Install the package
If working on a new feature it is possible to install a package version within the remote or local branch NOTE If testing changes to dbt_pipeline_utils in the dbt project don't forget to deploy a dbt project branch with the correct dbt_pipeline_utils version in the requirements.txt file! NOTE Any new env variables created, e.g. api keys, will need to be added to the dbt project deployment files.
# remote
pip install git+https://github.com/NIH-NCPI/pipeline-utils.git@{branch_name}

# local
pip install -e .

# Locutus should install using the following command.
pip install git+https://github.com/NIH-NCPI/pipeline_utils.git

# A re-install might be required while testing any changes to this repo, use this command to force the reinstall and ensure the latest version.
pip install --force-reinstall --no-cache-dir git+https://github.com/NIH-NCPI/pipeline-utils.git


# Developers
To add a new data dictionary format, add an entry to `DD_FORMATS` in `src/dbt_pipeline_utils/p_utils/common.py` mapping each expected column (`variable_name`, `description`, `data_type`, `enumerations`, `comment`, `src_variable_name`, `tests`, ...) to the corresponding column name in that format. Pass the format's key as `-f`/`--dd-format` to any of the CLI tools.
 - always update the readme options

Data dictionary files are matched by the `*_dd.*`/`*-dd.*` naming convention when a directory is given as input; the trailing `_dd`/`-dd` is stripped when deriving a default table name from the filename.