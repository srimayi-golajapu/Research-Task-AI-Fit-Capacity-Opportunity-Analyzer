"""
SciNet Data Loader Module
=========================
Responsible for loading the 6 raw SciNet CSV datasets and organization-specific
task usage datasets.

Preserves original raw CSV datasets without in-place modification.
"""

from pathlib import Path
from typing import Dict, Optional, Union
import pandas as pd

DEFAULT_DATA_PATH = Path("data/raw/scinet/")

SCINET_FILES = {
    "tasks": "tasks.csv",
    "task_time": "task_time.csv",
    "task_hours_per_year": "task_hours_per_year.csv",
    "task_ratings": "task_ratings.csv",
    "task_dimensions": "task_dimensions.csv",
    "task_activity_assignments": "task_activity_assignments.csv",
}


def load_scinet_data(data_dir: Optional[Union[str, Path]] = None) -> Dict[str, pd.DataFrame]:
    """
    Load all six SciNet raw datasets into a dictionary of DataFrames.

    Parameters
    ----------
    data_dir : str or Path, optional
        Path to directory containing SciNet CSV files.
        Defaults to 'data/raw/scinet/'.

    Returns
    -------
    dict of {str: pd.DataFrame}
        Dictionary mapping dataset name to loaded DataFrame.

    Raises
    ------
    FileNotFoundError
        If any of the required SciNet CSV files are missing.
    """
    path = Path(data_dir) if data_dir is not None else DEFAULT_DATA_PATH

    missing_files = []
    for key, filename in SCINET_FILES.items():
        file_path = path / filename
        if not file_path.exists():
            missing_files.append(str(file_path))

    if missing_files:
        raise FileNotFoundError(
            f"Missing required SciNet CSV files ({len(missing_files)}):\n"
            + "\n".join(f"  - {f}" for f in missing_files)
        )

    scinet_data = {}
    for key, filename in SCINET_FILES.items():
        file_path = path / filename
        scinet_data[key] = pd.read_csv(file_path, low_memory=False)

    return scinet_data


def load_organization_data(file_path: Union[str, Path]) -> pd.DataFrame:
    """
    Load an organization-specific task usage CSV file.

    Parameters
    ----------
    file_path : str or Path
        Path to the organization task usage CSV file.

    Returns
    -------
    pd.DataFrame
        Loaded organization DataFrame.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file is empty or cannot be parsed.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Organization data file not found: {path}")

    try:
        df = pd.read_csv(path, low_memory=False)
    except pd.errors.EmptyDataError:
        raise ValueError(f"Organization data file is empty: {path}")

    return df


if __name__ == "__main__":
    print("Testing load_scinet_data()...")
    datasets = load_scinet_data()
    for name, df in datasets.items():
        print(f"  {name:<28}: {df.shape[0]:>6} rows × {df.shape[1]:>2} cols")
    print("All SciNet datasets loaded successfully.")
