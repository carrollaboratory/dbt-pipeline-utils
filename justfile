set shell := ["bash", "-cu"]
set export

import "common.just"

# Basic generation profile: one dataset/stage at a time.
PROGRAM_ID := "inc"
STUDY_ID := "brainpower"
PIPELINE_STAGE := "src"  # src|int

# Local DD input root (optional when RELEASE_ASSETS is set).
DD_DIR := "../test_files/inc_brainpower"
MODELS_STAGE_ROOT := "include_kf_dbt_harmonization/models/include"

DD_FORMAT := "ftd_dd"
SRC_MATERIALIZED := "table"

# Stage naming. Empty values are derived from PROGRAM_ID and STUDY_ID by the
# stage recipes; set a value to override it, or `none` to disable a prefix.
#   SOURCE_SCHEMA        -> <program_id>_<study_id>_raw
#   SRC_TABLE_PREFIX     -> <program_id>_<study_id>_src
#   SRC_SOURCE_NAME      -> <program_id>_<study_id>_src
#   TABLE_PREFIX (int)   -> <program_id>_<study_id>_int   (src stays unprefixed)
#   FROM_CLAUSE_TEMPLATE (int) -> {{ ref('<src_table_prefix>_{base_name}') }}
TABLE_PREFIX := ""
SOURCE_SCHEMA := ""
SRC_TABLE_PREFIX := ""
SRC_SOURCE_NAME := ""
FROM_CLAUSE_TEMPLATE := ""
VERSION_LOG := ""

# Optional in-memory DD inputs (repeatable as "repo|asset" entries).
RELEASE_ASSETS := ""
RELEASE_TAG := "latest"
RELEASE_TOKEN := ""
REFRESH := ""

DDS_PULL_COMMAND := ""

# Direct-usage pass-through vars for the compatibility wrapper recipes below.
MODELS_YML := ""
MODELS_DOCS := ""
SOURCES_YML := ""
SOURCES_DOCS := ""
SOURCE_NAME := ""
SQL_DIR := ""
SRC_SQL_DIR := ""

default:
    @just --list

help:
    @just --list --unsorted
    @printf '%s\n' '' 'Basic generation examples (csv path and/or in-memory releases):' \
        '  just STUDY_ID=brainpower PIPELINE_STAGE=src generate-stage' \
        '  just STUDY_ID=brainpower PIPELINE_STAGE=int generate-stage' \
        '  just STUDY_ID=brainpower DD_DIR=data_dictionaries/src generate-stage' \
        '  just STUDY_ID=brainpower DD_DIR="" RELEASE_ASSETS="inc|project-artifacts.zip" generate-stage' \
        '' \
        'Advanced staged generation profile:' \
        '  just -f justfile.advanced help' \
        '' \
        'Refresh from GitHub releases is handled in justfile.access only:' \
        '  just -f justfile.access help'

_resolve_basic_paths := '
    stage="$PIPELINE_STAGE"
    study_id="$STUDY_ID"
    dd_root="$DD_DIR"
    models_root="$MODELS_STAGE_ROOT"

    stage_dir="$models_root/$study_id/$stage"

    dd_dir_by_study="$dd_root/$stage/$study_id"
    dd_dir_by_stage="$dd_root/$stage"
    if [[ -n "$dd_root" && -d "$dd_dir_by_study" ]]; then
        run_dd_dir="$dd_dir_by_study"
    elif [[ -n "$dd_root" && -d "$dd_dir_by_stage" ]]; then
        run_dd_dir="$dd_dir_by_stage"
    else
        run_dd_dir="$dd_root"
    fi

    if [[ -n "$run_dd_dir" && ! -e "$run_dd_dir" ]]; then
        if [[ -n "$RELEASE_ASSETS" ]]; then
            run_dd_dir=""
        else
            echo "Configured DD path does not exist: $run_dd_dir" >&2
            echo "Set DD_DIR to an existing path or set RELEASE_ASSETS for in-memory inputs." >&2
            exit 2
        fi
    fi

    run_models_yml="$stage_dir/_models.yml"
    run_models_docs="$stage_dir/_column_descriptions.md"
    run_sources_yml="$stage_dir/_sources.yml"
    run_sources_docs="$stage_dir/_column_descriptions.md"
    run_sql_dir="$stage_dir"
    run_src_sql_dir="$stage_dir"

    name_base="${PROGRAM_ID}_${study_id}"
    export SOURCE_SCHEMA="${SOURCE_SCHEMA:-${name_base}_raw}"
    export SRC_TABLE_PREFIX="${SRC_TABLE_PREFIX:-${name_base}_src}"
    export SRC_SOURCE_NAME="${SRC_SOURCE_NAME:-${name_base}_src}"
    if [[ "$SRC_TABLE_PREFIX" == "none" ]]; then SRC_TABLE_PREFIX=""; fi
    if [[ "$stage" == "int" ]]; then
        export TABLE_PREFIX="${TABLE_PREFIX:-${name_base}_int}"
        if [[ -z "$FROM_CLAUSE_TEMPLATE" ]]; then
            ref_name="{base_name}"
            if [[ -n "$SRC_TABLE_PREFIX" ]]; then ref_name="${SRC_TABLE_PREFIX}_{base_name}"; fi
            export FROM_CLAUSE_TEMPLATE="{{ ref($(printf "\047")${ref_name}$(printf "\047")) }}"
        fi
    fi
    if [[ "$TABLE_PREFIX" == "none" ]]; then TABLE_PREFIX=""; fi
'

# Direct generator wrappers.
generate-models-yml:
    just -f common.just _gen_models

generate-sources-yml:
    just -f common.just _gen_sources

generate-model-sql:
    just -f common.just _gen_model_sql

generate-src-sql:
    just -f common.just _gen_src_sql

generate-stage-models-yml:
    #!/usr/bin/env bash
    {{ _resolve_basic_paths }}
    DD_DIR="$run_dd_dir" \
    MODELS_YML="$run_models_yml" \
    MODELS_DOCS="$run_models_docs" \
    just -f common.just _gen_models

generate-stage-sources-yml:
    #!/usr/bin/env bash
    {{ _resolve_basic_paths }}
    DD_DIR="$run_dd_dir" \
    SOURCES_YML="$run_sources_yml" \
    SOURCES_DOCS="$run_sources_docs" \
    SOURCE_NAME="$SRC_SOURCE_NAME" \
    just -f common.just _gen_sources

generate-stage-model-sql:
    #!/usr/bin/env bash
    {{ _resolve_basic_paths }}
    DD_DIR="$run_dd_dir" \
    SQL_DIR="$run_sql_dir" \
    just -f common.just _gen_model_sql

generate-stage-src-sql:
    #!/usr/bin/env bash
    {{ _resolve_basic_paths }}
    DD_DIR="$run_dd_dir" \
    SRC_SQL_DIR="$run_src_sql_dir" \
    SRC_SOURCE_NAME="$SRC_SOURCE_NAME" \
    just -f common.just _gen_src_sql

generate-stage:
    #!/usr/bin/env bash
    {{ _resolve_basic_paths }}

    if [[ "$PIPELINE_STAGE" == "src" ]]; then
        DD_DIR="$run_dd_dir" \
        SOURCES_YML="$run_sources_yml" \
        SOURCES_DOCS="$run_sources_docs" \
        SOURCE_NAME="$SRC_SOURCE_NAME" \
        just -f common.just _gen_sources

        DD_DIR="$run_dd_dir" \
        SRC_SQL_DIR="$run_src_sql_dir" \
        SRC_SOURCE_NAME="$SRC_SOURCE_NAME" \
        just -f common.just _gen_src_sql
    else
        DD_DIR="$run_dd_dir" \
        MODELS_YML="$run_models_yml" \
        MODELS_DOCS="$run_models_docs" \
        just -f common.just _gen_models

        DD_DIR="$run_dd_dir" \
        SQL_DIR="$run_sql_dir" \
        just -f common.just _gen_model_sql
    fi

clean-dir:
    #!/usr/bin/env bash
    {{ _resolve_basic_paths }}
    if [[ -d "$run_sql_dir" ]]; then
        find "$run_sql_dir" -type f -name '*_generated.sql' -delete
    fi
