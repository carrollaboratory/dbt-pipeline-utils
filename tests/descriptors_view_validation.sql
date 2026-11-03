{%- set failures = [] -%}
{%- set required_columns = ['studyglobalid', 'fhirresourcetype', 'descriptor', 'descriptorstate'] -%}
{%- set expected_resources = ['Consent', 'List', 'ResearchStudy', 'Organization', 'Patient', 'Family', 'Group', 'FamilyMemberHistory', 'Observation', 'Device', 'MedicationAssertion', 'Specimen', 'Encounter', 'PlanDefinition', 'ActivityDefinition', 'DocumentReference'] -%}
{%- set expected_resources_normalized = expected_resources | map('lower') | list -%}
{%- set expected_resources_sql = "'" ~ expected_resources_normalized | join("','") ~ "'" -%}
{%- set excluded_resources_sql = "'" ~ excluded_resources | join("','") ~ "'" -%}

{%- if execute -%}
{%- for node in graph.nodes.values() | selectattr('resource_type', 'equalto', 'model') -%}
{%- if node.package_name == project_name and node.name.endswith('_descriptors') -%}
{%- set resolved_database = generate_database_name(node.config.database, node) -%}
{%- set resolved_schema = generate_schema_name(node.config.schema, node) -%}
      {%- set relation = adapter.get_relation(
          database=resolved_database,
          schema=resolved_schema,
          identifier=node.alias
      ) -%}
{%- if relation is none -%}
{%- set expected_relation = resolved_database ~ '.' ~ resolved_schema ~ '.' ~ node.alias -%}
{%- do failures.append("select '" ~ node.name ~ "' as model_name, 'model relation not found in warehouse' as failure_reason, 'expected_relation' as failing_column, '" ~ expected_relation ~ "' as failing_value") -%}
{%- continue -%}
{%- endif -%}
{%- set relation_columns = adapter.get_columns_in_relation(relation) -%}
{%- set relation_column_names = relation_columns | map(attribute='name') | map('lower') | list -%}
{%- set relation_column_map = {} -%}
{%- for c in relation_columns -%}
{%- do relation_column_map.update({(c.name | lower): c.name}) -%}
{%- endfor -%}

{%- if relation_columns | length == 0 -%}
{%- do failures.append("select '" ~ node.name ~ "' as model_name, 'no columns found via adapter.get_columns_in_relation' as failure_reason, cast(null as text) as failing_column, cast(null as text) as failing_value") -%}
{%- else -%}
{%- for required_column in required_columns -%}
{%- if required_column not in relation_column_names -%}
{%- do failures.append("select '" ~ node.name ~ "' as model_name, 'missing required column' as failure_reason, '" ~ required_column ~ "' as failing_column, cast(null as text) as failing_value") -%}
{%- else -%}
{%- set quoted_column = adapter.quote(relation_column_map[required_column]) -%}
{%- do failures.append("select '" ~ node.name ~ "' as model_name, 'not_null check failed' as failure_reason, '" ~ required_column ~ "' as failing_column, cast(" ~ quoted_column ~ " as text) as failing_value from " ~ relation ~ " where " ~ quoted_column ~ " is null") -%}
{%- endif -%}
{%- endfor -%}

{%- if 'studyglobalid' in relation_column_names -%}
{%- set quoted_studyglobalid = adapter.quote(relation_column_map['studyglobalid']) -%}
{%- do failures.append("select '" ~ node.name ~ "' as model_name, 'regex check failed (^sd-[a-z0-9]{10}$)' as failure_reason, 'studyglobalid' as failing_column, cast(" ~ quoted_studyglobalid ~ " as text) as failing_value from " ~ relation ~ " where " ~ quoted_studyglobalid ~ " is not null and " ~ quoted_studyglobalid ~ " !~ '^sd-[a-z0-9]{10}$'") -%}
{%- endif -%}

{%- if 'fhirresourcetype' in relation_column_names -%}
{%- set quoted_fhirresourcetype = adapter.quote(relation_column_map['fhirresourcetype']) -%}
{%- do failures.append("select '" ~ node.name ~ "' as model_name, 'accepted values check failed (expected_resources)' as failure_reason, 'fhirresourcetype' as failing_column, cast(" ~ quoted_fhirresourcetype ~ " as text) as failing_value from " ~ relation ~ " where " ~ quoted_fhirresourcetype ~ " is not null and lower(trim(cast(" ~ quoted_fhirresourcetype ~ " as text))) not in (" ~ expected_resources_sql ~ ")") -%}
{%- endif -%}
{%- endif -%}
{%- endif -%}
{%- endfor -%}
{%- endif -%}

{%- if failures | length == 0 -%}
select
  cast(null as text) as model_name,
  cast(null as text) as failure_reason,
  cast(null as text) as failing_column,
  cast(null as text) as failing_value
where 1 = 0
{%- else -%}
{{ failures | join('\nunion all\n') }}
{%- endif -%}
