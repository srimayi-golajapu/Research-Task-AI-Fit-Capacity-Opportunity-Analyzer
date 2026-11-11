
import pandas as pd
from pathlib import Path

DATA_PATH = Path("data/raw/scinet/")

files = [
    "tasks.csv",
    "task_time.csv",
    "task_hours_per_year.csv",
    "task_ratings.csv",
    "task_dimensions.csv",
    "task_activity_assignments.csv"
]

for file in files:
    print("\n" + "=" * 60)
    print(f"FILE: {file}")
    print("=" * 60)

    df = pd.read_csv(DATA_PATH / file)

    print("Shape:", df.shape)
    print("\nColumns:")
    print(df.columns.tolist())

    print("\nData types:")
    print(df.dtypes)

    print("\nMissing values:")
    print(df.isnull().sum())

    print("\nDuplicate rows:")
    print(df.duplicated().sum())

    print("\nFirst five records:")
    print(df.head())
