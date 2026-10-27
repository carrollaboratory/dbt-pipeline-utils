# Shared generator function recipes.
# These expect environment variables to be set by the calling justfile.

_dd_source_args := '
    args=()
    if [[ -n "${DD_DIR:-}" ]]; then args+=(-i "$DD_DIR"); fi
    for entry in ${RELEASE_ASSETS:-}; do
        repo="${entry%%|*}"
        asset="${entry#*|}"
        args+=(--release "$repo" "$asset")
    done
    if [[ -n "${RELEASE_TAG:-}" ]]; then args+=(--release-tag "$RELEASE_TAG"); fi
    if [[ -n "${RELEASE_TOKEN:-}" ]]; then args+=(--release-token "$RELEASE_TOKEN"); fi
    if [[ -n "${REFRESH:-}" ]]; then args+=(--refresh); fi
'

[private]
_gen_models:
    #!/usr/bin/env bash
    {{ _dd_source_args }}
    args+=(-o "$MODELS_YML" -f "$DD_FORMAT")
    if [[ -n "${TABLE_PREFIX:-}" ]]; then args+=(-p "$TABLE_PREFIX"); fi
    if [[ -n "${MODELS_DOCS:-}" ]]; then args+=(-d "$MODELS_DOCS"); fi
    if [[ -n "${VERSION_LOG:-}" ]]; then args+=(--version-log "$VERSION_LOG"); fi
    generate_models_yml "${args[@]}"

[private]
_gen_sources:
    #!/usr/bin/env bash
    {{ _dd_source_args }}
    args+=(-o "$SOURCES_YML" -s "$SOURCE_NAME" --schema "$SOURCE_SCHEMA" -f "$DD_FORMAT")
    if [[ -n "${TABLE_PREFIX:-}" ]]; then args+=(-p "$TABLE_PREFIX"); fi
    if [[ -n "${SOURCES_DOCS:-}" ]]; then args+=(-d "$SOURCES_DOCS"); fi
    if [[ -n "${VERSION_LOG:-}" ]]; then args+=(--version-log "$VERSION_LOG"); fi
    generate_sources_yml "${args[@]}"

[private]
_gen_model_sql:
    #!/usr/bin/env bash
    {{ _dd_source_args }}
    args+=(-o "$SQL_DIR" -f "$DD_FORMAT")
    if [[ -n "${TABLE_PREFIX:-}" ]]; then args+=(-p "$TABLE_PREFIX"); fi
    if [[ -n "${FROM_CLAUSE_TEMPLATE:-}" ]]; then args+=(--from-clause-template "$FROM_CLAUSE_TEMPLATE"); fi
    if [[ -n "${SQL_REFERENCE_DIR:-}" ]]; then args+=(--reference-dir "$SQL_REFERENCE_DIR"); fi
    if [[ -n "${VERSION_LOG:-}" ]]; then args+=(--version-log "$VERSION_LOG"); fi
    generate_sql_models "${args[@]}"

[private]
_gen_src_sql:
    #!/usr/bin/env bash
    {{ _dd_source_args }}
    args+=(-o "$SRC_SQL_DIR" -s "$SRC_SOURCE_NAME" -f "$DD_FORMAT" --materialized "$SRC_MATERIALIZED")
    if [[ -n "${SRC_TABLE_PREFIX:-}" ]]; then args+=(--sql-file-prefix "$SRC_TABLE_PREFIX"); fi
    if [[ -n "${TABLE_PREFIX:-}" ]]; then args+=(-p "$TABLE_PREFIX"); fi
    if [[ -n "${VERSION_LOG:-}" ]]; then args+=(--version-log "$VERSION_LOG"); fi
    generate_src_models "${args[@]}"

[private]
_pull_dd:
    #!/usr/bin/env bash
    if [[ -z "${DDS_PULL_COMMAND:-}" ]]; then
        echo "Set DDS_PULL_COMMAND to a command that downloads/releases DD files into DD_DIR=$DD_DIR." >&2
        exit 2
    fi
    eval "$DDS_PULL_COMMAND"

[private]
_extract_release_file:
    #!/usr/bin/env bash
    if [[ -z "${RELEASE_REPO:-}" ]]; then
        echo "Set RELEASE_REPO to a preset (kf/include/inc/common) or a full GitHub URL." >&2
        exit 2
    fi
    if [[ -z "${RELEASE_INTERNAL_PATH:-}" ]]; then
        echo "Set RELEASE_INTERNAL_PATH to the file path inside $RELEASE_ARTIFACT." >&2
        exit 2
    fi
    if [[ -z "${RELEASE_OUTPUT_PATH:-}" ]]; then
        echo "Set RELEASE_OUTPUT_PATH to the destination file path." >&2
        exit 2
    fi

    args=(
      "$RELEASE_REPO"
      "$RELEASE_ARTIFACT"
      "$RELEASE_INTERNAL_PATH"
      "$RELEASE_OUTPUT_PATH"
      --tag "$RELEASE_TAG"
    )
    if [[ -n "${RELEASE_TOKEN:-}" ]]; then args+=(--token "$RELEASE_TOKEN"); fi
    if [[ -n "${REFRESH:-}" ]]; then args+=(--refresh); fi

    extract_release_artifact_file "${args[@]}"
