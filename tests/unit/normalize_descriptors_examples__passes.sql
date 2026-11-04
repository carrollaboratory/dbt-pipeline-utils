with examples as (
  select
    'trim_outer_whitespace' as case_name,
    {{ normalize_descriptors(descriptor_cols=["'   HPO:00001   '"]) }} as actual,
    'HPO:00001' as expected
  union all
  select
    'collapse_inner_whitespace' as case_name,
    {{ normalize_descriptors(descriptor_cols=["'Participant    0001'"]) }} as actual,
    'Participant 0001' as expected
  union all
  select
    'preserve_case_by_default' as case_name,
    {{ normalize_descriptors(descriptor_cols=["'BrainPower.csv'"]) }} as actual,
    'BrainPower.csv' as expected
  union all
  select
    'lowercase_override' as case_name,
    {{ normalize_descriptors(descriptor_cols=[{'expr': "'BrainPower.csv'", 'keep_case': false}]) }} as actual,
    'brainpower.csv' as expected
  union all
  select
    'escape_delimiter_default' as case_name,
    {{ normalize_descriptors(descriptor_cols=["'brain,power.csv'"]) }} as actual,
    'brain/,power.csv' as expected
  union all
  select
    'escape_delimiter_semicolon' as case_name,
    {{ normalize_descriptors(descriptor_cols=["'brain;power.csv'"], delimiter=';') }} as actual,
    'brain/;power.csv' as expected
  union all
  select
    'descriptor_str_default' as case_name,
    {{ normalize_descriptors(descriptor_str='brainpower,v2') }} as actual,
    'brainpower/,v2' as expected
  union all
  select
    'descriptor_str_override_no_escape' as case_name,
    {{ normalize_descriptors(descriptor_str='brainpower,v2', descriptor_str_options={'escape_delimiter': false}) }} as actual,
    'brainpower,v2' as expected
  union all
  select
    'coalesce_expression' as case_name,
    {{ normalize_descriptors(descriptor_cols=["coalesce(null, 'participant_0001')"]) }} as actual,
    'participant_0001' as expected
)

select
  case_name,
  actual,
  expected
from examples
where actual is distinct from expected
