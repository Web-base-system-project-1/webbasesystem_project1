"""Package period aggregates with matching experiment and review records."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline._files import fingerprint, project_path, read_csv, read_json


def package(data_dir, experiment_dir, review_dir, output):
    manifest = read_json(data_dir / "MANIFEST.json")
    review = read_json(review_dir / "detection-data-review.json")
    if review["data_version"] != manifest["data_version"]:
        raise ValueError("데이터와 사례 검증의 버전이 다릅니다.")
    files = {filename: data_dir / filename for filename in manifest["files"]}
    for filename, info in manifest["files"].items():
        if fingerprint(files[filename]) != info["sha256"]:
            raise ValueError(f"{filename} 집계 해시가 다릅니다.")
    for filename, digest in review["experiment_files"].items():
        path = experiment_dir / filename
        if fingerprint(path) != digest:
            raise ValueError(f"{filename} 실험 검증 해시가 다릅니다.")
        files[filename] = path
    files["MANIFEST.json"] = data_dir / "MANIFEST.json"
    definitions = PROJECT_ROOT / "config/field_definition.csv"
    if read_csv(definitions) != manifest["definitions"]:
        raise ValueError("현재 분야 정의와 집계 정의가 다릅니다.")
    files["field_definition.csv"] = definitions
    raw_manifest = project_path(manifest["source"]["path"])
    if fingerprint(raw_manifest) != manifest["source"]["sha256"]:
        raise ValueError("원본 수집 기록의 해시가 다릅니다.")
    files["collection_log.csv"] = raw_manifest.parent / "collection_log.csv"
    for filename in ("data-verification.json", "detection-data-review.json", "institution-mapping-review.json"):
        path = review_dir / filename
        if read_json(path)["data_version"] != manifest["data_version"]:
            raise ValueError(f"{filename} 검증 버전이 다릅니다.")
        files[filename] = path
    guide = PROJECT_ROOT / "docs/data-review-2026-11-19.md"
    files["README.md"] = guide
    experiment_manifest = {
        "data_version": manifest["data_version"], "seed": review["seed"],
        "corrections": ["none", "min_international_total_3", "require_share_increase"],
        "code_sha256": {
            name: fingerprint(PROJECT_ROOT / name)
            for name in (
                "detectors/zscore.py", "detectors/growth.py", "detectors/panel.py",
                "experiments/inject.py", "experiments/correct.py",
                "experiments/run.py", "experiments/evaluate.py",
            )
        },
        "files": {name: {"sha256": digest} for name, digest in review["experiment_files"].items()},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    root = data_dir.name
    with TemporaryDirectory(prefix=".package-", dir=output.parent) as temporary:
        path = Path(temporary) / output.name
        with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
            for filename, source in sorted(files.items()):
                archive.write(source, f"{root}/{filename}")
            archive.writestr(f"{root}/experiment_manifest.json", json.dumps(experiment_manifest, indent=2) + "\n")
        with ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError("데이터 ZIP 검증 실패")
            for name, source in files.items():
                digest = hashlib.sha256(archive.read(f"{root}/{name}")).hexdigest()
                if digest != fingerprint(source):
                    raise ValueError(f"{name} ZIP 내용 해시가 다릅니다.")
        path.replace(output)
    print(f"공유 ZIP 생성: {output.name}, {len(files) + 1}파일, {manifest['data_version']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--experiments-dir", required=True, type=Path)
    parser.add_argument("--review-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    package(
        project_path(args.data_dir), project_path(args.experiments_dir),
        project_path(args.review_dir), project_path(args.output),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
