# Profiling macros quickstart

Query generators for answering questions like:

- Which datasets fill in which columns?
- Is this column unique? How many distinct values does it have?
- Does each `subject_id` belong to exactly one `family_id`?
- If I `left join` table A to table B, will I lose rows or duplicate them?

| Tool | What it does | Where |
| --- | --- | --- |
| `profile_*` macros | Generate a `SELECT` query. Nothing is written to the database. | [`profile_queries.sql`](../profile_queries.sql) |
| `store_profile` | Profiles every column of a table and **saves** the result to a `profile_<table>` table, keeping history. | [`store_profile.sql`](../store_profile.sql) |

The `profile_*` macros need `dbt-labs/dbt_utils` installed in the pipeline.
Call them with the package namespace from an analysis file or inline:

```bash
dbt show --limit 100 --inline "{{ dbt_pipeline_utils.profile_distinct_counts(ref('samples'), group_by='study_id') }}"
dbt compile --inline "{{ dbt_pipeline_utils.profile_distinct_counts(ref('samples')) }}"   # SQL only
```

`dbt show` truncates wide tables; add `--output json` to see every column.

> **Before you start:** the tables you profile must already be built (`dbt run`).
> The macros look up column names in the database, so they can't run against
> tables that don't exist yet.

---

## 1. The profiling macros

Arguments common to most macros:

| Argument | Meaning |
| --- | --- |
| `relation` | The table to profile, usually `ref('model_name')`. |
| `group_by` | A column name, or list of names, to get one result row per group (e.g. per dataset). `none` = one row for the whole table. |
| `include` | Only profile these columns. |
| `except` | Profile every column except these. |
| `blank_as_null` | `true` treats empty or whitespace-only strings as NULL. Use it when a column looks populated but contains `''`. |

### 1.1 `profile_column_presence`: which groups fill in which columns

```sql
{{ dbt_pipeline_utils.profile_column_presence(
    ref('subjects'),
    group_by='ingest_provenance',    -- default
    measure='any',                   -- 'any' | 'count' | 'proportion'
    blank_as_null=false
) }}
```

The output has one row per group and one column per profiled column, plus `n_rows`:

| `measure` | Each cell means |
| --- | --- |
| `any` | `1` = at least one non-null value in this group, `0` = every value is null |
| `count` | number of non-null rows |
| `proportion` | share of rows that are non-null (0 to 1) |

**How to read it:** a column that is `0` for most datasets is probably
dataset-specific. If two columns are never `1` in the same dataset, they may
hold the same information under different names (candidates for `coalesce`).

### 1.2 `profile_distinct_counts`: how many distinct values

```sql
{{ dbt_pipeline_utils.profile_distinct_counts(ref('subjects'), group_by=none) }}
```

The output has `n_rows` plus, for each column, the number of distinct
**non-null** values.

**How to read it:**

- value = `n_rows`: the column has a different value in every row, a
  candidate unique key (check for nulls with `profile_column_presence`,
  `measure='count'`).
- value = `1`: constant. With `group_by` set to a dataset column, this
  is a dataset-level attribute.
- value much smaller than `n_rows`: a category or code column.

### 1.3 `profile_column_relationships`: 1:1, 1:N, N:1 or N:N

```sql
{{ dbt_pipeline_utils.profile_column_relationships(
    ref('subjects'),
    columns=['subject_id', 'family_id', 'sex'],
    group_by=none
) }}
```

The output has one row per pair of columns (`column_a`, `column_b`):

| Column | Meaning |
| --- | --- |
| `distinct_a`, `distinct_b` | distinct values in each column (**NULL counts as a value here**) |
| `distinct_pairs` | distinct (a, b) combinations |
| `relationship` | see below |
| `note` | `one column is constant` or `both columns unique per row`: the relationship is technically true but not informative |

| `relationship` | Meaning | Example |
| --- | --- | --- |
| `1:1` | each a has one b, and each b has one a | `subject_id` and an alternate subject ID |
| `N:1` | each a has exactly one b; a b can have many a's | `subject_id` → `family_id` |
| `1:N` | the reverse of N:1 | `family_id` → `subject_id` |
| `N:N` | some a's have several b's **and** some b's have several a's | usually a data problem, or the columns aren't related |

To check something like "every subject is in exactly one family", look for
`N:1` (or `1:1`). An unexpected `N:N` means some values break the rule; use
`profile_column_pair` to find them.

Keep `columns` short (under about 10). The number of pairs grows quickly:
10 columns = 45 pairs.

### 1.4 `profile_column_pair`: which values break the rule

```sql
{{ dbt_pipeline_utils.profile_column_pair(
    ref('subjects'),
    column_a='subject_id',
    column_b='family_id',
    group_by='study_id',
    max_examples=10
) }}
```

The output lists only the problem values:

| Column | Meaning |
| --- | --- |
| `direction` | `subject_id -> family_id`: one subject with several families. `family_id -> subject_id`: one family with several subjects. |
| `value` | the value that maps to more than one value |
| `n_other_values` | how many different values it maps to |
| `other_values` | up to `max_examples` of them |

**An empty result means 1:1.** For an expected N:1 (e.g. many subjects per
family), rows in the `family_id -> subject_id` direction are normal; only
rows in the `subject_id -> family_id` direction are problems.

### 1.5 `profile_join_coverage`: will my left join drop or duplicate rows?

```sql
{{ dbt_pipeline_utils.profile_join_coverage(
    ref('samples'),                      -- left table
    ref('subjects'),                      -- right table
    left_columns=['subject_id', 'study_id'],
    right_columns=none,                          -- defaults to left_columns
    left_where=none, right_where=none,           -- optional filters, e.g. "sample_type = 'DNA'"
    group_by='study_id',               -- must be one of left_columns
    label='sample -> subject'
) }}
```

This simulates `left join right on left_columns = right_columns` without
running it. You can combine several checks with `union all`.

| Column | Meaning | What to look for |
| --- | --- | --- |
| `left_rows` | rows in the left table | |
| `left_keys` / `left_keys_matched` | distinct left keys / how many found a match | |
| `left_rows_unmatched` | left rows with **no** match (orphans) | `> 0`: these rows get NULLs from the right side; an inner join would drop them |
| `left_rows_null_key` | unmatched rows whose key contains a NULL | `> 0`: missing IDs, not just wrong IDs |
| `right_keys` / `right_keys_unmatched` | distinct right keys / how many nothing on the left points to | often fine (e.g. subjects with no samples) |
| `max_left_rows_per_key` | most left rows sharing one key | |
| `max_right_rows_per_key` | most right rows sharing one key | `> 1`: the join **fans out** (duplicates) |
| `rows_after_left_join` | rows the left join would return | |
| `rows_added_by_join` | `rows_after_left_join - left_rows` | **should be 0.** `> 0` means duplicates |

A clean lookup join has `rows_added_by_join = 0`,
`max_right_rows_per_key = 1` and `left_rows_unmatched = 0`.

---

## 2. `store_profile`: save a full column profile

`store_profile` is a run-operation: it runs immediately and writes a table
instead of returning a query. Use it to keep a record of a table's profile
over time.

```bash
dbt run-operation dbt_pipeline_utils.store_profile --args '{"profile_schema": "main", "profile_table": "subjects"}'
```

Optional args:

| Arg | Meaning |
| --- | --- |
| `profile_include_columns` / `profile_exclude_columns` | lists of columns (use only one of them) |
| `profile_where_clause` | e.g. `"study_id = 'study_a'"` |
| `profile_group_by` | list of columns; profiles each group separately |
| `adhoc_schema` / `adhoc_table` | where to write the result (default: same schema, `profile_<table>`) |

Per-dataset example:

```bash
dbt run-operation dbt_pipeline_utils.store_profile --args '{"profile_schema": "main", "profile_table": "subjects", "profile_group_by": ["study_id"]}'
```

Read the result:

```sql
select * from main.profile_subjects order by profiled_at desc, column_name
```

The result table has one row per column (per group):

| Column | Meaning |
| --- | --- |
| `column_name`, `data_type` | the profiled column |
| `row_count` | rows in the table (or group) |
| `not_null_proportion` | share of rows that are non-null |
| `distinct_count`, `distinct_proportion` | distinct values, and distinct values ÷ rows |
| `is_unique` | `true` if no value repeats **and** there are no NULLs |
| `min`, `max` | smallest / largest value **compared as text** (so `'10' < '9'`) |
| `avg`, `median`, `std_dev_*` | numeric columns only; NULL for other types |
| `profiled_at` | when the row was written |

**History:** each run inserts a row only for columns whose profile changed
since the last run. To get the current profile, take the latest `profiled_at`
for each `column_name`.

---

## 3. Gotchas

- **Blank strings aren't NULL.** A column of `''` counts as populated and as
  one distinct value. Use `blank_as_null=true` when that matters.
- **NULL handling differs between macros.** `profile_distinct_counts` ignores
  NULLs; `profile_column_relationships` treats NULL as a value, so a column
  that is half NULL can still show `1:1`.
- **Tables must exist.** Run `dbt run -s <model>` first. A "No columns
  selected" error usually means the table isn't built or `include` has a typo.
- **Join keys must match case and type.** `profile_join_coverage` compares
  values exactly, like the real join does.
