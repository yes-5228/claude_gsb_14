"""点位调整相关测试：历史归属保留、统计口径连续、调整可追溯。"""

from datetime import datetime, timedelta

from sqlalchemy import inspect

from tests.conftest import full_items


def _make_restroom(client, district, address="旧址路 1 号", **extra):
    payload = {
        "name": f"点位调整公厕-{district}",
        "district": district,
        "address": address,
        "longitude": 120.1,
        "latitude": 30.2,
    }
    payload.update(extra)
    response = client.post("/api/v1/restrooms", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _add_inspection(client, restroom_id, score=9.0, inspect_time=None):
    payload = {
        "restroom_id": restroom_id,
        "inspector": "李巡查",
        "items": full_items(score),
    }
    if inspect_time is not None:
        payload["inspect_time"] = inspect_time.isoformat()
    response = client.post("/api/v1/inspections", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _district_map(rows, key="district"):
    return {row[key]: row for row in rows}


def test_location_adjustment_keeps_history_and_keeps_stats_continuous(client):
    old = "调整前区域-甲"
    new = "调整后区域-乙"
    room = _make_restroom(client, old)
    rid = room["id"]

    # 调整前：一条巡查 + 一条关联的待整改问题，归属旧区域
    old_inspection = _add_inspection(client, rid, score=9.0)
    old_issue = client.post(
        "/api/v1/issues",
        json={
            "restroom_id": rid,
            "inspection_id": old_inspection["id"],
            "title": "旧址遗留问题",
            "category": "保洁不到位",
            "severity": "一般",
            "reporter": "李巡查",
        },
    ).json()
    assert old_issue["district"] == old

    # 执行点位调整 甲 -> 乙
    adjusted = client.post(
        f"/api/v1/restrooms/{rid}/location-adjustments",
        json={
            "to_district": new,
            "to_address": "新址路 8 号",
            "to_longitude": 121.5,
            "to_latitude": 31.0,
            "reason": "行政区划调整，公厕划入新区",
            "operator": "管理员",
        },
    )
    assert adjusted.status_code == 201, adjusted.text
    record = adjusted.json()
    assert record["from_district"] == old
    assert record["to_district"] == new
    assert record["from_address"] == "旧址路 1 号"
    assert record["to_address"] == "新址路 8 号"
    assert record["reason"]

    # 公厕当前位置已是新区域
    detail = client.get(f"/api/v1/restrooms/{rid}").json()
    assert detail["district"] == new
    assert detail["address"] == "新址路 8 号"
    assert detail["location_adjustment_count"] == 1

    # 历史巡查/问题的位置快照保持旧区域（原位置保留）
    history_inspection = client.get(f"/api/v1/inspections/{old_inspection['id']}").json()
    assert history_inspection["district"] == old
    assert history_inspection["address"] == "旧址路 1 号"
    assert history_inspection["restroom"]["district"] == new  # 台账当前为新区
    history_issue = client.get(f"/api/v1/issues/{old_issue['id']}").json()
    assert history_issue["district"] == old
    assert history_issue["address"] == "旧址路 1 号"

    # 调整后新建的巡查/问题归属新区域
    new_inspection = _add_inspection(client, rid, score=8.0)
    assert new_inspection["district"] == new
    assert new_inspection["address"] == "新址路 8 号"
    new_issue = client.post(
        "/api/v1/issues",
        json={"restroom_id": rid, "title": "新址新问题", "reporter": "王巡查"},
    ).json()
    # 先让新问题进入未闭环之外，避免干扰旧区域 open 统计：保持其待整改即可（归新区）
    assert new_issue["district"] == new

    # 看板区域统计：旧区只留历史（公厕数 0，均分 90，未闭环 1），新区含当前（公厕数 1，均分 80）
    dashboard = client.get("/api/v1/stats/dashboard").json()
    stats = _district_map(dashboard["districts"])
    assert old in stats and new in stats
    assert stats[old]["restroom_count"] == 0
    assert stats[old]["avg_score"] == 90.0
    assert stats[old]["issue_open"] == 1
    assert stats[new]["restroom_count"] == 1
    assert stats[new]["avg_score"] == 80.0

    # 公厕维度累计仍为前后之和
    refreshed = client.get(f"/api/v1/restrooms/{rid}").json()
    assert refreshed["inspection_count"] == 2
    assert refreshed["total_issue_count"] == 2

    # 区域下拉同时含新旧区域；列表按快照区域筛选
    districts = client.get("/api/v1/restrooms/meta/districts").json()
    assert old in districts and new in districts
    old_inspections = client.get("/api/v1/inspections", params={"district": old}).json()
    assert {item["id"] for item in old_inspections["items"]} == {old_inspection["id"]}
    new_inspections = client.get("/api/v1/inspections", params={"district": new}).json()
    assert {item["id"] for item in new_inspections["items"]} == {new_inspection["id"]}
    old_issues = client.get("/api/v1/issues", params={"district": old}).json()
    assert {item["id"] for item in old_issues["items"]} == {old_issue["id"]}
    new_issues = client.get("/api/v1/issues", params={"district": new}).json()
    assert {item["id"] for item in new_issues["items"]} == {new_issue["id"]}

    # 调整记录可查询，最新在前
    logs = client.get(f"/api/v1/restrooms/{rid}/location-adjustments").json()
    assert len(logs) == 1
    assert logs[0]["to_district"] == new


def test_adjust_to_same_location_rejected_and_patch_cannot_change_location(client):
    room = _make_restroom(client, "锁死区域", address="锁死路 1 号")
    rid = room["id"]

    noop = client.post(
        f"/api/v1/restrooms/{rid}/location-adjustments",
        json={
            "to_district": "锁死区域",
            "to_address": "锁死路 1 号",
            "to_longitude": 120.1,
            "to_latitude": 30.2,
            "reason": "无变化",
        },
    )
    assert noop.status_code == 400

    # 普通 PATCH 不允许携带点位字段
    blocked = client.patch(f"/api/v1/restrooms/{rid}", json={"district": "别的区域"})
    assert blocked.status_code == 422
    blocked_addr = client.patch(f"/api/v1/restrooms/{rid}", json={"address": "别的地址"})
    assert blocked_addr.status_code == 422

    # 非点位字段仍可正常更新
    ok = client.patch(f"/api/v1/restrooms/{rid}", json={"status": "维修中", "manager": "新责任人"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "维修中"
    assert ok.json()["district"] == "锁死区域"


def test_backdated_record_uses_pre_adjustment_location(client):
    old = "补录旧区域"
    new = "补录新区域"
    room = _make_restroom(client, old)
    rid = room["id"]

    adjusted = client.post(
        f"/api/v1/restrooms/{rid}/location-adjustments",
        json={"to_district": new, "to_address": "新址", "reason": "道路更名"},
    )
    assert adjusted.status_code == 201

    # 调整之后补录一条"昨天"的巡查：三级回退应取最早调整的 from_*，归属旧区域
    past = datetime.now() - timedelta(days=2)
    backdated = _add_inspection(client, rid, score=7.0, inspect_time=past)
    assert backdated["district"] == old
    assert backdated["address"] == "旧址路 1 号"

    # 群众反馈（不关联巡查）补录历史问题，同样归属旧区域
    past_issue = client.post(
        "/api/v1/issues",
        json={
            "restroom_id": rid,
            "title": "历史反馈",
            "report_time": past.isoformat(),
            "reporter": "群众",
        },
    ).json()
    assert past_issue["district"] == old

    # 当下新建的记录归属新区域
    current = _add_inspection(client, rid, score=9.0)
    assert current["district"] == new


def test_multiple_adjustments_ordered_and_linked_issue_inherits(client):
    first, second, third = "连续区域-壹", "连续区域-贰", "连续区域-叁"
    room = _make_restroom(client, first)
    rid = room["id"]

    for target in (second, third):
        resp = client.post(
            f"/api/v1/restrooms/{rid}/location-adjustments",
            json={"to_district": target, "reason": f"调整到{target}"},
        )
        assert resp.status_code == 201, resp.text

    logs = client.get(f"/api/v1/restrooms/{rid}/location-adjustments").json()
    assert [log["to_district"] for log in logs] == [third, second]
    assert logs[-1]["from_district"] == first

    # 关联巡查的问题即便在调整后上报，也继承该巡查（旧点位）的快照
    past = datetime.now() - timedelta(days=1)
    old_inspection = _add_inspection(client, rid, score=8.0, inspect_time=past)
    assert old_inspection["district"] == first
    linked = client.post(
        "/api/v1/issues",
        json={"restroom_id": rid, "inspection_id": old_inspection["id"], "title": "关联旧巡查"},
    ).json()
    assert linked["district"] == first


def test_force_delete_cascades_adjustment_logs(client):
    from app.core.database import SessionLocal
    from app.models import LocationAdjustment, Restroom

    room = _make_restroom(client, "级联区域")
    rid = room["id"]
    resp = client.post(
        f"/api/v1/restrooms/{rid}/location-adjustments",
        json={"to_district": "级联区域-新", "reason": "调整后删除"},
    )
    assert resp.status_code == 201

    with SessionLocal() as db:
        assert db.query(LocationAdjustment).filter_by(restroom_id=rid).count() == 1
        assert db.get(Restroom, rid) is not None

    # 无关联巡查/问题，直接删除即可；调整日志随之级联清除
    deleted = client.delete(f"/api/v1/restrooms/{rid}")
    assert deleted.status_code == 200
    with SessionLocal() as db:
        assert db.query(LocationAdjustment).filter_by(restroom_id=rid).count() == 0


def test_startup_migration_backfills_legacy_db(tmp_path):
    """模拟缺少快照列的老库：迁移补列、按台账回填且幂等。"""
    from sqlalchemy import create_engine, text

    from app.core.migrations import run_startup_migrations
    from app.core.database import Base
    from app import models  # noqa: F401  注册模型

    legacy = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{legacy}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE restrooms ("
                "id INTEGER PRIMARY KEY, code VARCHAR(32), name VARCHAR(120), "
                "district VARCHAR(60), address VARCHAR(200), longitude FLOAT, latitude FLOAT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE inspections ("
                "id INTEGER PRIMARY KEY, restroom_id INTEGER)"
            )
        )
        conn.execute(text("CREATE TABLE issues (id INTEGER PRIMARY KEY, restroom_id INTEGER)"))
        conn.execute(
            text(
                "INSERT INTO restrooms (id, code, name, district, address, longitude, latitude) "
                "VALUES (1, 'WC-0001', '老库公厕', '老库区域', '老库地址', 120.0, 30.0)"
            )
        )
        conn.execute(text("INSERT INTO inspections (id, restroom_id) VALUES (1, 1)"))
        conn.execute(text("INSERT INTO issues (id, restroom_id) VALUES (1, 1)"))

    # create_all 只补建新表，不改动既有 inspections/issues
    Base.metadata.create_all(bind=engine)
    run_startup_migrations(engine)

    inspector = inspect(engine)
    inspection_cols = {c["name"] for c in inspector.get_columns("inspections")}
    issue_cols = {c["name"] for c in inspector.get_columns("issues")}
    assert {"district", "address", "longitude", "latitude"} <= inspection_cols
    assert {"district", "address", "longitude", "latitude"} <= issue_cols

    with engine.begin() as conn:
        ins = conn.execute(text("SELECT district, address, longitude FROM inspections")).first()
        iss = conn.execute(text("SELECT district, address, latitude FROM issues")).first()
        version = conn.execute(
            text("SELECT version FROM schema_migrations")
        ).scalars().all()
    assert tuple(ins) == ("老库区域", "老库地址", 120.0)
    assert tuple(iss) == ("老库区域", "老库地址", 30.0)
    assert version == ["0001_location_snapshots"]

    # 再执行一次不报错、不重复登记
    run_startup_migrations(engine)
    with engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM schema_migrations")).scalar()
    assert count == 1
