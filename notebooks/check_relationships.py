import pandas as pd
from pathlib import Path

DATA_PATH = Path("C:\\Users\\Acer\\Downloads\\scinet-backup\\data")

tasks_df = pd.read_csv(DATA_PATH / "tasks.csv")
dimensions_df = pd.read_csv(DATA_PATH / "task_dimensions.csv")
task_hours_per_year_df = pd.read_csv(DATA_PATH / "task_hours_per_year.csv")

key_columns = ["task", "level", "domain", "field", "subfield"]

print("\nDATASET SHAPES")
print("tasks.csv:", tasks_df.shape)
print("task_dimensions.csv:", dimensions_df.shape)
print("task_hours_per_year.csv:", task_hours_per_year_df.shape)

print("\nTASKS AND DIMENSIONS ALIGNMENT")
print(
    "All five key columns match in order:",
    tasks_df[key_columns].equals(dimensions_df[key_columns])
)

print("\nDUPLICATE COMPOSITE KEYS")
print(
    "tasks.csv:",
    tasks_df.duplicated(subset=key_columns).sum()
)
print(
    "task_hours_per_year.csv:",
    task_hours_per_year_df.duplicated(subset=key_columns).sum()
)

tasks_keys = tasks_df[key_columns].drop_duplicates()
hours_keys = task_hours_per_year_df[key_columns].drop_duplicates()

comparison_df = tasks_keys.merge(
    hours_keys,
    on=key_columns,
    how="outer",
    indicator=True
)

unmatched_in_tasks = comparison_df[
    comparison_df["_merge"] == "left_only"
]

unmatched_in_hours = comparison_df[
    comparison_df["_merge"] == "right_only"
]

matched_keys = comparison_df[
    comparison_df["_merge"] == "both"
]

print("\nCOMPOSITE KEY COMPARISON")
print("Matched keys:", len(matched_keys))
print("Keys only in tasks.csv:", len(unmatched_in_tasks))
print("Keys only in task_hours_per_year.csv:", len(unmatched_in_hours))

print("\nFIRST 10 KEYS ONLY IN tasks.csv")
#print(unmatched_in_tasks[key_columns].head(10).to_string(index=False))

print("\nFIRST 10 KEYS ONLY IN task_hours_per_year.csv")
#print(unmatched_in_hours[key_columns].head(10).to_string(index=False))

blank_subfields = (
    task_hours_per_year_df["subfield"].isna() |
    task_hours_per_year_df["subfield"].str.strip().eq("")
).sum()
print("Number of blank subfields:", blank_subfields)
print(task_hours_per_year_df["level"].value_counts(dropna=False))
print(task_hours_per_year_df["subfield"].value_counts().head(10))
print(tasks_df["level"].value_counts(dropna=False))
print(
    task_hours_per_year_df.groupby("level")["task"].nunique()
)

other_df = tasks_df[tasks_df["level"] == "universal"]
hours_other_df = task_hours_per_year_df[task_hours_per_year_df["level"] == "universal"]
#merged_other_df = pd.merge(other_df,hours_other_df,on=key_columns,how="left",indicator=True)
#unmatched_other_df = merged_other_df[merged_other_df["_merge"] == "left_only"]
#print("Number of unmatched records:", unmatched_other_df.shape[0])
#print(unmatched_other_df[key_columns].head(10).to_string(index=False))
#universal_tasks = task_hours_per_year_df[task_hours_per_year_df["level"] == "universal"]
#print(universal_tasks[key_columns].head(5).to_string(index=False))


field_tasks = tasks_df[tasks_df["level"] == "field"]
field_hours = task_hours_per_year_df[task_hours_per_year_df["level"] == "field"]
#print("All field tasks exist in task_hours_per_year.csv:",field_hours["task"].isin(field_tasks["task"]).all())
#missing_in_tasks = field_tasks[~field_tasks["task"].isin(field_hours["task"])]
#print("Missing task names:", missing_in_tasks.shape[0])
#print(missing_in_tasks["task"].to_string(index=False))

key_columns = ["task", "level", "domain"]
domain_tasks = tasks_df[tasks_df["level"] == "domain"]
domain_hours = task_hours_per_year_df[task_hours_per_year_df["level"] == "domain"]
domain_tasks_keys= domain_tasks[key_columns].drop_duplicates()
domain_hours_keys= domain_hours[key_columns].drop_duplicates()
domain_comparison = domain_tasks_keys.merge(domain_hours_keys,on=key_columns,how="outer",indicator=True)
print(domain_comparison["_merge"].value_counts())

print("Only in tasks.csv:")
print(
    domain_comparison[
        domain_comparison["_merge"] == "left_only"
    ][key_columns].head().to_string(index=False)
)

print("\nOnly in task_hours_per_year.csv:")
print(
    domain_comparison[
        domain_comparison["_merge"] == "right_only"
    ][key_columns].head().to_string(index=False)
)