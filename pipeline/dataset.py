"""Locate and open the dataset used by the web app and experiment runner."""

from contextlib import contextmanager
import os
from zipfile import Path as ZipPath, ZipFile

from dotenv import dotenv_values

from pipeline._files import PROJECT_ROOT, project_path

DEFAULT_DATASET = "data/sample/actual/four_fields_2015_2025_v1.zip"


def dataset_path(value=None):
    configured = value or os.environ.get("DATA_DIR")
    if not configured:
        configured = dotenv_values(PROJECT_ROOT / ".env").get("DATA_DIR")
    return project_path(configured or DEFAULT_DATASET)


@contextmanager
def open_dataset(source):
    if source.is_dir():
        yield source
        return

    if source.suffix.lower() != ".zip":
        raise FileNotFoundError(f"데이터 폴더가 없습니다: {source.name}")

    with ZipFile(source) as archive:
        root = ZipPath(archive)
        directories = [entry for entry in root.iterdir() if entry.is_dir()]
        if len(directories) != 1:
            raise ValueError("데이터 ZIP 최상위에 집계 폴더 하나가 필요합니다.")
        yield directories[0]
