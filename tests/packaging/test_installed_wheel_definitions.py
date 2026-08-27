"""Proves Definition loading works from an installed wheel, not the checkout.

Builds a real wheel, installs it into an isolated venv (never `pip install
-e`), and runs a child process outside the repository checkout with the
repository path removed from PYTHONPATH, so `import dnd_engine` can only
resolve to the installed copy.
"""

import importlib.metadata
import os
import shutil
import subprocess
import sys
import venv
from dataclasses import dataclass
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_COPY_EXCLUDES = shutil.ignore_patterns(
    ".git",
    ".venv",
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".mypy_cache",
    "build",
    "dist",
    "*.egg-info",
)

SUCCESS_SCRIPT = """
import os
from pathlib import Path

import dnd_engine
from dnd_engine.domain.definitions.monster import MonsterDefinition
from dnd_engine.domain.definitions.weapon import WeaponDefinition
from dnd_engine.domain.value_objects.damage_type import DamageType
from dnd_engine.infrastructure.definitions.packaged import PackagedDefinitionSource

repo_root = Path(os.environ["REPO_ROOT_UNDER_TEST"]).resolve()
module_path = Path(dnd_engine.__file__).resolve()
assert repo_root not in module_path.parents, (repo_root, module_path)
assert not (module_path.parent.parent / "rules").exists()

source = PackagedDefinitionSource()
monster = source.get_definition(
    ruleset_id="dnd_5e",
    ruleset_version="5.1",
    definition_id="goblin",
    expected_type=MonsterDefinition,
)

assert type(monster) is MonsterDefinition, type(monster)
assert monster.id == "goblin", monster.id
assert monster.armor_class == 15, monster.armor_class
assert monster.ability_scores.dexterity == 14, monster.ability_scores.dexterity

weapon = source.get_definition(
    ruleset_id="dnd_5e",
    ruleset_version="5.1",
    definition_id="dagger",
    expected_type=WeaponDefinition,
)

assert type(weapon) is WeaponDefinition, type(weapon)
assert weapon.id == "dagger", weapon.id
assert weapon.name == "Dagger", weapon.name
assert weapon.damage_dice == "1d4", weapon.damage_dice
assert weapon.damage_type is DamageType.PIERCING, weapon.damage_type
assert weapon.properties == ("finesse", "light", "thrown"), weapon.properties
print("INSTALLED_WHEEL_LOOKUP_OK")
"""

MISSING_DEFINITION_SCRIPT = """
from dnd_engine.domain.definitions.monster import MonsterDefinition
from dnd_engine.domain.services.definitions import DefinitionNotFoundError
from dnd_engine.infrastructure.definitions.packaged import PackagedDefinitionSource

source = PackagedDefinitionSource()
try:
    source.get_definition(
        ruleset_id="dnd_5e",
        ruleset_version="5.1",
        definition_id="does_not_exist",
        expected_type=MonsterDefinition,
    )
except DefinitionNotFoundError:
    print("INSTALLED_WHEEL_MISSING_OK")
else:
    raise AssertionError("expected DefinitionNotFoundError")
"""


@dataclass(frozen=True)
class InstalledWheel:
    venv_python: Path
    outside_repo_cwd: Path


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


_DECLARED_MINIMUM_SETUPTOOLS = 68


def _build_environment_has_declared_setuptools() -> bool:
    """True if the interpreter running this test already satisfies the
    `setuptools>=68` build requirement declared in pyproject.toml.

    Used to skip pip's isolated-build environment (which would otherwise
    fetch a fresh setuptools/wheel over the network) when this interpreter
    can already build the project directly.
    """
    try:
        version = importlib.metadata.version("setuptools")
    except importlib.metadata.PackageNotFoundError:
        return False
    try:
        major = int(version.split(".", 1)[0])
    except ValueError:
        return False
    return major >= _DECLARED_MINIMUM_SETUPTOOLS


@pytest.fixture(scope="module")
def installed_wheel(tmp_path_factory: pytest.TempPathFactory) -> InstalledWheel:
    # Build from a throwaway copy of the source tree, not the real checkout,
    # so setuptools' intermediate `build/`/`*.egg-info` staging directories
    # never land inside the repository.
    source_copy = tmp_path_factory.mktemp("source") / "ai-dnd-master"
    shutil.copytree(REPOSITORY_ROOT, source_copy, ignore=_SOURCE_COPY_EXCLUDES)

    wheel_dir = tmp_path_factory.mktemp("wheel")
    venv_dir = tmp_path_factory.mktemp("venv")
    outside_repo_cwd = tmp_path_factory.mktemp("outside-repo-cwd")

    build_command = [
        sys.executable,
        "-m",
        "pip",
        "wheel",
        str(source_copy),
        "--no-deps",
        "--wheel-dir",
        str(wheel_dir),
    ]
    if _build_environment_has_declared_setuptools():
        # This interpreter already satisfies pyproject.toml's declared
        # `setuptools>=68` build requirement, so skip pip's isolated build
        # environment (and the network fetch it would otherwise perform).
        build_command.append("--no-build-isolation")

    build_result = subprocess.run(
        build_command,
        cwd=str(outside_repo_cwd),
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert build_result.returncode == 0, (
        f"wheel build failed:\nstdout:\n{build_result.stdout}\n"
        f"stderr:\n{build_result.stderr}"
    )

    wheel_files = sorted(wheel_dir.glob("*.whl"))
    assert len(wheel_files) == 1, f"expected exactly one wheel, found {wheel_files}"
    wheel_path = wheel_files[0]

    venv.EnvBuilder(with_pip=True, clear=True).create(str(venv_dir))
    venv_python = (
        venv_dir / "Scripts" / "python.exe"
        if os.name == "nt"
        else venv_dir / "bin" / "python"
    )
    assert venv_python.is_file()

    install_result = subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--no-index", str(wheel_path)],
        cwd=str(outside_repo_cwd),
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert install_result.returncode == 0, (
        f"wheel install failed:\nstdout:\n{install_result.stdout}\n"
        f"stderr:\n{install_result.stderr}"
    )

    return InstalledWheel(venv_python=venv_python, outside_repo_cwd=outside_repo_cwd)


def _run_child_script(installed_wheel: InstalledWheel, script: str) -> subprocess.CompletedProcess[str]:
    env = _clean_env()
    env["REPO_ROOT_UNDER_TEST"] = str(REPOSITORY_ROOT)
    return subprocess.run(
        [str(installed_wheel.venv_python), "-c", script],
        cwd=str(installed_wheel.outside_repo_cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_installed_wheel_resolves_packaged_goblin_definition(
    installed_wheel: InstalledWheel,
) -> None:
    result = _run_child_script(installed_wheel, SUCCESS_SCRIPT)

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "INSTALLED_WHEEL_LOOKUP_OK" in result.stdout


def test_installed_wheel_raises_definition_not_found_for_missing_id(
    installed_wheel: InstalledWheel,
) -> None:
    result = _run_child_script(installed_wheel, MISSING_DEFINITION_SCRIPT)

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "INSTALLED_WHEEL_MISSING_OK" in result.stdout
