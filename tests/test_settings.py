"""Runtime configuration for the local operator dashboard."""

from parking.common import load_settings


def test_dashboard_environment_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("PARKING_DASHBOARD_HOST", "0.0.0.0")
    monkeypatch.setenv("PARKING_DASHBOARD_PORT", "9001")
    monkeypatch.setenv("PARKING_DASHBOARD_OPEN_BROWSER", "false")

    settings = load_settings(str(tmp_path / "missing.yaml"))

    assert settings.dashboard_host == "0.0.0.0"
    assert settings.dashboard_port == 9001
    assert settings.dashboard_open_browser is False
