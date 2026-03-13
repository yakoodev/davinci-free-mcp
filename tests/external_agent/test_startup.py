from pathlib import Path

from davinci_free_mcp.external_agent.startup import (
    PreparedStartupTarget,
    ResolveProjectStartupOrchestrator,
    ResolveStartupConfig,
    ResolveStartupPaths,
)


CONFIG_XML = """<Config>
<AutoReloadPrevProj>false</AutoReloadPrevProj>
<LastWorkingProject>Old Project</LastWorkingProject>
<LastWorkingProjectFolder/>
</Config>
"""


def build_paths(tmp_path: Path) -> ResolveStartupPaths:
    prefs_dir = tmp_path / "Preferences"
    support_dir = tmp_path / "Support"
    backup_root = tmp_path / "runtime" / "startup_backups"
    prefs_dir.mkdir(parents=True, exist_ok=True)
    (support_dir / "logs").mkdir(parents=True, exist_ok=True)
    (support_dir / "Resolve Project Library" / "Resolve Projects" / "Users" / "guest" / "Projects").mkdir(
        parents=True,
        exist_ok=True,
    )
    config_user_xml = prefs_dir / "config.user.xml"
    recent_projects = prefs_dir / "recentprojects.conf"
    config_user_xml.write_text(CONFIG_XML, encoding="utf-8")
    recent_projects.write_text(
        "disk:Local Database:Local Database:\\Demo Project:Demo Project::abc\n",
        encoding="utf-8",
    )
    return ResolveStartupPaths(
        config_user_xml=config_user_xml,
        recent_projects=recent_projects,
        support_dir=support_dir,
        log_path=support_dir / "logs" / "davinci_resolve.log",
        library_root=support_dir / "Resolve Project Library" / "Resolve Projects",
        backup_root=backup_root,
    )


def build_orchestrator(tmp_path: Path) -> ResolveProjectStartupOrchestrator:
    paths = build_paths(tmp_path)
    config = ResolveStartupConfig(
        target_mode="existing",
        project_name="Demo Project",
        command="cmd /c exit 0",
        warmup_seconds=0,
        timeout_seconds=1,
        poll_interval_seconds=0.0,
    )
    return ResolveProjectStartupOrchestrator(
        config,
        paths=paths,
        process_lister=lambda: ["Resolve.exe                  42 Console                    1     42,000 K"],
        process_launcher=lambda args: None,
        process_killer=lambda names: None,
        command_runner=lambda command: 0,
        resolve_provider=lambda: None,
    )


def test_prepare_startup_target_updates_only_required_prefs(tmp_path: Path) -> None:
    orchestrator = build_orchestrator(tmp_path)

    prepared = orchestrator.prepare_startup_target()

    content = orchestrator.paths.config_user_xml.read_text(encoding="utf-8")
    assert prepared.startup_target == "Demo Project"
    assert "<AutoReloadPrevProj>true</AutoReloadPrevProj>" in content
    assert "<LastWorkingProject>Demo Project</LastWorkingProject>" in content


def test_backup_and_restore_round_trip(tmp_path: Path) -> None:
    orchestrator = build_orchestrator(tmp_path)
    original = orchestrator.paths.config_user_xml.read_text(encoding="utf-8")

    prepared = orchestrator.prepare_startup_target()
    orchestrator.restore_preferences(prepared.prefs_backup_dir)

    restored = orchestrator.paths.config_user_xml.read_text(encoding="utf-8")
    assert restored == original


def test_project_exists_in_library_when_not_in_recent(tmp_path: Path) -> None:
    orchestrator = build_orchestrator(tmp_path)
    orchestrator.paths.recent_projects.write_text("", encoding="utf-8")
    project_dir = (
        orchestrator.paths.library_root
        / "Users"
        / "guest"
        / "Projects"
        / "Library Project"
    )
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "Project.db").write_text("", encoding="utf-8")

    assert orchestrator.project_exists_in_library("Library Project") is True


def test_verify_current_project_uses_log_markers_for_likely_state(tmp_path: Path) -> None:
    orchestrator = build_orchestrator(tmp_path)
    orchestrator.update_startup_preferences("Demo Project")
    orchestrator.paths.log_path.write_text(
        "[x] | SyManager.ProjectManager | INFO | Loading project (Demo Project) from project library (Local Database) took 300 ms\n",
        encoding="utf-8",
    )
    prepared = PreparedStartupTarget(
        startup_target="Demo Project",
        startup_mode="existing",
        prefs_backup_dir=tmp_path / "backup",
        log_size_before_launch=0,
        recent_project_names=["Demo Project"],
    )

    state, current_project_name, reason, scripting_connected = orchestrator.verify_current_project(
        prepared
    )

    assert state == "likely"
    assert current_project_name == "Demo Project"
    assert "Resolve logs" in reason
    assert scripting_connected is False


def test_verify_current_project_fails_when_target_missing_and_no_log_signal(tmp_path: Path) -> None:
    orchestrator = build_orchestrator(tmp_path)
    prepared = PreparedStartupTarget(
        startup_target="Missing Project",
        startup_mode="existing",
        prefs_backup_dir=tmp_path / "backup",
        log_size_before_launch=0,
        recent_project_names=[],
    )

    state, current_project_name, reason, scripting_connected = orchestrator.verify_current_project(
        prepared
    )

    assert state == "failed"
    assert current_project_name != "Missing Project"
    assert "did not confirm" in reason
    assert scripting_connected is False
