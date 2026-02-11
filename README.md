# vitro plugin for pytest

`pytest-vitro` is the extension that integrates vitro with pytest.
It adapts vitro's plugin/runner lifecycle into pytest sessions and exposes
convenient fixtures for tests and interactive sessions.


## Overview

`pytest-vitro` is responsible for the following operations:

- Register vitro `fixtures` and a `VitroPlugin` object that coordinates
environment parsing, device registration, deployment and teardown.
- Expose `device_manager`, `vitro_config`, `vt_context` and `vt_logger`
fixtures to tests.
- Orchestrate a multi-phase boot/config lifecycle via vitro plug-in hooks when
pytest runs (deploy devices before tests and release them at the end).
- Add a small test selector (`--test-names`) to limit which tests are executed
  by name.
- Integrate with pytest-html to add vitro deployment metadata and captured
images to generated HTML reports.


## Quick install

```bash
pip install pytest-vitro
```

## How the plugin loads

There are two important registration points in the plugin code:

1. An early `conftest` hook registers a minimal fixtures module so small utilities
are available early (`vt_context`, `vt_logger`). The heavier `VitroPlugin`
instance is registered conditionally based on detected command-line arguments.
1. The `VitroPlugin` class is the main integration surface. It adds
command-line arguments via `vitro_add_cmdline_args`, parses inventory and env
JSONs, registers and sets up devices through vitro hooks, and performs
teardown and release at session end.

This separation allows lightweight test runs to use a couple of fixtures without provisioning devices, and it enables full vitro provisioning only when requested.

## Command-line options and selection

The plugin adds a test selection option named `--test-names` which accepts a space-separated list of logical test names. When provided, collected tests are filtered: only items matching normalized `test_<name>`.

vitro's own CLI options (for example: `board-name`, `env-config`, `inventory-config`, `skip-boot`, `skip-contingency-checks`, `save-console-logs`) are exposed by the plugin through the `VitroPlugin` lifecycle. Once the plugin is active you can inspect available options using pytest's help output.

```bash
$ pytest -h
usage: pytest [options] [file_or_dir] [file_or_dir] [...]

...
vitro:
  --board-name=BOARD_NAME
                        Board name
  --env-config=ENV_CONFIG
                        Environment JSON config file path
  --inventory-config=INVENTORY_CONFIG
                        Inventory JSON config file path
  --legacy              allows for devices.<device> obj to be exposed (only for legacy use)
  --skip-boot           Skips the booting process, all devices will be used as they are
  --skip-contingency-checks
                        Skip contingency checks while running tests
  --save-console-logs=SAVE_CONSOLE_LOGS
                        Save the console logs at the give location
  --ignore-devices=IGNORE_DEVICES
                        Ignore the given devices (names are comma separated). Useful when a device is incommunicado

Custom options:
  --test-names=TEST_NAMES
                        Test names for which the execution will be performed
```

---

## Fixtures provided

The plugin exposes several fixtures aimed at easing device interaction, configuration access and contextual logging. Most of these are session scoped.

- `vt_context` (function scope): Returns a `ContextStorage` instance useful for sharing ephemeral data within a single test.

    ```python
    def test_example(vt_context):
        vt_context["foo"] = "bar"
    ```

- `vt_logger` (session *autouse*): Returns a `TestLogger` instance for step-level logging and tracing.

    ```python
    def test_log(vt_logger):
        vt_logger.step("Connect to DUT")
    ```

- `vitro_config` (session): Returns the resolved `vitroConfig` that the plugin created by merging inventory, env files and CLI overrides. Use this to inspect provisioning mode and environment definitions.

    ```python
    def test_config(vitro_config):
        assert vitro_config.get_prov_mode() in ("ipv4", "ipv6", "dual")
    ```

- `device_manager` (session): Returns the `DeviceManager` that holds instantiated device objects constructed from the inventory. Use it to query devices by template/interface or type.

    ```python
    def test_device(device_manager):
        cpe = device_manager.get_device_by_type(CPE)
        assert cpe is not None
    ```

These fixtures are intended to be the main integration points for tests and interactive sessions.

> **Important**: Tests should call use-cases and obtain devices through `device_manager` rather than instantiating devices directly.

## Markers

### `@pytest.mark.env_req(...)`

`env_req` is a custom marker introduced by the plugin to declare an environment requirement for the test. If the current vitro environment does not satisfy the requested env_req, the test will be skipped.

**Example scenario:** mark tests that require dual-stack provisioning.

```python
import pytest


@pytest.mark.env_req({
    "environment_def": {"board": {"eRouter_Provisioning_mode": ["dual"]}}
})
def test_tr069_dual_mode(device_manager): ...
```

During `pytest_runtest_setup`, the plugin validates the marker against the loaded `vitro_config.env_config`. If matched, the plugin also runs the `contingency_check` hook to ensure devices are healthy before test execution.

---

## Running tests — examples

Run pytest and let vitro provision the environment as part of test setup.
(typical invocation — vitro CLI args are forwarded by the plugin):

```bash
pytest -s \
    --rootdir=. \
    --board-name prplos-docker-1 \
    --env-config ./vitro/configs/vitro_env_example.json  \
    --inventory-config ./vitro/configs/vitro_config_example.json \
    --junitxml ./results/pytest_run_report.xml \
    --html=./results/pytest_run_report.html  \
    --self-contained-html  \
    --save-console-logs=./results  \
    ./tests/
```

- The pytest-vitro plugin reads the --env-config and --inventory-config options and uses them to build a `vitroConfig` and a `DeviceManager`.
- Unless you pass `--skip-boot`, the plugin will call vitro pluggy hooks to reserve, boot and configure services and devices before tests run.
- During tests, fixtures like `device_manager` and `vitro_config` become available for use cases and tests.
- After the run, vitro plugin will run device teardown and release hooks, and store the collected logs/reports in `./results` directory.

### `--skip-contingency-checks` option

When passed, vitro will skip running the per-device **`contingency_check`** hooks that normally run just before a test starts (or during provisioning) to validate that devices/services are healthy and meet the test’s `env_req` expectations.

#### Where contingency checks run

The plugin calls device-level `contingency_check(env_req, device_manager)` hooks when a test is about to run (if the test has an `@pytest.mark.env_req(...)`) or during provisioning to ensure devices are responsive and in the expected state.

These checks typically run commands like TR-069 calls, IP checks, or basic service pings on each device.

#### Why you might use `--skip-contingency-checks`

- Faster iteration during development (avoid waiting for slow health checks).
- Quick smoke runs where you don’t want the plugin to gate tests.
- When contingency checks are known to be flaky and you’re debugging other layers.

#### Risks / tradeoffs (important)

- You may run tests against **unhealthy or misconfigured devices**. Skipping checks removes a safety gate that would otherwise detect unreachable consoles, missing services or mis-provisioned DUTs.

- **More flaky failures:** tests may fail with confusing symptoms because the device wasn’t validated first.

- **Harder root-cause:** the bug might be environment-related (power, network, container not up), but you’ll only see it when tests fail — later in the cycle.

#### Recommendation

Use `--skip-contingency-checks` **only** for short development loops or when you explicitly know the environment is already healthy. For CI and official runs, prefer **not** to skip contingency checks so tests are executed against validated devices.

## How the plugin orchestrates vitro

High-level lifecycle the plugin implements:

1. `pytest` starts and early fixtures are registered.
2. When `VitroPlugin` is active it adds vitro CLI args and, on session start:
   - Calls the `vitro_reserve_devices` hook to reserve lab hardware or otherwise prepare inventory.
   - Calls the `vitro_parse_config` hook to merge inventory, env JSON and CLI overrides into a `vitroConfig`.
3. During the test run the plugin:
   - Registers and instantiates device classes via `vitro_register_devices`.
   - Calls `vitro_setup_env` (async-capable) which triggers device-level hooks to boot and configure servers, devices and attached clients in the documented order.
4. Tests execute and call use-cases that use templated APIs; `DeviceManager` supplies the correct concrete implementation at runtime.
5. After tests complete the plugin calls `vitro_release_devices` and device shutdown hooks to clean up resources.

Because the plugin uses vitro’s pluggy hooks for the heavy lifting, tests remain concise and protocol-driven while the plugin ensures correct lifecycle orchestration.

## HTML report integration

When `pytest-html` is present, the plugin enhances the generated HTML report by:

- Adding columns for test start time and hidden epoch time for sorting.
- Appending a vitro section to the summary that shows deployment, environment and teardown details.
- Embedding captured PNG images attached to test results into the HTML output.
    > **Note:** This feature is only available when a GUI test performs a screen shot and the fixture saves the attachment.

This provides a compact test execution summary together with environment metadata and visual evidence useful for debugging.

## Troubleshooting & tips

- **Plugin not loaded:** make sure the plugin package is installed and the pytest entry points are configured. Use pytest's plugin diagnostics to verify loaded plugins.
- **HTML report not showing vitro data:** confirm `pytest-html` is installed and enabled; the plugin only augments the HTML report when the html plugin is available.
- **Tests skipped via `env_req`:** verify that the `env_req` marker matches the keys and values declared in your `env_config`. Use the `vitro_config` fixture in a quick test to inspect resolved environment values.
- **Test selection edge cases:** the test selection option does pattern matching; ensure you provide normalized logical names that correspond to the collected test items.

## Development notes

- The plugin exposes a minimal set of early fixtures so small helper functionality can be used even when full deployment is not performed.
- The `VitroPlugin` uses hookwrapper-style pytest hooks to capture setup and teardown logs and to integrate cleanly with pytest's logging plugin.
- For extending functionality, add command-line args via `vitro_add_cmdline_args`, register device classes using `vitro_add_devices` / `vitro_register_devices`, and implement device hooks in plugin packages.

## Contributing

Contributions are welcome. When adding or modifying plugin behavior follow these guidelines:

- Expose new CLI options via the `vitro_add_cmdline_args` hook so they participate in the standard parsing lifecycle.
- New device classes should be registered through `vitro_add_devices`, and any lifecycle orchestration should use core hooks rather than modifying runner internals.
- Add tests for fixture behavior using pytest's testing helpers and ensure HTML reporting integration remains intact where applicable.

## License

The pytest-vitro plugin follows the same licensing as vitro (Clear BSD). See the top-level [LICENSE](https://github.com/vitro-dev/pytest-vitro/blob/vitro/LICENSE) file for details.


## Acknowledgements

This plugin is fork of [pytest-boardfarm](https://github.com/lgirdk/pytest-boardfarm),
tailored to the usage with the [vitro framework](https://github.com/vitro-dev/vitro/).
