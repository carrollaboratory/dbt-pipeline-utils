import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
