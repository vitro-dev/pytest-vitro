"""pytest plugin for vitro."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from pytest_vitro import vitro_fixtures
from pytest_vitro.vitro_plugin import VITRO_PLUGIN_NAME, VitroPlugin

if TYPE_CHECKING:
    from _pytest.config.argparsing import Parser
    from _pytest.nodes import Item
    from pytest import Config  # noqa: PT013

sys.setrecursionlimit(3000)


# pylint: disable=too-few-public-methods


def pytest_addoption(parser: Parser) -> None:
    """Add command line arguments to pytest.

    :param parser: argument parser
    :type parser: Parser
    """
    parser.addoption(
        "--test-names",
        action="store",
        default=None,
        help="Test names for which the execution will be performed",
    )


def pytest_load_initial_conftests(early_config: Config, args: list[str]) -> None:
    """Register vitro plugin to pytest based on command line arguments.

    :param early_config: pytest config
    :type early_config: Config
    :param args: command line arguments
    :type args: list[str]
    """
    early_config.pluginmanager.register(vitro_fixtures)
    if any(x for x in args if (x in ("--help", "-h") or x.startswith("--board"))):
        early_config.pluginmanager.register(VitroPlugin(), VITRO_PLUGIN_NAME)


def pytest_collection_modifyitems(config: Config, items: list[Item]) -> None:
    """Discover the tests in the folder.

    Select the test from the tests folder based on the value provided for --test-names

    :param config: pytest config
    :type config: Config
    :param items: list of collected tests function
    :type items: list
    """
    selected_tests = []
    deselected_tests = []
    test_names = config.getoption("--test-names")

    if not test_names:
        return

    test_list = test_names.split(" ")
    for item in items:
        for test in test_list:
            test_name = f"test_{test.replace('-', '_')}"
            if (
                test_name == item.name
                or f"{test_name}[" in item.name
                or f"{test}-" in item.name
            ):
                selected_tests.append(item)
                break
        else:
            deselected_tests.append(item)
    items[:] = selected_tests
    if deselected_tests:
        config.hook.pytest_deselected(items=deselected_tests)
