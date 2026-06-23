from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from sqlalchemy import inspect as sa_inspect
from sqlmodel import Session, create_engine, select

from scoutbot_module.db.models import (
    AuditLog,
    Project,
    Target,
    TargetLink,
    Watch,
    Workspace,
)
from scoutbot_module.db.repo import (
    create_target,
    export_workspace_to_yaml,
    import_seed_yaml,
)
from scoutbot_module.db.session import init_schema


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite://", echo=False)
    init_schema(engine)
    session = Session(engine)
    yield session
    session.close()


def _make_seed(tmp_path: Path, name: str = "TestWorkspace") -> Path:
    data = {
        "workspace": {
            "name": name,
            "description": "Test workspace",
        },
        "projects": [
            {
                "name": "TestProject",
                "homepage_url": "https://example.com",
                "tags": ["test"],
                "targets": [
                    {
                        "title": "Test Target",
                        "url": "https://example.com/page",
                        "kind": "website",
                        "priority": "high",
                    },
                    {
                        "title": "Test Blog",
                        "url": "https://example.com/blog",
                        "kind": "blog",
                        "priority": "medium",
                    },
                ],
            }
        ],
    }
    path = tmp_path / "seed.yml"
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f)
    return path


def _write_seed_data(tmp_path: Path, data: dict | list, name: str = "seed.yml") -> Path:
    path = tmp_path / name
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f)
    return path


def test_init_db_creates_expected_tables(db_session: Session) -> None:
    engine = db_session.get_bind()
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    assert "workspaces" in tables
    assert "projects" in tables
    assert "targets" in tables
    assert "watches" in tables
    assert "target_links" in tables
    assert "signals" in tables
    assert "audit_log" in tables

    ws = Workspace(name="test", description="desc")
    db_session.add(ws)
    db_session.commit()

    proj = Project(workspace_id=ws.workspace_id, name="proj")
    db_session.add(proj)
    db_session.commit()

    tgt = Target(project_id=proj.project_id, title="tgt", url="https://example.com")
    db_session.add(tgt)
    db_session.commit()

    link = TargetLink(
        source_target_id=tgt.target_id,
        target_id=tgt.target_id,
        url="https://example.com/link",
    )
    db_session.add(link)
    db_session.commit()

    watch = Watch(target_id=tgt.target_id)
    db_session.add(watch)
    db_session.commit()

    audit = AuditLog(action="test")
    db_session.add(audit)
    db_session.commit()

    assert db_session.exec(select(Workspace)).all()
    assert db_session.exec(select(Project)).all()
    assert db_session.exec(select(Target)).all()
    assert db_session.exec(select(TargetLink)).all()
    assert db_session.exec(select(Watch)).all()
    assert db_session.exec(select(AuditLog)).all()


def test_seed_import_creates_workspace_project_target(
    db_session: Session, tmp_path: Path
) -> None:
    seed_path = _make_seed(tmp_path)
    count = import_seed_yaml(db_session, seed_path)

    assert count == 2

    workspaces = db_session.exec(select(Workspace)).all()
    assert len(workspaces) == 1
    assert workspaces[0].name == "TestWorkspace"

    projects = db_session.exec(select(Project)).all()
    assert len(projects) == 1
    assert projects[0].name == "TestProject"

    targets = db_session.exec(select(Target)).all()
    assert len(targets) == 2
    assert targets[0].title == "Test Target"
    assert targets[1].title == "Test Blog"


def test_seed_import_strips_target_strings(db_session: Session, tmp_path: Path) -> None:
    seed_path = _make_seed(tmp_path)
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    data["projects"][0]["targets"][0]["title"] = "  Test Target  "
    data["projects"][0]["targets"][0]["status"] = "  queued  "
    data["projects"][0]["targets"][0]["fetch_backend"] = "  html_requests  "
    seed_path = _write_seed_data(tmp_path, data)

    import_seed_yaml(db_session, seed_path)

    target = db_session.exec(
        select(Target).where(Target.url == "https://example.com/page")
    ).first()
    assert target is not None
    assert target.title == "Test Target"
    assert target.status == "queued"
    assert target.fetch_backend == "html_requests"


def test_seed_import_invalid_target_url_raises(
    db_session: Session, tmp_path: Path
) -> None:
    seed_path = _make_seed(tmp_path)
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    data["projects"][0]["targets"][0]["url"] = "ftp://example.com/file"
    seed_path = _write_seed_data(tmp_path, data)

    with pytest.raises(ValueError, match="url"):
        import_seed_yaml(db_session, seed_path)


def test_seed_import_missing_target_url_raises(
    db_session: Session, tmp_path: Path
) -> None:
    seed_path = _make_seed(tmp_path)
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    del data["projects"][0]["targets"][0]["url"]
    seed_path = _write_seed_data(tmp_path, data)

    with pytest.raises(ValueError, match="url"):
        import_seed_yaml(db_session, seed_path)


def test_seed_import_project_item_not_mapping_raises(
    db_session: Session, tmp_path: Path
) -> None:
    seed_path = _make_seed(tmp_path)
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    data["projects"][0] = "not-a-project-mapping"
    seed_path = _write_seed_data(tmp_path, data)

    with pytest.raises(ValueError, match=r"seed\.projects\[0\]"):
        import_seed_yaml(db_session, seed_path)


def test_seed_import_targets_not_list_raises(
    db_session: Session, tmp_path: Path
) -> None:
    seed_path = _make_seed(tmp_path)
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    data["projects"][0]["targets"] = {"title": "not a list"}
    seed_path = _write_seed_data(tmp_path, data)

    with pytest.raises(ValueError, match="targets"):
        import_seed_yaml(db_session, seed_path)


def test_seed_import_optional_valid_homepage_url_accepted(
    db_session: Session, tmp_path: Path
) -> None:
    seed_path = _make_seed(tmp_path)
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    data["projects"][0]["homepage_url"] = "http://example.com"
    seed_path = _write_seed_data(tmp_path, data)

    import_seed_yaml(db_session, seed_path)

    project = db_session.exec(select(Project)).first()
    assert project is not None
    assert project.homepage_url == "http://example.com"


def test_seed_import_invalid_homepage_url_raises(
    db_session: Session, tmp_path: Path
) -> None:
    seed_path = _make_seed(tmp_path)
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    data["projects"][0]["homepage_url"] = "mailto:hello@example.com"
    seed_path = _write_seed_data(tmp_path, data)

    with pytest.raises(ValueError, match="homepage_url"):
        import_seed_yaml(db_session, seed_path)


def test_seed_import_project_tags_string_raises(
    db_session: Session, tmp_path: Path
) -> None:
    seed_path = _make_seed(tmp_path)
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    data["projects"][0]["tags"] = "test"
    seed_path = _write_seed_data(tmp_path, data)

    with pytest.raises(ValueError, match=r"seed\.projects\[0\]\.tags"):
        import_seed_yaml(db_session, seed_path)


def test_seed_import_empty_target_status_raises(
    db_session: Session, tmp_path: Path
) -> None:
    seed_path = _make_seed(tmp_path)
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    data["projects"][0]["targets"][0]["status"] = ""
    seed_path = _write_seed_data(tmp_path, data)

    with pytest.raises(ValueError, match=r"seed\.projects\[0\]\.targets\[0\]\.status"):
        import_seed_yaml(db_session, seed_path)


def test_seed_import_numeric_target_fetch_backend_raises(
    db_session: Session, tmp_path: Path
) -> None:
    seed_path = _make_seed(tmp_path)
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    data["projects"][0]["targets"][0]["fetch_backend"] = 123
    seed_path = _write_seed_data(tmp_path, data)

    with pytest.raises(
        ValueError,
        match=r"seed\.projects\[0\]\.targets\[0\]\.fetch_backend",
    ):
        import_seed_yaml(db_session, seed_path)


def test_seed_import_is_idempotent(db_session: Session, tmp_path: Path) -> None:
    seed_path = _make_seed(tmp_path)
    first_count = import_seed_yaml(db_session, seed_path)
    second_count = import_seed_yaml(db_session, seed_path)

    workspaces = db_session.exec(select(Workspace)).all()
    assert len(workspaces) == 1

    projects = db_session.exec(select(Project)).all()
    assert len(projects) == 1

    targets = db_session.exec(select(Target)).all()
    assert len(targets) == 2
    assert first_count == 2
    assert second_count == 0


def test_seed_import_creates_audit_log(db_session: Session, tmp_path: Path) -> None:
    seed_path = _make_seed(tmp_path)
    import_seed_yaml(db_session, seed_path)

    audit = db_session.exec(select(AuditLog)).all()
    assert len(audit) >= 1
    assert audit[0].action == "import_seed"


def test_export_writes_yaml_without_secrets(
    db_session: Session, tmp_path: Path
) -> None:
    seed_path = _make_seed(tmp_path)
    import_seed_yaml(db_session, seed_path)

    output_path = tmp_path / "export.yml"
    export_workspace_to_yaml(db_session, "TestWorkspace", output_path)

    assert output_path.exists()
    with output_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["workspace"]["name"] == "TestWorkspace"
    assert len(data["projects"]) == 1
    assert len(data["projects"][0]["targets"]) == 2

    content = output_path.read_text(encoding="utf-8")
    assert "TELEGRAM_BOT_TOKEN" not in content
    assert "CHANGEDETECTION_API_KEY" not in content
    assert "api_key" not in content.lower()


def test_export_reads_targets_from_sqlite(db_session: Session, tmp_path: Path) -> None:
    seed_path = _make_seed(tmp_path)
    import_seed_yaml(db_session, seed_path)

    proj = db_session.exec(select(Project)).first()
    assert proj is not None
    create_target(
        db_session,
        proj.project_id,
        title="Runtime Target",
        url="https://example.com/runtime",
        kind="docs",
    )

    output_path = tmp_path / "export.yml"
    export_workspace_to_yaml(db_session, "TestWorkspace", output_path)
    data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    urls = [item["url"] for item in data["projects"][0]["targets"]]

    assert "https://example.com/runtime" in urls
    assert len(urls) == 3


def test_export_unknown_workspace_raises(db_session: Session, tmp_path: Path) -> None:
    output_path = tmp_path / "export.yml"
    with pytest.raises(ValueError, match="not found"):
        export_workspace_to_yaml(db_session, "DoesNotExist", output_path)
