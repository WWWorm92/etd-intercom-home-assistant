"""Run the custom integration in Home Assistant's real test harness."""
import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow loading this repository's integration."""
