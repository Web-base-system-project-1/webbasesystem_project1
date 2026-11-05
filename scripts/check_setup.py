"""Check the local environment without accessing OpenAlex or modifying files."""

import importlib
import json
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    failures = []

    def report(label, passed, detail=""):
        print(f"[{'OK' if passed else 'FAIL'}] {label}")
        if detail:
            print(f"       {detail}")
        if not passed:
            failures.append(label)

    print(f"Project: {PROJECT_ROOT}")
    report("Python 3.12", sys.version_info[:2] == (3, 12), sys.version.split()[0])
    report(
        "Project virtual environment",
        sys.prefix != sys.base_prefix
        and Path(sys.prefix).resolve() == (PROJECT_ROOT / ".venv").resolve(),
        sys.executable,
    )

    required_paths = [
        "pipeline/__init__.py", "detectors/__init__.py", "experiments/__init__.py",
        "web/app.py", "web/templates/index.html", "web/static/js/main.js",
        "web/static/js/api/client.js", "web/static/css/style.css",
        "data/sample", "config", "tests", "docs", "setting.md",
        "requirements.txt", "requirements-lock.txt", ".env.example",
    ]
    missing = [name for name in required_paths if not (PROJECT_ROOT / name).exists()]
    report("Project files", not missing, ", ".join(missing))

    for name in ("settings.json", "extensions.json", "launch.json", "tasks.json"):
        try:
            json.loads((PROJECT_ROOT / ".vscode" / name).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            report(f"VS Code {name}", False, str(error))
        else:
            report(f"VS Code {name}", True)

    imports_ok = True
    for module in ("flask", "requests", "pandas", "numpy", "yaml", "dotenv", "pytest"):
        try:
            importlib.import_module(module)
        except Exception as error:
            imports_ok = False
            report(f"Import {module}", False, str(error))
        else:
            report(f"Import {module}", True)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        report("pip check", False, str(error))
    else:
        report("pip check", result.returncode == 0, (result.stdout + result.stderr).strip())

    if imports_ok:
        try:
            from web.app import app

            app.config["TESTING"] = True
            with app.test_client() as client:
                for path in ("/", "/static/js/main.js", "/static/js/api/client.js", "/static/css/style.css"):
                    response = client.get(path)
                    report(f"HTTP {path}", response.status_code == 200, str(response.status_code))
                response = client.get("/api/health")
                report(
                    "Health API",
                    response.status_code == 200 and response.get_json() == {"status": "ok"},
                    f"HTTP {response.status_code}",
                )
        except Exception as error:
            report("Flask application", False, str(error))
    else:
        report("Flask application", False, "Install missing packages first.")

    if not (PROJECT_ROOT / ".env").exists():
        print("[NOTE] Copy .env.example to .env before entering your OpenAlex key.")
    print("[NOTE] OpenAlex API requests and Windows execution are not tested by this script.")
    print()
    if failures:
        print(f"Setup check FAILED: {len(failures)} item(s). See setting.md.")
        return 1
    print("Setup check PASSED. Start Flask and check the browser next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
