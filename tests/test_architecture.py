import ast
import os
from pathlib import Path


def test_core_does_not_import_io() -> None:
    """
    Ensure that packages/core does NOT import any I/O, network, or DB related libraries.
    This enforces the 'core is pure, edge is dirty' architecture principle.
    """
    forbidden_modules = {
        "requests",
        "httpx",
        "urllib",
        "urllib3",
        "aiohttp",
        "sqlalchemy",
        "redis",
        "fastapi",
        "starlette",
        "psycopg",
        "psycopg2",
        "osrm",
        "socket",
    }

    core_dir = Path("packages/core")
    
    # If the directory doesn't exist yet, we can pass the test (TDD approach)
    if not core_dir.exists():
        return

    violations = []

    for root, _, files in os.walk(core_dir):
        for file in files:
            if not file.endswith(".py"):
                continue

            file_path = Path(root) / file
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError:
                # Syntax errors will be caught by other tools (ruff, etc.)
                continue

            for node in ast.walk(tree):
                module_name = None
                
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split(".")[0]
                        if module_name in forbidden_modules:
                            violations.append(f"{file_path}: import {alias.name}")
                            
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split(".")[0]
                        if module_name in forbidden_modules:
                            violations.append(f"{file_path}: from {node.module} import ...")

    assert not violations, "Core code must not import I/O modules:\n" + "\n".join(violations)
