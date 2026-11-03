# URI / CURIE Harmonization Work Plan

## Goal

- Many Common Access Model columns must be a full URI, a CURIE (`prefix:id`), or either (LinkML `uri` / `uriorcurie`).
- Examples: `website`, `data_use_accession`, `family_study_focus`, `concept_curie`, and `external_id` on every Record class.
- Source data arrives in mixed shapes (`phs002981`, `dbGaP:phs002981`, `example.org`, `HP:0001631`, `PT-0042`).
- We need one consistent, low-effort way for harmonizers to clean these values, and tests that catch bad ones.
- Everything must work the same on Postgres and DuckDB.

## Decisions

- Two separate problems:
  - CURIE prefixes need a clear definition (base URI) and a FHIR system.
  - Study-local source identifiers need a URI that scopes them to where they came from.
- We do not mint prefixes. We only adopt prefixes that are defined externally (eg Bioregistry).
  - Example: `dbgap` is defined, but only for phs ids. Other dbGaP ids (pht, etc) use the full URI.
- One source of truth seed: `seeds/curie_prefixes.csv`.
  - Columns: `prefix`, `uri`, `fhir_system`, `alias_prefix`.
  - FHIR system rule: the system is the same as `uri` unless `fhir_system` is filled in.
  - Every CURIE prefix used in the data must be in this seed, or the test fails.
- CURIE prefixes use the exact canonical spelling in the prefix seed, matching the model YAML (`CDCREC:1002-5`, `NCIT:C2986`, `edam:data_0582`). The local id keeps its case.
- Study-local ids are minted as URIs, not CURIEs:
  - `https://identifier.includedcc.org/source/{dewrangle study id}/{source id}`
  - Example: `https://identifier.includedcc.org/source/sd-dbaknypgqp/PT-0042`
  - No class segment for now (see gaps).
- Never invent data. Macros only add a prefix or `https://` when the value's shape is known. Anything else passes through unchanged so a test flags it.
- Standard terms (sample type, storage method, conditions) are mapped to CURIEs by our existing term-mapping process before harmonization. Macros only clean them up.
- Harmonizers should do as little upfront data characterization as possible. They run the macro on every URI/CURIE column; values that are already clean pass through unchanged.

## What was built

- Dependent macros, regex helpers, and generic tests:
  [`macros/uri_curie/uri_curie.sql`](../uri_curie.sql).
- Independent macros: `macros/uri_curie/normalize_doi.sql` and
  `macros/uri_curie/source_identifier_uri.sql`.
- Standalone examples: `tests/unit/`. The consuming pipeline supplies
  `seeds/curie_prefixes.csv`.
- `uri_curie_patterns()`
  - Shared regexes for `uri`, `http_uri`, `curie`, and `curie_prefix`.
  - Kept simple on purpose: catches whitespace and missing scheme/host. Not a full RFC 3986 validator.
- `regex_match()`
  - Regex match that works on Postgres and DuckDB.
- `normalize_curie()`
  - Trims and maps case variants/aliases to the exact canonical prefix spelling in the seed.
  - Built-in bare-ID pattern for `dbgap` phs accessions; other prefixes require an explicit `local_id_pattern`.
  - Non-matching bare values pass through unchanged so the format tests can catch them.
- `normalize_doi()` and `valid_doi_format`
  - `normalize_doi` only trims surrounding whitespace; it preserves the bare DOI string used by CAM `do_id`.
  - `valid_doi_format` checks `10.` + a 4-9 digit registrant code + `/` + a non-empty, whitespace-free suffix.
  - A DOI cannot be generated from a study ID alone; it must be assigned by a DOI registration agency.
  - Full URIs and `urn:` values pass through.
- `normalize_http_uri()`
  - Trims, lowercases the scheme, and adds `https://` only to values shaped like `host.tld/...`.
- `source_identifier_uri()`
  - Mints the source URI from a study-local id and the Dewrangle study id.
  - Trims, percent-encodes `% space / ? #`, and returns null for blank ids.
  - Fails at compile time if the study id is not a Dewrangle id.
- Tests
  - `valid_uri_format`: value is a full URI (name matches the other project so their models.yml can be reused).
  - `uri_or_curie_format`: value is a URI or a CURIE (name matches the other project).
  - `valid_http_uri`: value is an http(s) web address.
  - `valid_curie_prefix`: CURIE prefix exists in the seed.
  - `accepted_values_or_uri_or_curie`: for enum-or-CURIE slots (`program`, `organism_type`). Value is in the accepted enum list, or else a URI/CURIE.
  - Unit tests: `uri_curie_patterns_examples__passes`, `source_identifier_uri_examples__passes`.
- Example model: `models/include/brainpower/int/inc_brainpower_int_accesspolicy.sql`
  - `data_use_accession` from the dbGaP column via `normalize_curie(..., default_prefix='dbgap')`.
  - `website` via `normalize_http_uri`.
  - Tests wired in `models/include/brainpower/int/_inc_brainpower_int.yml`.
- Planning sheet: `macros/uri_curie/docs/uri_curie_column_map.csv`
  - Every relevant CAM table/column with a source example, harmonized example, macro call, and tests.

## How a harmonizer uses this

- Find the column in `uri_curie_column_map.csv`.
- Pick the macro by source type:
  - Web address: `normalize_http_uri`.
  - Public accession or mapped standard term: `normalize_curie`.
  - Study-local id (participant, family, sample barcode, visit, REDCap event): `source_identifier_uri`.
  - Already a full URI (s3, drs, https): `normalize_curie` (passes through, trim only).
- For bare dbGaP phs accessions and DOI values, pass `default_prefix` only; the macro supplies the known pattern.
- For other bare accessions, supply a source-specific `local_id_pattern` and only use a prefix present in the seed.
- Add the tests listed in the column map to the model yml.
- Run. Fix test failures by adding a seed prefix (only if externally defined) or adjusting the source mapping.

## Logic gaps and things to revisit

- Class segment in minted URIs
  - Without it, a participant `1234` and a sample `1234` in the same study get the same URI.
  - That is OK for FHIR Identifiers (resource type separates them) but ambiguous as a URI.
  - The macro builds the path from a list, so adding a class (or source table) segment is a one-line change.
  - Adding it later changes every minted URI. We should decide before the first public release.
- Minted base URI
  - `identifier.includedcc.org` does not resolve yet. Changing the domain later also changes every minted URI.
- FHIR system / value split is not built yet
  - CURIE: system = seed `fhir_system` or `uri`; value = local id.
  - Minted URI: system = base up to the study id; value = decoded source id.
  - Other full URIs: no rule yet (likely longest matching seed `uri`).
  - Need to decide whether this lives in dbt or in the FHIR ingest.
- Encoding
  - Only `% space / ? #` are encoded. Other unusual characters pass through. Add more when real data needs it.
- FHIR systems for OBO ontologies
  - Left blank in the seed, so they default to the PURL base (eg `http://purl.obolibrary.org/obo/MONDO_`).
  - FHIR implementations often use a different system (eg the ontology `.owl` URL). Needs a decision.
- Seed values copied from the CAM schema
  - `cdcrec` base URI ends in `/` after a URN, which is unusual.
  - `edam` had no trailing `/` in the schema; the seed adds one so ids append correctly.
- Prefix casing
  - CURIE syntax accepts uppercase and lowercase prefix variants.
  - `normalize_curie` maps known variants to the exact prefix spelling in the seed.
  - `valid_curie_prefix` requires that exact canonical spelling after normalization.
  - The seed's canonical casing should match the model YAML's accepted values.
- Enum-or-CURIE columns (`program`, `organism_type`)
  - Covered by `accepted_values_or_uri_or_curie`. The enum list is passed in the model yml, so it must be kept in sync with the CAM enums by hand.
- Unknown prefixes
  - `normalize_curie` lowercases them and passes them through. `valid_curie_prefix` catches them.

## Next steps

- Load the seed and run the unit tests and example model tests on Postgres and DuckDB.
- Decide on the class segment and the minted base domain before release.
- Decide where FHIR system/value derivation lives.
- Wire `source_identifier_uri` into one `*_external_id` model once the source linkage exists.
- Add seed prefixes only as real data needs them.
