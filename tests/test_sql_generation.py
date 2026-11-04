import csv
import importlib.util
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from dbt_pipeline_utils.p_utils.actions.generate_src_models import main as generate_src_models_cli
from dbt_pipeline_utils.p_utils.dd_sources import InMemoryDataDictionary
from dbt_pipeline_utils.p_utils.files import write_file
from dbt_pipeline_utils.p_utils.sql_models import (
    generate_sql_models,
    generate_src_models,
    generate_stb_union_models,
)


class SQLGenerationTests(unittest.TestCase):
    def test_sql_writer_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.sql"
            write_file(path, "old SQL")
            write_file(path, "select 1;\n")
            self.assertEqual(path.read_text(), "select 1;\n")
            write_file(path, "select 2;\n", mode="create")
            self.assertEqual(path.read_text(), "select 1;\n")

    def test_generators_replace_sql_without_reference_files(self):
        for in_memory in (False, True):
            for kind in ("model", "int", "src", "stb"):
                with self.subTest(in_memory=in_memory, kind=kind):
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        output = root / "models"
                        references = root / "references"
                        model_name = "combined_patients" if kind == "stb" else "patients"
                        model = output / f"{model_name}.sql"
                        for column in ("old_column", "new_column"):
                            content = (
                                "variable_name,data_type\n"
                                f"{column},string\n"
                            )
                            if in_memory:
                                source = InMemoryDataDictionary(
                                    "patients_dd.csv", content.encode()
                                )
                            else:
                                source = root / "patients_dd.csv"
                                source.write_text(content)

                            if kind in ("model", "int"):
                                generate_sql_models(
                                    source, output,
                                    reference_dir=references if in_memory else None,
                                    int_descriptors=kind == "int",
                                )
                            elif kind == "src":
                                generate_src_models(source, output, source_name="raw")
                            else:
                                generate_stb_union_models(source, output)

                            sql = model.read_text()
                            if kind == "stb":
                                self.assertIn("combined_union_from_current_model", sql)
                            else:
                                self.assertIn(column, sql)
                                if column == "new_column":
                                    self.assertNotIn("old_column", sql)
                            self.assertEqual(list(output.iterdir()), [model])
                            self.assertFalse(references.exists())
                            model.write_text("stale hand-edited SQL")

    def test_from_clause_template_base_name_excludes_table_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "accesspolicy_dd.csv"
            source.write_text("variable_name,data_type\nid,string\n")
            output = root / "models"

            generate_sql_models(
                source, output,
                table_prefix="inc_access",
                from_clause_template="{{ ref('inc_program_{base_name}') }} -- {table_name}",
            )

            sql = (output / "inc_access_accesspolicy.sql").read_text()
            self.assertIn(
                "from {{ ref('inc_program_accesspolicy') }} -- inc_access_accesspolicy",
                sql,
            )

    def test_program_projection_uses_dynamic_program_ref_and_integer_study_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "activitydefinition_dd.csv"
            source.write_text(
                "variable_name,data_type\n"
                "activity_definition_id,string\n"
                "name,string\n"
                "description,string\n"
                "access_policy_id,string\n"
                "study_id,string\n",
                encoding="utf-8",
            )
            output = root / "models"

            generate_sql_models(
                source,
                output,
                table_prefix="kf_access",
                program_ref_prefix="kf_program",
            )

            sql = (output / "kf_access_activitydefinition.sql").read_text(
                encoding="utf-8"
            )
            self.assertEqual(
                sql,
                "{{ config(materialized='table') }}\n"
                "{%- set program_ref = "
                "generate_source_ref_from_current_model("
                "prefix='kf_program') -%}\n\n"
                "select\n"
                '    activity_definition_id::text as "activity_definition_id",\n'
                '    name::text as "name",\n'
                '    description::text as "description",\n'
                '    access_policy_id::text as "access_policy_id",\n'
                '    study_id::integer as "study_id"\n'
                "from {{ program_ref }}\n",
            )

    def test_int_descriptor_keeps_external_id_as_a_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "aliquot_dd.csv"
            source.write_text(
                "variable_name,data_type\n"
                "aliquot_id,string\n"
                "external_id,string\n"
                "participant_external_id,string\n"
                "sample_id,string\n",
                encoding="utf-8",
            )
            output = root / "models"

            generate_sql_models(source, output, int_descriptors=True)

            sql = (output / "aliquot.sql").read_text(encoding="utf-8")
            self.assertIn("-- null::text as aliquot_id,", sql)
            self.assertIn("null::text as external_id,", sql)
            self.assertIn("null::text as participant_external_id,", sql)
            self.assertIn("-- null::text as sample_id,", sql)
            self.assertIn("null::text as aliquot_descriptor", sql)

    def test_src_sql_preserves_source_names_and_normalizes_aliases(self):
        cases = [
            ("ID", "", '"ID"::text as id'),
            ("MiXeD_Name", "", '"MiXeD_Name"::text as mixed_name'),
            ("Visit Date", "", '"Visit Date"::text as visit_date'),
            ('Header "quoted"', "", '"Header ""quoted"""::text as header_quoted'),
            ("Renamed", "SourceID", '"SourceID"::text as renamed'),
            ("MixedCase", "mixedcase", '"mixedcase"::text as mixedcase'),
        ]
        formats = (
            ("ftd_dd", "variable_name"),
            ("pipeline_format", "variable_name"),
            ("src_type1", "Variable Name"),
        )

        for dd_format, name_column in formats:
            for in_memory in (False, True):
                for has_source_column in (False, True):
                    with self.subTest(
                        dd_format=dd_format,
                        in_memory=in_memory,
                        has_source_column=has_source_column,
                    ):
                        selected_cases = cases if has_source_column else cases[:4]
                        content = io.StringIO(newline="")
                        writer = csv.writer(content)
                        writer.writerow(
                            [name_column, "src_variable_name"]
                            if has_source_column else [name_column]
                        )
                        for name, source_name, _ in selected_cases:
                            writer.writerow(
                                [name, source_name] if has_source_column else [name]
                            )

                        with tempfile.TemporaryDirectory() as tmp:
                            root = Path(tmp)
                            if in_memory:
                                source = InMemoryDataDictionary(
                                    "patients_dd.csv", content.getvalue().encode()
                                )
                            else:
                                source = root / "patients_dd.csv"
                                source.write_text(content.getvalue(), encoding="utf-8")
                            output = root / "models"
                            generate_src_models(
                                source, output, source_name="raw", dd_format=dd_format
                            )

                            expected = (
                                "{{ config(materialized='table') }}\n\n"
                                "select\n    "
                                + ",\n    ".join(case[2] for case in selected_cases)
                                + "\nfrom {{ source('raw', 'patients') }}\n"
                            )
                            self.assertEqual(
                                (output / "patients.sql").read_text(encoding="utf-8"),
                                expected,
                            )

    def test_src_filename_prefix_is_independent_of_source_table_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bp_age_event_latency_dd.csv"
            source.write_text(
                "variable_name,data_type\niD,string\n",
                encoding="utf-8",
            )
            output = root / "models"

            generate_src_models(
                source,
                output,
                source_name="inc_brainpower_raw",
                table_prefix="inc_brainpowers_raw",
                sql_file_prefix="inc_brainpowers_src",
            )

            sql = (output / "inc_brainpowers_src_bp_age_event_latency.sql").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                "source('inc_brainpower_raw', 'inc_brainpowers_raw_bp_age_event_latency')",
                sql,
            )
            self.assertEqual(len(list(output.glob("*.sql"))), 1)

    def test_regular_sql_keeps_normalized_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "patients_dd.csv"
            source.write_text(
                "variable_name,src_variable_name\nID,\nRenamed,SourceID\n",
                encoding="utf-8",
            )
            generate_sql_models(source, root / "models")
            self.assertEqual(
                (root / "models" / "patients.sql").read_text(encoding="utf-8"),
                'select\n    id::text as "id",\n    SourceID::text as "renamed"\n',
            )

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "openpyxl is required")
    def test_src_sql_preserves_names_from_xlsx(self):
        import pandas as pd

        content = io.BytesIO()
        pd.DataFrame(
            {
                "variable_name": ["ID", "Renamed"],
                "src_variable_name": [None, "SourceID"],
            }
        ).to_excel(content, index=False, engine="openpyxl")

        for in_memory in (False, True):
            with self.subTest(in_memory=in_memory):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    if in_memory:
                        source = InMemoryDataDictionary(
                            "patients_dd.xlsx", content.getvalue()
                        )
                    else:
                        source = root / "patients_dd.xlsx"
                        source.write_bytes(content.getvalue())

                    output = root / "models"
                    generate_src_models(source, output, source_name="raw")
                    sql = (output / "patients.sql").read_text(encoding="utf-8")
                    self.assertIn('"ID"::text as id', sql)
                    self.assertIn('"SourceID"::text as renamed', sql)

    def test_src_cli_preserves_names_from_local_and_release_inputs(self):
        release_content = io.BytesIO()
        with zipfile.ZipFile(release_content, "w") as archive:
            archive.writestr(
                "nested/release_dd.csv",
                "variable_name,src_variable_name\nID,\nRenamed,SourceID\n",
            )

        for refresh in (False, True):
            with self.subTest(refresh=refresh):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    local = root / "local_dd.csv"
                    local.write_text("variable_name\nLocalID\n", encoding="utf-8")
                    output = root / "models"
                    argv = [
                        "generate_src_models",
                        "-i", str(local),
                        "-o", str(output),
                        "-s", "raw",
                        "--release", "https://example.invalid/repo", "bundle.zip",
                    ]
                    if refresh:
                        argv.append("--refresh")

                    with patch("sys.argv", argv), patch(
                        "dbt_pipeline_utils.p_utils.github_release.pull_release_asset_to_memory",
                        return_value=release_content.getvalue(),
                    ) as pull:
                        generate_src_models_cli()

                    pull.assert_called_once_with(
                        "https://example.invalid/repo", "bundle.zip",
                        tag="latest", token=None, refresh=refresh,
                    )
                    release_sql = (output / "release.sql").read_text(encoding="utf-8")
                    local_sql = (output / "local.sql").read_text(encoding="utf-8")
                    self.assertIn('"ID"::text as id', release_sql)
                    self.assertIn('"SourceID"::text as renamed', release_sql)
                    self.assertIn('"LocalID"::text as localid', local_sql)


if __name__ == "__main__":
    unittest.main()
