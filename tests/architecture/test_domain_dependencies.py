import ast
from importlib.util import resolve_name
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
DOMAIN_ROOT = SRC_ROOT / "dnd_engine" / "domain"
FORBIDDEN_PREFIXES = (
    "dnd_engine.application",
    "dnd_engine.infrastructure",
    "dnd_engine.api",
)


def package_name(path: Path, src_root: Path = SRC_ROOT) -> str:
    module_parts = path.relative_to(src_root).with_suffix("").parts
    return ".".join(module_parts[:-1])


def imported_modules(path: Path, src_root: Path = SRC_ROOT) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    current_package = package_name(path, src_root)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module is not None:
                    modules.append(node.module)
                continue

            relative_name = "." * node.level + (node.module or "")
            absolute_name = resolve_name(relative_name, current_package)
            if node.module is not None:
                modules.append(absolute_name)
            else:
                modules.extend(
                    f"{absolute_name}.{alias.name}" for alias in node.names
                )

    return tuple(modules)


def is_forbidden(module: str) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in FORBIDDEN_PREFIXES
    )


def write_module(tmp_path: Path, relative_path: str, source: str) -> tuple[Path, Path]:
    src_root = tmp_path / "src"
    path = src_root / relative_path
    path.parent.mkdir(parents=True)
    path.write_text(source, encoding="utf-8")
    return path, src_root


def test_forbidden_relative_import_from_ordinary_module(tmp_path: Path) -> None:
    path, src_root = write_module(
        tmp_path,
        "dnd_engine/domain/rules/example.py",
        "from ...application import something\n",
    )

    modules = imported_modules(path, src_root)

    assert modules == ("dnd_engine.application",)
    assert is_forbidden(modules[0])


def test_forbidden_relative_import_from_domain_package_init(tmp_path: Path) -> None:
    path, src_root = write_module(
        tmp_path,
        "dnd_engine/domain/__init__.py",
        "from ..application import something\n",
    )

    assert package_name(path, src_root) == "dnd_engine.domain"
    modules = imported_modules(path, src_root)

    assert modules == ("dnd_engine.application",)
    assert is_forbidden(modules[0])


def test_allowed_domain_relative_import(tmp_path: Path) -> None:
    path, src_root = write_module(
        tmp_path,
        "dnd_engine/domain/rules/example.py",
        "from ..value_objects import ability\nfrom . import helpers\n",
    )

    modules = imported_modules(path, src_root)

    assert modules == (
        "dnd_engine.domain.value_objects",
        "dnd_engine.domain.rules.helpers",
    )
    assert not any(is_forbidden(module) for module in modules)


def test_forbidden_absolute_imports(tmp_path: Path) -> None:
    path, src_root = write_module(
        tmp_path,
        "dnd_engine/domain/rules/example.py",
        "from dnd_engine.infrastructure.foo import Bar\n"
        "import dnd_engine.application.handlers\n",
    )

    modules = imported_modules(path, src_root)

    assert modules == (
        "dnd_engine.infrastructure.foo",
        "dnd_engine.application.handlers",
    )
    assert all(is_forbidden(module) for module in modules)


def test_domain_has_no_outward_layer_imports() -> None:
    violations: list[str] = []

    for path in sorted(DOMAIN_ROOT.rglob("*.py")):
        for module in imported_modules(path):
            if is_forbidden(module):
                relative_path = path.relative_to(SRC_ROOT.parent)
                violations.append(f"{relative_path.as_posix()}: {module}")

    assert violations == []
