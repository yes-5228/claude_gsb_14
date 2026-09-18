"""点位调整与时点归属测试。"""

from datetime import datetime, timedelta

from tests.conftest import full_items

OLD_DISTRICT = "点位测试-调整前区域"
NEW_DISTRICT = "点位测试-调整后区域"
OLD_ADDRESS = "点位测试路 1 号"
NEW_ADDRESS = "点位测试新址 8 号"


def _make_restroom(client):
    return client.post(
        "/api/v1/restrooms",
        json={
            "name": "点位调整测试公厕",
            "district": OLD_DISTRICT,
            "address": OLD_ADDRESS,
        },
    ).json()


def test_location_snapshot_and_relocation(client):
    restroom = _make_restroom(client)
    rid = restroom["id"]

    # 调整前：巡查与问题均固化「发生时」位置（旧区域）
    inspection_before = client.post(
        "/api/v1/inspections",
        json={"restroom_id": rid, "inspector": "点位巡查员", "items": full_items(9)},
    ).json()
    assert inspection_before["district"] == OLD_DISTRICT
    assert inspection_before["address"] == OLD_ADDRESS

    issue_before = client.post(
        "/api/v1/issues",
        json={
            "restroom_id": rid,
            "title": "点位调整前的问题",
            "reporter": "点位巡查员",
            "deadline": (datetime.now() + timedelta(days=2)).isoformat(),
        },
    ).json()
    assert issue_before["district"] == OLD_DISTRICT
    assert issue_before["address"] == OLD_ADDRESS

    # 执行点位调整
    adjustment = client.post(
        f"/api/v1/restrooms/{rid}/location-adjustments",
        json={
            "district": NEW_DISTRICT,
            "address": NEW_ADDRESS,
            "longitude": 120.123,
            "latitude": 30.456,
            "reason": "道路改造，公厕整体迁移",
            "operator": "点位管理员",
            "remark": "迁移至新址",
        },
    )
    assert adjustment.status_code == 201, adjustment.text
    record = adjustment.json()
    assert record["district_from"] == OLD_DISTRICT
    assert record["district_to"] == NEW_DISTRICT
    assert record["address_from"] == OLD_ADDRESS
    assert record["address_to"] == NEW_ADDRESS
    assert record["longitude_to"] == 120.123
    assert record["latitude_to"] == 30.456
    assert record["reason"] == "道路改造，公厕整体迁移"
    assert record["operator"] == "点位管理员"

    # 公厕当前位置已更新
    detail = client.get(f"/api/v1/restrooms/{rid}").json()
    assert detail["district"] == NEW_DISTRICT
    assert detail["address"] == NEW_ADDRESS

    # 调整后新发生的巡查固化「新区域」
    inspection_after = client.post(
        "/api/v1/inspections",
        json={"restroom_id": rid, "inspector": "点位巡查员", "items": full_items(8)},
    ).json()
    assert inspection_after["district"] == NEW_DISTRICT

    # 历史记录不搬家：旧巡查/问题仍属旧区域，新巡查属新区域
    old_insp = client.get(
        "/api/v1/inspections", params={"district": OLD_DISTRICT}
    ).json()
    assert {row["id"] for row in old_insp["items"]} >= {inspection_before["id"]}
    assert inspection_after["id"] not in {row["id"] for row in old_insp["items"]}

    new_insp = client.get(
        "/api/v1/inspections", params={"district": NEW_DISTRICT}
    ).json()
    assert {row["id"] for row in new_insp["items"]} >= {inspection_after["id"]}
    assert inspection_before["id"] not in {row["id"] for row in new_insp["items"]}

    old_issues = client.get("/api/v1/issues", params={"district": OLD_DISTRICT}).json()
    assert issue_before["id"] in {row["id"] for row in old_issues["items"]}

    # 历史问题详情仍带原位置，且公厕简要信息为当前位置
    issue_detail = client.get(f"/api/v1/issues/{issue_before['id']}").json()
    assert issue_detail["district"] == OLD_DISTRICT
    assert issue_detail["restroom"]["district"] == NEW_DISTRICT


def test_relocation_validation(client):
    restroom = _make_restroom(client)
    rid = restroom["id"]

    # 位置未变化 -> 400
    same = client.post(
        f"/api/v1/restrooms/{rid}/location-adjustments",
        json={"district": OLD_DISTRICT, "address": OLD_ADDRESS, "reason": "无变化", "operator": "甲"},
    )
    assert same.status_code == 400
    assert "未发生变化" in same.json()["detail"]

    # 缺少原因/操作人 -> 422
    invalid = client.post(
        f"/api/v1/restrooms/{rid}/location-adjustments",
        json={"district": NEW_DISTRICT},
    )
    assert invalid.status_code == 422

    # 普通 PATCH 无法修改区域（位置字段被忽略）
    patched = client.patch(f"/api/v1/restrooms/{rid}", json={"district": "试图绕过"}).json()
    assert patched["district"] == OLD_DISTRICT


def test_adjustment_records_queryable(client):
    restroom = _make_restroom(client)
    rid = restroom["id"]
    client.post(
        f"/api/v1/restrooms/{rid}/location-adjustments",
        json={"district": NEW_DISTRICT, "reason": "区划调整", "operator": "留痕管理员"},
    )

    # 单座历史
    per_restroom = client.get(f"/api/v1/restrooms/{rid}/location-adjustments").json()
    assert per_restroom["meta"]["total"] >= 1
    assert per_restroom["items"][0]["district_to"] == NEW_DISTRICT

    # 全局查询
    global_list = client.get("/api/v1/restrooms/location-adjustments").json()
    assert per_restroom["items"][0]["id"] in {row["id"] for row in global_list["items"]}
    assert global_list["items"][0]["restroom"]["id"] == rid

    # 迁出、迁入区域都能命中
    hit_from = client.get(
        "/api/v1/restrooms/location-adjustments", params={"district": OLD_DISTRICT}
    ).json()
    hit_to = client.get(
        "/api/v1/restrooms/location-adjustments", params={"district": NEW_DISTRICT}
    ).json()
    assert hit_from["meta"]["total"] >= 1
    assert hit_to["meta"]["total"] >= 1

    # 关键字（原因/操作人）
    by_keyword = client.get(
        "/api/v1/restrooms/location-adjustments", params={"keyword": "留痕管理员"}
    ).json()
    assert by_keyword["meta"]["total"] >= 1


def test_district_stats_continuous_across_relocation(client):
    # 使用本用例专属区域，避免与其他用例的全局按区域聚合相互干扰
    stats_old = "点位测试-统计旧区域"
    stats_new = "点位测试-统计新区域"
    restroom = client.post(
        "/api/v1/restrooms",
        json={"name": "点位统计测试公厕", "district": stats_old},
    ).json()
    rid = restroom["id"]
    client.post(
        "/api/v1/inspections",
        json={"restroom_id": rid, "inspector": "统计巡查", "items": full_items(7)},
    )
    client.post(
        f"/api/v1/restrooms/{rid}/location-adjustments",
        json={"district": stats_new, "reason": "区划调整", "operator": "统计管理员"},
    )

    payload = client.get("/api/v1/stats/dashboard", params={"trend_days": 7}).json()
    by_district = {item["district"]: item for item in payload["districts"]}

    # 历史巡查均分仍计入旧区域，当前公厕计数计入新区域
    assert stats_old in by_district
    assert by_district[stats_old]["avg_score"] == 70.0
    assert by_district[stats_old]["restroom_count"] == 0
    assert by_district[stats_new]["restroom_count"] >= 1
