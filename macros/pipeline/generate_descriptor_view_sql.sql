{%- macro generate_descriptor_view_sql(table_prefix='', study_global_id='') -%}

{%- set descriptor_sources = [
    {'resource_model': 'Consent', 'relation_name': 'accesspolicy', 'descriptor_column': 'access_policy_descriptor'},
    {'resource_model': 'Patient', 'relation_name': 'demographics', 'descriptor_column': 'subject_descriptor'},
    {'resource_model': 'ResearchStudy', 'relation_name': 'demographics', 'descriptor_column': 'study_descriptor'},
    {'resource_model': 'Family', 'relation_name': 'family', 'descriptor_column': 'family_descriptor'},
    {'resource_model': 'DocumentReference', 'relation_name': 'file', 'descriptor_column': 'file_descriptor'},
    {'resource_model': 'List', 'relation_name': 'dataset', 'descriptor_column': 'dataset_descriptor'},
    {'resource_model': 'Encounter', 'relation_name': 'encounter', 'descriptor_column': 'encounter_descriptor'},
    {'resource_model': 'Observation', 'relation_name': 'subjectassertion', 'descriptor_column': 'assertion_descriptor'}
] -%}


{%- set curated_sources = [] -%}
{%- for source_row in descriptor_sources -%}
{%- set source_identifier = table_prefix ~ source_row['relation_name'] -%}
{%- if execute -%}
        {%- set descriptor_relation = adapter.get_relation(
            database=this.database,
            schema=this.schema,
            identifier=source_identifier
        ) -%}
{%- if descriptor_relation is not none -%}
                {%- do curated_sources.append({'resource_model': source_row['resource_model'], 'relation': descriptor_relation, 'descriptor_column': source_row['descriptor_column']}) -%}
            {%- endif -%}
        {%- else -%}
        {%- set descriptor_relation = api.Relation.create(
            database=this.database,
            schema=this.schema,
            identifier=source_identifier
        ) -%}
{%- do curated_sources.append({'resource_model': source_row['resource_model'], 'relation': descriptor_relation, 'descriptor_column': source_row['descriptor_column']}) -%}
{%- endif -%}
{%- endfor -%}

{%- if curated_sources | length == 0 -%}
select
    '{{ study_global_id }}'::text as "studyGlobalId",
    cast(null as text) as "fhirResourceType",
    cast(null as text) as descriptor,
    cast(null as text) as "descriptorState"
where 1 = 0
    {%- else -%}

with int_descriptors as (
{%- for source_row in curated_sources %}
            
    select
        '{{ source_row['resource_model'] }}'::text as resource_model,
        {{ source_row['descriptor_column'] }}::text as descriptor
    from {{ source_row['relation'] }}
{% if not loop.last %}
    union all

{% endif %}
{%- endfor %}
),

unique_descriptors as (
    select distinct
        resource_model,
        descriptor
    from int_descriptors
    where nullif(trim(descriptor), '') is not null
),

existing_global_ids as (
    select distinct
        "fhirResourceType"::text as resource_model,
        descriptor::text as descriptor
    from {{ source('brainpower', 'global_ids') }}
    where "studyId" = '{{ study_global_id }}'
)

select
    '{{ study_global_id }}'::text as "studyGlobalId",
    u.resource_model as "fhirResourceType",
    u.descriptor as descriptor,
    'ACTIVE'::text as "descriptorState"
from unique_descriptors as u
left join existing_global_ids as g
  on u.resource_model = g.resource_model
 and u.descriptor = g.descriptor
where g.descriptor is null
order by u.resource_model, u.descriptor
{%- endif -%}

{%- endmacro -%}
