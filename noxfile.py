"""Lint and test pytest-vitro on multiple python environments."""

import nox

_PYTHON_VERSIONS = (
    "3.10",
    "3.11",
    "3.12",
    "3.13",
    "3.14",
    "3.14t",
)

# Fail nox session when run a program which is not installed in its virtualenv
nox.options.error_on_external_run = True

# use uv to speed up the dependencies installation
nox.options.default_venv_backend = "uv"


def _install_deps(session: nox.Session) -> None:
    session.run_install(
        "uv",
        "sync",
        "-q",
        "--frozen",
        f"--python={session.virtualenv.location}",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )


@nox.session(python=_PYTHON_VERSIONS)
def lint(session: nox.Session) -> None:
    """Lint pytest-vitro."""
    _install_deps(session=session)
    session.run("ruff", "format", "--check", ".")
    session.run("ruff", "check", ".")
    session.run("mypy", "./src/", "./tests/")


@nox.session(python=_PYTHON_VERSIONS)
def pylint(session: nox.Session) -> None:
    """Lint pytest-vitro using pylint without dev dependencies."""
    _install_deps(session=session)
    session.run("pylint", "pytest_vitro")


@nox.session
def coverage_clean(session: nox.Session) -> None:
    """Clean coverage data."""
    _install_deps(session=session)
    session.run("coverage", "erase")


@nox.session(python=_PYTHON_VERSIONS, requires=["coverage_clean"])
def test(session: nox.Session) -> None:
    """Test pytest-vitro."""
    _install_deps(session=session)
    session.run("coverage", "run", "-m", "pytest", "tests")

    session.notify("coverage_collate")


@nox.session
def coverage_collate(session: nox.Session) -> None:
    """Collate coverage data from all sessions."""
    _install_deps(session=session)
    session.run("coverage", "html")


@nox.session(python=_PYTHON_VERSIONS)
def vitro_help(session: nox.Session) -> None:
    """Execute vitro --help.

    This helps identifying integration issues with the plugins/devices.
    """
    _install_deps(session)
    session.run("vitro", "--help")
