import pytest

import synthetic
from repomentor import envs


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
    monkeypatch.delenv("REPOMENTOR_SESSIONS", raising=False)
    return home


@pytest.fixture(scope="session")
def upstream(tmp_path_factory):
    """(url, buggy_sha, fixed_sha) of the synthetic minicalc repo."""
    return synthetic.make_upstream(tmp_path_factory.mktemp("upstream"))


@pytest.fixture
def fake_envs(monkeypatch):
    fake = synthetic.FakeEnvs()
    monkeypatch.setattr(envs, "create_venv", fake.create_venv)
    monkeypatch.setattr(envs, "install_lock", fake.install_lock)
    monkeypatch.setattr(envs, "install_package", fake.install_package)
    return fake


@pytest.fixture
def challenge_dir(tmp_path, upstream):
    """A validated synthetic demo-001 in the demo dir."""
    return synthetic.write_challenge(tmp_path / "demo", synthetic.challenge_manifest(*upstream))
