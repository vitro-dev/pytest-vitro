"""pytest vitro fixtures."""

from __future__ import annotations

from argparse import Namespace
from typing import TYPE_CHECKING, Any

import pytest
from vitro.devices.base_devices import VitroDevice

from pytest_vitro.exceptions import VitroPluginError
from pytest_vitro.lib.test_logger import TestLogger
from pytest_vitro.lib.utils import ContextStorage
from pytest_vitro.vitro_plugin import VITRO_PLUGIN_NAME, VitroPlugin

if TYPE_CHECKING:
    from _pytest.config import Config
    from vitro.libraries.device_manager import DeviceManager
    from vitro.libraries.vitro_config import VitroConfig


@pytest.fixture
def vt_context() -> ContextStorage:
    """Fixture that return context storage instance.

    :return: context storage instance
    :rtype: ContextStorage
    """
    return ContextStorage()


@pytest.fixture(scope="session", autouse=True)
def vt_logger() -> TestLogger:
    """Fixture that return test step log wrapper instance.

    :return: log wrapper instance
    :rtype: TestLogger
    """
    return TestLogger()


def get_vitro_plugin(pytestconfig: Config) -> VitroPlugin:
    """Return vitro plugin from pytest config.

    :param pytestconfig: pytest config
    :type pytestconfig: Config
    :raises VitroPluginError: when vitro plugin is not registered
    :return: vitro plugin instance
    :rtype: VitroPlugin
    """
    plugin = pytestconfig.pluginmanager.get_plugin(VITRO_PLUGIN_NAME)
    if plugin is None:
        err_msg = "vitro plugin is not registered."
        raise VitroPluginError(err_msg)
    return plugin


@pytest.fixture(scope="session")
def vitro_config(pytestconfig: Config) -> VitroConfig:
    """Fixture that return vitro config.

    :param pytestconfig: pytest config
    :type pytestconfig: Config
    :return: vitro config
    :rtype: VitroConfig
    """
    return get_vitro_plugin(pytestconfig).vitro_config


@pytest.fixture(scope="session")
def device_manager(pytestconfig: Config) -> DeviceManager:
    """Fixture that return vitro device manager.

    :param pytestconfig: pytest config
    :param pytestconfig: Config
    :return: vitro device manager
    :rtype: DeviceManager
    """
    dm = get_vitro_plugin(pytestconfig).device_manager
    if dm is None:
        err_msg = "vitro device manager is not initialized."
        raise VitroPluginError(err_msg)
    return dm


@pytest.fixture(scope="session")
def devices(
    device_manager: DeviceManager,  # pylint: disable=redefined-outer-name
) -> Any:  # noqa: ANN401
    """Legacy vitro devices fixture.

    :param device_manager: device manager
    :type device_manager: DeviceManager
    :return: devices fixture
    :rtype: Any
    """
    return Namespace(**device_manager.get_devices_by_type(VitroDevice))
