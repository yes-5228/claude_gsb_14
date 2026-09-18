"""公厕点位调整业务逻辑。

点位调整是位置变更的唯一通道：更新公厕当前位置并写入一条调整留痕，
但不回写任何历史巡查与问题——历史记录按发生时的位置快照归属。
"""

from datetime import date, datetime, time

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.models import RestroomAdjustment
from app.schemas.adjustment import RestroomRelocationPayload
from app.services import restroom_service


def relocate(
    db: Session, restroom_id: int, payload: RestroomRelocationPayload
) -> RestroomAdjustment:
    restroom = restroom_service.get_restroom(db, restroom_id)

    new_district = payload.district.strip()
    new_address = (payload.address or "").strip()
    if not new_district:
        raise DomainError("调整后所属区域不能为空")

    old = (restroom.district, restroom.address, restroom.longitude, restroom.latitude)
    new = (new_district, new_address, payload.longitude, payload.latitude)
    if old == new:
        raise DomainError("点位信息未发生变化，无需调整")

    adjustment = RestroomAdjustment(
        restroom_id=restroom_id,
        district_from=restroom.district,
        district_to=new_district,
        address_from=restroom.address or "",
        address_to=new_address,
        longitude_from=restroom.longitude,
        longitude_to=payload.longitude,
        latitude_from=restroom.latitude,
        latitude_to=payload.latitude,
        reason=payload.reason.strip(),
        operator=payload.operator.strip(),
        remark=payload.remark,
    )
    restroom.district = new_district
    restroom.address = new_address
    restroom.longitude = payload.longitude
    restroom.latitude = payload.latitude
    restroom.updated_at = datetime.now()

    db.add(adjustment)
    db.commit()
    db.refresh(adjustment)
    return adjustment


def list_for_restroom(
    db: Session, restroom_id: int, *, page: int = 1, page_size: int = 10
) -> tuple[list[RestroomAdjustment], int]:
    restroom_service.get_restroom(db, restroom_id)
    base = select(RestroomAdjustment).where(RestroomAdjustment.restroom_id == restroom_id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base.order_by(
                RestroomAdjustment.created_at.desc(), RestroomAdjustment.id.desc()
            ).offset((page - 1) * page_size).limit(page_size)
        )
    )
    return rows, total


def list_adjustments(
    db: Session,
    *,
    restroom_id: int | None = None,
    district: str | None = None,
    operator: str | None = None,
    keyword: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 10,
    order: str = "desc",
) -> tuple[list[RestroomAdjustment], int]:
    stmt = select(RestroomAdjustment)
    if restroom_id:
        stmt = stmt.where(RestroomAdjustment.restroom_id == restroom_id)
    if district:
        # 跨区调整在迁出、迁入两侧都能查到
        stmt = stmt.where(
            or_(
                RestroomAdjustment.district_from == district,
                RestroomAdjustment.district_to == district,
            )
        )
    if operator:
        stmt = stmt.where(RestroomAdjustment.operator.like(f"%{operator.strip()}%"))
    if date_from:
        stmt = stmt.where(RestroomAdjustment.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        stmt = stmt.where(RestroomAdjustment.created_at <= datetime.combine(date_to, time.max))
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                RestroomAdjustment.reason.like(like),
                RestroomAdjustment.remark.like(like),
                RestroomAdjustment.operator.like(like),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column = RestroomAdjustment.created_at
    stmt = stmt.order_by(column.desc() if order == "desc" else column.asc(), RestroomAdjustment.id.desc())
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return rows, total
