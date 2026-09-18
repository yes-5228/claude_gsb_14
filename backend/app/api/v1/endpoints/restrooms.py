"""公厕台账接口。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import PaginationDep, build_meta
from app.core.database import get_db
from app.schemas.adjustment import (
    RestroomAdjustmentListItem,
    RestroomAdjustmentOut,
    RestroomRelocationPayload,
)
from app.schemas.common import MessageOut, Page
from app.schemas.restroom import RestroomCreate, RestroomDetail, RestroomOut, RestroomUpdate
from app.services import adjustment_service, restroom_service

router = APIRouter(prefix="/restrooms", tags=["公厕台账"])


@router.get("/meta/districts", response_model=list[str], summary="区域列表")
def list_districts(db: Annotated[Session, Depends(get_db)]) -> list[str]:
    return restroom_service.list_districts(db)


@router.get(
    "/location-adjustments",
    response_model=Page[RestroomAdjustmentListItem],
    summary="点位调整记录（全局查询）",
)
def list_location_adjustments(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    restroom_id: Annotated[int | None, Query(description="按公厕过滤")] = None,
    district: Annotated[str | None, Query(description="按区域过滤（命中迁出或迁入区域）")] = None,
    operator: Annotated[str | None, Query(description="按操作人模糊过滤")] = None,
    keyword: Annotated[str | None, Query(description="原因/说明/操作人模糊搜索")] = None,
    date_from: Annotated[date | None, Query(description="调整开始日期")] = None,
    date_to: Annotated[date | None, Query(description="调整结束日期")] = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> Page[RestroomAdjustmentListItem]:
    rows, total = adjustment_service.list_adjustments(
        db,
        restroom_id=restroom_id,
        district=district,
        operator=operator,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        page=pagination.page,
        page_size=pagination.page_size,
        order=order,
    )
    return Page[RestroomAdjustmentListItem](
        items=[RestroomAdjustmentListItem.model_validate(row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.get("", response_model=Page[RestroomOut], summary="公厕列表")
def list_restrooms(
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
    keyword: Annotated[str | None, Query(description="名称/编号/地址/责任人模糊搜索")] = None,
    district: Annotated[str | None, Query(description="所属区域")] = None,
    status: Annotated[str | None, Query(description="开放状态")] = None,
    grade: Annotated[str | None, Query(description="公厕等级")] = None,
    sort_by: Annotated[str, Query(description="排序字段")] = "created_at",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> Page[RestroomOut]:
    rows, total = restroom_service.list_restrooms(
        db,
        keyword=keyword,
        district=district,
        status=status,
        grade=grade,
        page=pagination.page,
        page_size=pagination.page_size,
        sort_by=sort_by,
        order=order,
    )
    return Page[RestroomOut](
        items=[RestroomOut.model_validate(row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.post("", response_model=RestroomOut, status_code=201, summary="新增公厕")
def create_restroom(
    payload: RestroomCreate, db: Annotated[Session, Depends(get_db)]
) -> RestroomOut:
    return RestroomOut.model_validate(restroom_service.create_restroom(db, payload))


@router.get("/{restroom_id}", response_model=RestroomDetail, summary="公厕详情")
def get_restroom(restroom_id: int, db: Annotated[Session, Depends(get_db)]) -> RestroomDetail:
    return restroom_service.get_restroom_detail(db, restroom_id)


@router.patch("/{restroom_id}", response_model=RestroomOut, summary="更新公厕")
def update_restroom(
    restroom_id: int, payload: RestroomUpdate, db: Annotated[Session, Depends(get_db)]
) -> RestroomOut:
    return RestroomOut.model_validate(restroom_service.update_restroom(db, restroom_id, payload))


@router.delete("/{restroom_id}", response_model=MessageOut, summary="删除公厕")
def delete_restroom(
    restroom_id: int,
    db: Annotated[Session, Depends(get_db)],
    force: Annotated[bool, Query(description="为 true 时级联删除巡查与问题记录")] = False,
) -> MessageOut:
    restroom_service.delete_restroom(db, restroom_id, force=force)
    return MessageOut(message="删除成功")


@router.get(
    "/{restroom_id}/location-adjustments",
    response_model=Page[RestroomAdjustmentOut],
    summary="单座公厕的点位调整历史",
)
def list_restroom_adjustments(
    restroom_id: int,
    db: Annotated[Session, Depends(get_db)],
    pagination: PaginationDep,
) -> Page[RestroomAdjustmentOut]:
    rows, total = adjustment_service.list_for_restroom(
        db, restroom_id, page=pagination.page, page_size=pagination.page_size
    )
    return Page[RestroomAdjustmentOut](
        items=[RestroomAdjustmentOut.model_validate(row) for row in rows],
        meta=build_meta(total, pagination),
    )


@router.post(
    "/{restroom_id}/location-adjustments",
    response_model=RestroomAdjustmentOut,
    status_code=201,
    summary="调整公厕点位（区域/地址/经纬度）",
)
def relocate_restroom(
    restroom_id: int,
    payload: RestroomRelocationPayload,
    db: Annotated[Session, Depends(get_db)],
) -> RestroomAdjustmentOut:
    adjustment = adjustment_service.relocate(db, restroom_id, payload)
    return RestroomAdjustmentOut.model_validate(adjustment)
