"""
CLI: generate one STB combined-union model SQL file per DD source.

Each output file contains:
  {{ config(materialized='table') }}

  {{ combined_union_from_current_model(studies_var='...') }}

Supports local DD files/directories and GitHub release DD assets via --release.
"""

import argparse
from pathlib import Path

from dbt_pipeline_utils.p_utils.actions._release_args import (
    add_release_arguments,
    resolve_dd_sources,
)
from dbt_pipeline_utils.p_utils.sql_models import generate_stb_union_models


def main():
    parser = argparse.ArgumentParser(
        description="Generate one STB combined-union model SQL file per data dictionary source."
    )
    parser.add_argument(
        "-i",
        "--dd-filepaths",
        nargs="+",
        type=Path,
        default=[],
        help="One or more data dictionary files and/or directories (csv/xlsx). Optional if --release is given.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        required=True,
        type=Path,
        help="Directory where generated STB union model SQL files are written.",
    )
    parser.add_argument(
        "--studies-var",
        default="inc_studies",
        help="Value for studies_var in combined_union_from_current_model(...).",
    )
    parser.add_argument(
        "--model-prefix",
        default="combined",
        help="Optional prefix for generated model filenames.",
    )
    add_release_arguments(parser)
    args = parser.parse_args()

    written = generate_stb_union_models(
        resolve_dd_sources(args),
        args.output_dir,
        studies_var=args.studies_var,
        model_prefix=args.model_prefix,
    )
    print(f"Wrote {written} stb union model files to {args.output_dir}")


if __name__ == "__main__":
    main()
