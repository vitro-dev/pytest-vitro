"""pytest vitro plugin module."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
from pytest import Config, Item, Parser, Session, TestReport  # noqa: PT013
from vitro.libraries.device_manager import DeviceManager, get_device_manager
from vitro.libraries.vitro_config import VitroConfig, get_json
from vitro.main import get_plugin_manager

from pytest_vitro.configs import LOGGING_CONFIG
from pytest_vitro.lib.argument_parser import ArgumentParser
from pytest_vitro.lib.html_report import get_vitro_html_table_report
from pytest_vitro.lib.utils import capture_vitro_logs, is_env_matching

if TYPE_CHECKING:
    from collections.abc import Generator


PALCO_PLUGIN_NAME = "_vitro"

THIS_TZ = datetime.now(timezone.utc).astimezone().tzinfo


class VitroPlugin:
    """Pytest vitro plugin."""

    # pylint: disable=no-member  # hook calls are not a member

    def __init__(self) -> None:
        """Initialize vitro plugin."""
        self._session_config: Config | None = None
        self._test_start_time: datetime | None = None
        self._deployment_setup_data: dict = {}
        self._deployment_teardown_data: dict = {}
        self._plugin_manager = get_plugin_manager()
        self.device_manager: DeviceManager | None = None
        self._vitro_config: VitroConfig | None = None

    @property
    def session_config(self) -> Config:
        """Raise Exception in case session config is not set, else return it."""
        if self._session_config is None:
            msg = "Session config is not set yet."
            raise ValueError(msg)
        return self._session_config

    @property
    def vitro_config(self) -> VitroConfig:
        """Raise Exception in case vitro config is not set, else return it."""
        if self._vitro_config is None:
            msg = "vitro config is not set yet."
            raise ValueError(msg)
        return self._vitro_config

    def pytest_addoption(self, parser: Parser) -> None:
        """Add command line arguments to pytest.

        :param parser: argument parser
        :type parser: Parser
        """
        self._plugin_manager.hook.vitro_add_cmdline_args(
            argparser=ArgumentParser(parser),
        )

    def deploy_vitro_devices(self) -> None:
        """Deploy vitro devices to the environment."""
        self.device_manager = self._plugin_manager.hook.vitro_register_devices(
            config=self._vitro_config,
            cmdline_args=self.session_config.option,
            plugin_manager=self._plugin_manager,
        )
        asyncio.run(
            self._plugin_manager.hook.vitro_setup_env(
                config=self._vitro_config,
                cmdline_args=self.session_config.option,
                plugin_manager=self._plugin_manager,
                device_manager=self.device_manager,
            ),
        )

    def release_vitro_devices(self) -> None:
        """Release vitro devices after the test execution."""
        if "exception" not in self._deployment_setup_data:
            deployment_status = {"status": "success"}
        else:
            exception_info = self._deployment_setup_data.get("exception")
            if exception_info is not None:
                deployment_status = {
                    "status": "failed",
                    "exception": exception_info[1],
                }
            else:
                deployment_status = {"status": "failed", "exception": "Unknown error"}
        self._plugin_manager.hook.vitro_release_devices(
            config=self._vitro_config,
            cmdline_args=self.session_config.option,
            plugin_manager=self._plugin_manager,
            deployment_status=deployment_status,
            device_manager=self.device_manager,
        )

    @pytest.hookimpl(hookwrapper=True)
    def pytest_sessionstart(self, session: Session) -> Generator[None]:
        """Deploy devices to environment and them release after use.

        :param session: pytest session instance
        :type session: Session
        """
        yield
        self._session_config = session.config
        self._plugin_manager.hook.vitro_configure(
            cmdline_args=self._session_config.option,
            plugin_manager=self._plugin_manager,
        )
        inventory_config = self._plugin_manager.hook.vitro_reserve_devices(
            cmdline_args=self._session_config.option,
            plugin_manager=self._plugin_manager,
        )

        self._vitro_config = self._plugin_manager.hook.vitro_parse_config(
            cmdline_args=self._session_config.option,
            inventory_config=inventory_config,
            env_config=get_json(self._session_config.option.env_config),
        )

    @staticmethod
    def _get_device_manager() -> DeviceManager | None:
        try:
            return get_device_manager()
        except ValueError:
            return None

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtestloop(self, session: Session) -> Generator[None]:
        """Deploy devices to environment and them release after use.

        :param session: pytest session instance
        :type session: Session
        """
        logging_plugin = session.config.pluginmanager.get_plugin(
            "logging-plugin",  # type:ignore[assignment]
        )
        if logging_plugin is None:
            msg = "Logging plugin is not available."
            raise RuntimeError(msg)
        device_manager = self._get_device_manager()
        try:
            if device_manager is None:
                logging_plugin.log_cli_handler.set_when("vitro setup")
                capture_vitro_logs(
                    logging_plugin,
                    self.deploy_vitro_devices,
                    capture_to=self._deployment_setup_data,
                )
            else:
                self.device_manager = device_manager
            yield
        finally:
            if device_manager is None:
                logging_plugin.log_cli_handler.set_when("vitro teardown")
                capture_vitro_logs(
                    logging_plugin,
                    self.release_vitro_devices,
                    capture_to=self._deployment_teardown_data,
                )

    @staticmethod
    def pytest_configure(config: Config) -> None:
        """Initialize env_req marker.

        :param config: pytest config
        :type config: Config
        """
        logging.config.dictConfig(LOGGING_CONFIG)
        config.addinivalue_line(
            "markers",
            "env_req(env_req: Dict): mark test with environment request. Skip"
            " test if environment check fails.\n"
            'Example: @pytest.mark.env_req({"environment_def":{"board":'
            '{"eRouter_Provisioning_mode":["dual"]}}})',
        )

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_setup(self, item: Item) -> Generator[None]:
        """Pytest run test setup hook wrapper to validate env_req marker.

        :param item: test item
        :type item: Item
        """
        env_req_marker = item.get_closest_marker("env_req")
        if (
            env_req_marker
            and env_req_marker.args
            and not is_env_matching(
                env_req_marker.args[0],
                self.vitro_config.env_config,
            )
        ):
            pytest.skip("Environment mismatch. Skipping")
        elif env_req_marker and env_req_marker.args:
            self._plugin_manager.hook.contingency_check(
                env_req=env_req_marker.args[0],
                device_manager=self.device_manager,
            )

        yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self) -> Generator[None]:
        """Capture test start and end time for the html report."""
        self._test_start_time = datetime.now(tz=THIS_TZ)
        yield
        self._test_start_time = None

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: Item) -> Generator[None]:
        """Save test start time to put in html execution report."""
        outcome = yield
        report: TestReport = outcome.get_result()  # type: ignore[attr-defined]
        report.test_start_time = self._test_start_time  # type: ignore[attr-defined]
        if report.when != "call":
            return
        pytest_html = item.config.pluginmanager.getplugin("html")
        if pytest_html is None:
            return
        report.extra = [  # type: ignore[attr-defined]
            pytest_html.extras.image(image[1], image[0])
            for image in report.user_properties
            if ".png" in list(image)[1]  # type: ignore[operator]
        ]

    @staticmethod
    @pytest.hookimpl(optionalhook=True)
    def pytest_html_results_table_header(cells: list[str]) -> None:
        """Add test start time custom header in html report.

        :param cells: html table header list
        :type cells: list[str]
        """
        cells.insert(0, '<th class="sortable" data-column-type="time">Start Time</th>')
        cells.insert(
            1,
            '<th class="sortable" data-column-type="time" style="display: none;">'
            "Hidden Time</th>",
        )

    @staticmethod
    @pytest.hookimpl(optionalhook=True)
    def pytest_html_results_table_row(report: TestReport, cells: list[str]) -> None:
        """Add test test start time in the html report.

        :param report: test execution report
        :type report: TestReport
        :param cells: html table row list
        :type cells: list[str]
        """
        test_start_time = (
            report.test_start_time
            if hasattr(report, "test_start_time")
            else datetime.now(tz=THIS_TZ)
        )
        epoch_time = test_start_time.strftime("%s %f")
        start_time_test = test_start_time.strftime("%d-%m-%Y %H:%M:%S:%f")
        cells.insert(
            0,
            f'<td class="col-time" style="display: none;">{epoch_time}</td>',
        )
        cells.insert(1, f'<td class="col-time">{start_time_test}</td>')

    @pytest.hookimpl(optionalhook=True)
    def pytest_html_results_summary(self, postfix: list[str]) -> None:
        """Update the html report with vitro deployment and environment details.

        :param postfix: html report postfix content list
        :type postfix: list[str]
        """
        postfix.extend(
            [
                "<h3>vitro</h3>",
                get_vitro_html_table_report(
                    session_config=self.session_config,
                    device_manager=self.device_manager,
                    vitro_config=self.vitro_config,
                    deployment_setup_data=self._deployment_setup_data,
                    deployment_teardown_data=self._deployment_teardown_data,
                ),
                "<br>",
            ],
        )
