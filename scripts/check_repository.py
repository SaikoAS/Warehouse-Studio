"""Bootstrap repository checks; no application tests or external link requests."""

import ast
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]


class UniqueLoader(yaml.BaseLoader):
    """Keep YAML keys like 'on' as strings and reject duplicate mapping keys."""


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT
    ).decode("utf-8").split("\0")
    paths = sorted({ROOT / name for name in tracked if name})
    configs = {}
    for path in paths:
        if path.suffix.lower() not in {".md", ".yml", ".yaml", ".json", ".py", ".txt"}:
            continue
        content = path.read_text(encoding="utf-8")
        require("\ufffd" not in content and "\x00" not in content, f"Invalid text: {path}")
        if path.suffix in {".yml", ".yaml"}:
            configs[path.relative_to(ROOT).as_posix()] = yaml.load(content, Loader=UniqueLoader)
        elif path.suffix == ".json":
            json.loads(content)
        elif path.suffix == ".py":
            ast.parse(content, filename=str(path))
        elif path.suffix == ".md":
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
                target = target.strip().strip("<>")
                parsed = urlsplit(target)
                if parsed.scheme or target.startswith(("#", "//")):
                    continue
                destination = (path.parent / unquote(parsed.path)).resolve()
                require(destination.is_relative_to(ROOT), f"Link escapes repository: {path}: {target}")
                require(destination.exists(), f"Missing local link: {path}: {target}")

    manifest = json.loads((ROOT / ".github/labels.json").read_text(encoding="utf-8"))
    names = [label["name"] for label in manifest]
    require(len(names) == len(set(names)), "Duplicate label names")
    for label in manifest:
        require(re.fullmatch(r"[0-9a-fA-F]{6}", label["color"]), "Invalid label color")
        require(bool(label["description"]), "Label description required")
        require(not label["name"].startswith(("priority:", "status:", "agent:")), "Use Project fields/manual launches")

    required_ids = {"goal", "scope", "acceptance", "dependencies", "validation", "done"}
    expected_forms = {"bug-report.yml": "Bug Report", "feature-request.yml": "Feature Request", "technical-task.yml": "Technical Task"}
    for filename, name in expected_forms.items():
        form = configs[f".github/ISSUE_TEMPLATE/{filename}"]
        require(form["name"] == name and bool(form["description"]), f"Invalid form: {filename}")
        fields = form["body"]
        ids = [field["id"] for field in fields if "id" in field]
        require(len(ids) == len(set(ids)), f"Duplicate form IDs: {filename}")
        require(required_ids <= set(ids), f"Missing task contract: {filename}")
        for field in fields:
            require(field["type"] in {"markdown", "input", "textarea", "dropdown", "checkboxes"}, "Unsupported form type")
            if field.get("id") in required_ids:
                require(field.get("validations", {}).get("required") == "true", f"Required field missing: {filename}")
        require(set(form.get("labels", [])) <= set(names), f"Unknown form label: {filename}")

    workflow = configs[".github/workflows/repository-checks.yml"]
    require(set(workflow["on"]) == {"pull_request", "push"}, "Unexpected workflow trigger")
    require(workflow["permissions"] == {"contents": "read"}, "Workflow must be read-only")
    require(set(workflow["jobs"]) == {"docs-config", "windows-app"}, "Unexpected CI job")
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "uses" in step:
                action, _, revision = step["uses"].partition("@")
                require(action in {"actions/checkout", "actions/setup-node", "actions/setup-python",
                                   "actions/upload-artifact"}, "Unexpected CI action")
                require(re.fullmatch(r"[0-9a-f]{40}", revision), "Pin the reviewed action")
                if action == "actions/checkout":
                    require(step.get("with", {}).get("persist-credentials") == "false", "Do not persist credentials")
    require("secrets." not in (ROOT / ".github/workflows/repository-checks.yml").read_text(encoding="utf-8"), "Bootstrap needs no secrets")
    print(f"PASS: {len(paths)} repository files inspected; text, local file links, YAML/JSON, task forms, labels and baseline workflow checks.")
    print("Not application tests; external links, Markdown anchors and live GitHub/Codex settings are not checked.")


if __name__ == "__main__":
    main()
