import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Every test gets its own REPOMENTOR_HOME, workspace root, and an empty demo dir."""
    home = tmp_path / "home"
    workspaces = tmp_path / "workspaces"
    demo = tmp_path / "demo"
    for d in (home, workspaces, demo):
        d.mkdir()
    monkeypatch.setenv("REPOMENTOR_HOME", str(home))
    monkeypatch.setenv("REPOMENTOR_WORKSPACES", str(workspaces))
    monkeypatch.setenv("REPOMENTOR_DEMO_DIR", str(demo))
    return home
