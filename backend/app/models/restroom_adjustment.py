"""公厕点位调整记录模型。"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RestroomAdjustment(Base):
    """一次公厕点位调整的留痕：记录区域/地址/经纬度的完整前后值。

    调整只更新公厕当前位置并写入本表，不回写历史巡查与问题，
    历史记录按各自发生时的位置快照归属，保证按位置统计口径前后连续。
    """

    __tablename__ = "restroom_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restroom_id: Mapped[int] = mapped_column(
        ForeignKey("restrooms.id", ondelete="CASCADE"), index=True, comment="所属公厕"
    )
    district_from: Mapped[str] = mapped_column(String(60), comment="调整前所属区域")
    district_to: Mapped[str] = mapped_column(String(60), index=True, comment="调整后所属区域")
    address_from: Mapped[str] = mapped_column(String(200), default="", comment="调整前详细地址")
    address_to: Mapped[str] = mapped_column(String(200), default="", comment="调整后详细地址")
    longitude_from: Mapped[float | None] = mapped_column(Float, nullable=True, comment="调整前经度")
    longitude_to: Mapped[float | None] = mapped_column(Float, nullable=True, comment="调整后经度")
    latitude_from: Mapped[float | None] = mapped_column(Float, nullable=True, comment="调整前纬度")
    latitude_to: Mapped[float | None] = mapped_column(Float, nullable=True, comment="调整后纬度")
    reason: Mapped[str] = mapped_column(String(200), comment="调整原因")
    operator: Mapped[str] = mapped_column(String(60), default="", index=True, comment="操作人")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="调整说明")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True, comment="生效时间"
    )

    restroom: Mapped["Restroom"] = relationship(back_populates="adjustments")  # noqa: F821
