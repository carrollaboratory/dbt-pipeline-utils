{% macro grant_schema_role_access(target_schema, users_role) %}
{% if execute %}
    {#
      Use explicit table privileges instead of GRANT ALL to follow least-privilege.
      In Postgres, ALL TABLE privileges also include TRIGGER, REFERENCES, and TRUNCATE,
      which are broader than required for this workflow.
    #}
{% set table_privileges = 'select, insert, update, delete' %}
{% set sequence_privileges = 'usage, select' %}

{% if not target_schema %}
{% do exceptions.raise_compiler_error('grant_schema_role_access: target_schema is required') %}
{% endif %}

{% if not users_role %}
      {% do exceptions.raise_compiler_error('grant_schema_role_access: users_role is required') %}
    {% endif %}

    {% set schema_name = target_schema %}
    {% set grantee_name = users_role %}
    {% set quoted_schema = adapter.quote(schema_name) %}
    {% set grantee = adapter.quote(grantee_name) %}

    {% set schema_granted_sql %}
      select
        has_schema_privilege('{{ grantee_name }}', '{{ schema_name }}', 'USAGE') as has_usage,
        has_schema_privilege('{{ grantee_name }}', '{{ schema_name }}', 'CREATE') as has_create
    {% endset %}
    {% set schema_granted_result = run_query(schema_granted_sql) %}
    {% set schema_usage_granted = false %}
    {% set schema_create_granted = false %}

    {% if schema_granted_result is not none and schema_granted_result.rows | length > 0 %}
      {% set schema_usage_granted = schema_granted_result.rows[0][0] %}
      {% set schema_create_granted = schema_granted_result.rows[0][1] %}
    {% endif %}

    {% if not schema_usage_granted or not schema_create_granted %}
      {% do log('Applying ' ~ grantee_name ~ ' grants on schema ' ~ schema_name, info=True) %}

      {% do run_query("grant usage on schema " ~ quoted_schema ~ " to " ~ grantee) %}
      {% do run_query("grant create on schema " ~ quoted_schema ~ " to " ~ grantee) %}
      {% do run_query("grant " ~ table_privileges ~ " on all tables in schema " ~ quoted_schema ~ " to " ~ grantee) %}
      {% do run_query("grant " ~ sequence_privileges ~ " on all sequences in schema " ~ quoted_schema ~ " to " ~ grantee) %}

      {% do run_query("alter default privileges in schema " ~ quoted_schema ~ " grant " ~ table_privileges ~ " on tables to " ~ grantee) %}
      {% do run_query("alter default privileges in schema " ~ quoted_schema ~ " grant " ~ sequence_privileges ~ " on sequences to " ~ grantee) %}
    {% else %}
      {% do log('Skipping grants for schema ' ~ schema_name ~ ' (USAGE and CREATE already granted for role ' ~ grantee_name ~ ')', info=True) %}
    {% endif %}
  {% endif %}

{{ return('') }}
{% endmacro %}
