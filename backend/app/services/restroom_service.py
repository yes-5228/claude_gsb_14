"""公厕台账业务逻辑。"""

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import OPEN_ISSUE_STATUSES
from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.models import Inspection, Issue, LocationAdjustment, Restroom
from app.schemas.restroom import (
    LocationAdjustmentCreate,
    RestroomCreate,
    RestroomDetail,
    RestroomOut,
    RestroomUpdate,
)

SORTABLE_FIELDS = {
    "code": Restroom.code,
    "name": Restroom.name,
    "district": Restroom.district,
    "created_at": Restroom.created_at,
    "updated_at": Restroom.updated_at,
}


def _next_code(db: Session) -> str:
    """生成形如 WC-0007 的公厕编号。"""
    seq = (db.scalar(select(func.count()).select_from(Restroom)) or 0) + 1
    while True:
        code = f"WC-{seq:04d}"
        if not db.scalar(select(Restroom.id).where(Restroom.code == code)):
            return code
        seq += 1


def get_restroom(db: Session, restroom_id: int) -> Restroom:
    restroom = db.get(Restroom, restroom_id)
    if restroom is None:
        raise NotFoundError(f"公厕 {restroom_id} 不存在")
    return restroom


def list_restrooms(
    db: Session,
    *,
    keyword: str | None = None,
    district: str | None = None,
    status: str | None = None,
    grade: str | None = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = "created_at",
    order: str = "desc",
) -> tuple[list[Restroom], int]:
    stmt = select(Restroom)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                Restroom.name.like(like),
                Restroom.code.like(like),
                Restroom.address.like(like),
                Restroom.manager.like(like),
            )
        )
    if district:
        stmt = stmt.where(Restroom.district == district)
    if status:
        stmt = stmt.where(Restroom.status == status)
    if grade:
        stmt = stmt.where(Restroom.grade == grade)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column = SORTABLE_FIELDS.get(sort_by, Restroom.created_at)
    stmt = stmt.order_by(column.desc() if order == "desc" else column.asc(), Restroom.id.desc())
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return rows, total


def list_districts(db: Session) -> list[str]:
    """区域下拉：当前台账区域与历史巡查/问题快照区域的并集。

    保留只存在历史数据的旧区域，保证点位调整后仍可按旧区域筛选与统计。
    """
    districts: set[str] = set()
    districts.update(
        d for d in db.scalars(select(Restroom.district).distinct()) if d
    )
    districts.update(
        d for d in db.scalars(select(Inspection.district).distinct()) if d
    )
    districts.update(d for d in db.scalars(select(Issue.district).distinct()) if d)
    return sorted(districts)


def location_as_of(
    db: Session, restroom_id: int, moment: datetime
) -> tuple[str, str, float | None, float | None]:
    """公厕在某时刻的点位（区域、地址、经纬度），供新建巡查/问题时冻结快照。

    三级回退：
    1. 生效时间不晚于 moment 的最新一次调整 -> 取其 to_*；
    2. 存在更早调整（moment 早于首次调整）-> 取最早一次调整的 from_*；
    3. 从未调整 -> 取当前台账位置。
    """
    latest = db.scalars(
        select(LocationAdjustment)
        .where(
            LocationAdjustment.restroom_id == restroom_id,
            LocationAdjustment.effective_at <= moment,
        )
        .order_by(LocationAdjustment.effective_at.desc(), LocationAdjustment.id.desc())
        .limit(1)
    ).first()
    if latest is not None:
        return latest.to_district, latest.to_address, latest.to_longitude, latest.to_latitude

    first = db.scalars(
        select(LocationAdjustment)
        .where(LocationAdjustment.restroom_id == restroom_id)
        .order_by(LocationAdjustment.effective_at.asc(), LocationAdjustment.id.asc())
        .limit(1)
    ).first()
    if first is not None:
        return (
            first.from_district,
            first.from_address,
            first.from_longitude,
            first.from_latitude,
        )

    restroom = get_restroom(db, restroom_id)
    return restroom.district, restroom.address, restroom.longitude, restroom.latitude


def list_adjustments(db: Session, restroom_id: int) -> list[LocationAdjustment]:
    get_restroom(db, restroom_id)
    return list(
        db.scalars(
            select(LocationAdjustment)
            .where(LocationAdjustment.restroom_id == restroom_id)
            .order_by(LocationAdjustment.effective_at.desc(), LocationAdjustment.id.desc())
        )
    )


def adjust_location(
    db: Session, restroom_id: int, payload: LocationAdjustmentCreate
) -> LocationAdjustment:
    """调整公厕点位：记录原值/新值流水并更新台账，历史巡查/问题快照不变。"""
    restroom = get_restroom(db, restroom_id)
    target = (
        payload.to_district.strip(),
        payload.to_address.strip(),
        payload.to_longitude,
        payload.to_latitude,
    )
    current = (restroom.district, restroom.address, restroom.longitude, restroom.latitude)
    if target == current:
        raise DomainError("调整后的点位与当前点位完全相同，无需调整")

    adjustment = LocationAdjustment(
        restroom_id=restroom_id,
        reason=payload.reason,
        operator=payload.operator,
        effective_at=datetime.now(),
        from_district=restroom.district,
        to_district=target[0],
        from_address=restroom.address,
        to_address=target[1],
        from_longitude=restroom.longitude,
        to_longitude=target[2],
        from_latitude=restroom.latitude,
        to_latitude=target[3],
    )
    restroom.district = target[0]
    restroom.address = target[1]
    restroom.longitude = target[2]
    restroom.latitude = target[3]
    db.add(adjustment)
    db.commit()
    db.refresh(adjustment)
    return adjustment


def create_restroom(db: Session, payload: RestroomCreate) -> Restroom:
    data = payload.model_dump()
    code = (data.pop("code") or "").strip() or _next_code(db)
    if db.scalar(select(Restroom.id).where(Restroom.code == code)):
        raise DomainError(f"公厕编号 {code} 已存在")
    data = {key: (value.value if hasattr(value, "value") else value) for key, value in data.items()}
    restroom = Restroom(code=code, **data)
    db.add(restroom)
    db.commit()
    db.refresh(restroom)
    return restroom


def update_restroom(db: Session, restroom_id: int, payload: RestroomUpdate) -> Restroom:
    restroom = get_restroom(db, restroom_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(restroom, key, value.value if hasattr(value, "value") else value)
    db.commit()
    db.refresh(restroom)
    return restroom


def delete_restroom(db: Session, restroom_id: int, *, force: bool = False) -> None:
    restroom = get_restroom(db, restroom_id)
    inspection_count = db.scalar(
        select(func.count()).select_from(Inspection).where(Inspection.restroom_id == restroom_id)
    ) or 0
    issue_count = db.scalar(
        select(func.count()).select_from(Issue).where(Issue.restroom_id == restroom_id)
    ) or 0
    if (inspection_count or issue_count) and not force:
        raise ConflictError(
            f"该公厕已有 {inspection_count} 条巡查记录、{issue_count} 条问题记录，"
            "确需删除请使用 force=true"
        )
    db.delete(restroom)
    db.commit()


def get_restroom_detail(db: Session, restroom_id: int) -> RestroomDetail:
    restroom = get_restroom(db, restroom_id)
    inspection_count = db.scalar(
        select(func.count()).select_from(Inspection).where(Inspection.restroom_id == restroom_id)
    ) or 0
    avg_score = db.scalar(
        select(func.avg(Inspection.score)).where(Inspection.restroom_id == restroom_id)
    )
    latest = db.scalars(
        select(Inspection)
        .where(Inspection.restroom_id == restroom_id)
        .order_by(Inspection.inspect_time.desc(), Inspection.id.desc())
        .limit(1)
    ).first()
    open_issue_count = db.scalar(
        select(func.count())
        .select_from(Issue)
        .where(Issue.restroom_id == restroom_id, Issue.status.in_(OPEN_ISSUE_STATUSES))
    ) or 0
    total_issue_count = db.scalar(
        select(func.count()).select_from(Issue).where(Issue.restroom_id == restroom_id)
    ) or 0
    adjustment_count = db.scalar(
        select(func.count())
        .select_from(LocationAdjustment)
        .where(LocationAdjustment.restroom_id == restroom_id)
    ) or 0

    base = RestroomOut.model_validate(restroom).model_dump()
    return RestroomDetail(
        **base,
        inspection_count=inspection_count,
        latest_inspection_time=latest.inspect_time if latest else None,
        latest_inspection_score=latest.score if latest else None,
        avg_score=round(float(avg_score), 1) if avg_score is not None else None,
        open_issue_count=open_issue_count,
        total_issue_count=total_issue_count,
        location_adjustment_count=adjustment_count,
    )


def touch(db: Session, restroom_id: int) -> None:
    """巡查或问题变更后刷新台账更新时间。"""
    restroom = db.get(Restroom, restroom_id)
    if restroom is not None:
        restroom.updated_at = datetime.now()
        db.commit()
