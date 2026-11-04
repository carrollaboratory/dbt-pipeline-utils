import hashlib
import re
import tempfile
import unittest
from pathlib import Path

import yaml

from dbt_pipeline_utils.p_utils.dd_sources import InMemoryDataDictionary
from dbt_pipeline_utils.p_utils.models_yml import build_model_entry, generate_models_yml
from dbt_pipeline_utils.p_utils.sources_yml import build_source_table_entry, generate_sources_yml


class ColumnDescriptionTests(unittest.TestCase):
    def test_doc_id_length_boundary(self):
        columns = [{
            "variable_name": "ID",
            "formatted_variable_name": "id",
            "description": "Identifier",
        }]
        for kind in ("model", "source"):
            for length in (59, 60, 61):
                with self.subTest(kind=kind, length=length):
                    namespace = "raw_" if kind == "source" else ""
                    table_name = "a" * (length - len(namespace) - len("_id"))
                    full_id = f"{namespace}{table_name}_id"
                    if kind == "source":
                        entry, blocks = build_source_table_entry(
                            table_name, columns, source_name="raw"
                        )
                    else:
                        entry, blocks = build_model_entry(table_name, columns)
                    expected = full_id if length <= 60 else (
                        f'{full_id[:51]}_{hashlib.md5(full_id.encode()).hexdigest()[:8]}'
                    )
                    self.assertEqual(blocks, [(expected, "Identifier")])
                    self.assertEqual(
                        entry["columns"][0]["description"], f'{{{{ doc("{expected}") }}}}'
                    )
                    self.assertLessEqual(len(expected), 60)

    def test_doc_ids_use_unprefixed_table_and_column_names(self):
        content = (
            "variable_name,description\n"
            "External Identifier,External identifier description\n"
            "External Identifier Type,External identifier type description\n"
        )
        prefixes = (
            "inc_brainpower_int",
            "inc_" + "long_study_name_" * 5 + "int",
        )
        for kind in ("model", "source"):
            for in_memory in (False, True):
                for prefix in prefixes:
                    with self.subTest(kind=kind, in_memory=in_memory, prefix=prefix):
                        with tempfile.TemporaryDirectory() as tmp:
                            root = Path(tmp)
                            if in_memory:
                                source = InMemoryDataDictionary(
                                    "patients_dd.csv", content.encode()
                                )
                            else:
                                source = root / "patients_dd.csv"
                                source.write_text(content, encoding="utf-8")
                            output = root / "schema.yml"
                            docs = root / "descriptions.md"
                            kwargs = {
                                "table_names": {"patients_dd": "participants"},
                                "table_prefix": prefix,
                                "docs_output": docs,
                            }
                            if kind == "model":
                                generate_models_yml(source, output, **kwargs)
                            else:
                                generate_sources_yml(
                                    source, output, source_name="raw", schema="raw",
                                    **kwargs,
                                )
                            data = yaml.safe_load(output.read_text())
                            table = (
                                data["models"][0] if kind == "model"
                                else data["sources"][0]["tables"][0]
                            )
                            self.assertEqual(table["name"], f"{prefix}_participants")
                            doc_namespace = (
                                table["name"] if kind == "model"
                                else "raw_participants"
                            )
                            expected_ids = [
                                f'{doc_namespace}_external_identifier',
                                f'{doc_namespace}_external_identifier_type',
                            ]
                            expected_ids = [
                                doc_id if len(doc_id) <= 60 else
                                f'{doc_id[:51]}_{hashlib.md5(doc_id.encode()).hexdigest()[:8]}'
                                for doc_id in expected_ids
                            ]
                            self.assertTrue(all(len(doc_id) <= 60 for doc_id in expected_ids))
                            self.assertEqual(len(set(expected_ids)), 2)
                            self.assertEqual(
                                [col["description"] for col in table["columns"]],
                                [f'{{{{ doc("{doc_id}") }}}}' for doc_id in expected_ids],
                            )
                            doc_text = docs.read_text()
                            self.assertEqual(
                                re.findall(r"\{% docs (\w+) %\}", doc_text),
                                expected_ids,
                            )
                            self.assertIn("External identifier description", doc_text)
                            if kind == "model":
                                generate_models_yml(source, output, **kwargs)
                            else:
                                generate_sources_yml(
                                    source, output, source_name="raw", schema="raw",
                                    **kwargs,
                                )
                            self.assertEqual(docs.read_text(), doc_text)

    def test_source_doc_ids_exclude_table_prefix(self):
        source = InMemoryDataDictionary(
            "bp_age_event_latency_dd.csv",
            b"variable_name,description\niD,Identifier\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "sources.yml"
            docs = root / "descriptions.md"

            generate_sources_yml(
                source,
                output,
                source_name="inc_brainpower_raw",
                schema="inc_brainpowers_raw",
                table_prefix="inc_brainpowers_raw",
                docs_output=docs,
            )

            data = yaml.safe_load(output.read_text())
            table = data["sources"][0]["tables"][0]
            expected_doc_id = "inc_brainpower_raw_bp_age_event_latency_id"
            self.assertEqual(table["name"], "inc_brainpowers_raw_bp_age_event_latency")
            self.assertEqual(table["identifier"], "bp_age_event_latency")
            self.assertEqual(
                table["columns"][0]["description"],
                f'{{{{ doc("{expected_doc_id}") }}}}',
            )
            self.assertIn(f"{{% docs {expected_doc_id} %}}", docs.read_text())

    def test_source_doc_ids_are_unique_across_sources_and_tables(self):
        sources = [
            InMemoryDataDictionary(
                f"{table}_dd.csv",
                f"variable_name,description\nID,{table} identifier\n".encode(),
            )
            for table in ("patients", "samples")
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "sources.yml"
            docs = root / "descriptions.md"
            for source_name in ("inc_brainpower_src", "kf_study_src"):
                generate_sources_yml(
                    sources, output, source_name=source_name,
                    schema="same_schema", docs_output=docs,
                )
            data = yaml.safe_load(output.read_text())
            expected_ids = []
            for source in data["sources"]:
                for table in source["tables"]:
                    doc_id = f'{source["name"]}_{table["name"]}_id'
                    expected_ids.append(doc_id)
                    self.assertEqual(
                        table["columns"][0]["description"],
                        f'{{{{ doc("{doc_id}") }}}}',
                    )
            self.assertEqual(len(set(expected_ids)), 4)
            self.assertEqual(
                re.findall(r"\{% docs (\w+) %\}", docs.read_text()),
                expected_ids,
            )


if __name__ == "__main__":
    unittest.main()
