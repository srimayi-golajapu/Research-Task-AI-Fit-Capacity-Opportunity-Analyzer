# SciNet Source Relationship Findings

## 1. Source Datasets

| Dataset | Rows | Columns |
|---|---:|---:|
| tasks.csv | 7,262 | 7 |
| task_dimensions.csv | 7,262 | 36 |
| task_hours_per_year.csv | 26,803 | 23 |
| task_time.csv | 18,283 | 9 |
| task_ratings.csv | 26,803 | 9 |
| task_activity_assignments.csv | 6,956 | 4 |

## 2. Tasks and Dimensions Alignment

- Both datasets contain 7,262 records.
- All five key columns match in the same order.
- Verified using positional comparison.
- No duplicate composite keys were found in either dataset.

Key columns:
- task
- level
- domain
- field
- subfield

## 3. Relationship Between tasks.csv and task_hours_per_year.csv

The datasets have different levels of detail.

| Level | Matching columns | Matched records |
|---|---|---:|
| Universal | task | 30 |
| Domain | task, level, domain | 134 |
| Field | task, level, domain, field | 321 |
| Subfield | task, level, domain, field, subfield | 6,777 |

### Observations

- Universal-level task names exist in both datasets.
- Domain-level records match using task, level, and domain.
- Field-level records match using task, level, domain, and field.
- Subfield-level records match using all five key columns.
- Domain and field records in tasks.csv have broader scope, while task_hours_per_year.csv contains more detailed records associated with specific research areas.

## 4. Duplicate Checks

- tasks.csv: 0 duplicate composite keys.
- task_hours_per_year.csv: 0 duplicate composite keys.
- No duplicate full rows were found in the inspected source datasets.

## 5. Missing Values

Important findings:

- tasks.csv contains missing domain, field, subfield, and expert_input values.
- task_hours_per_year.csv contains missing values in several secondary estimation columns.
- task_dimensions.csv contains one missing elo_opus5 value and missing values in pasteur_understanding and pasteur_use.

Missing values should be handled according to their meaning rather than automatically replaced with zero.

## 6. Ingestion Considerations

1. Preserve the original CSV files.
2. Validate composite keys before joining datasets.
3. Use the appropriate matching columns for each level.
4. Avoid joining records using task name alone where multiple research areas exist.
5. Preserve missing values unless a documented transformation rule applies.
6. Investigate time-estimation aggregation rules before calculating total annual hours.

## 7. Status

Source inspection and initial relationship checks completed.

Next phase: Build SciNet ingestion, validation, and normalization modules.
