"""公厕点位调整记录与轻量迁移登记。"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LocationAdjustment(Base):
    """一次公厕点位调整的流水，记录调整前后的区域/地址/坐标。

    历史巡查与问题通过各自的位置快照归属到发生时的点位；
    本表只追加、不修改、不删除，供查询调整轨迹。
    """

    __tablename__ = "location_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restroom_id: Mapped[int] = mapped_column(
        ForeignKey("restrooms.id", ondelete="CASCADE"), index=True, comment="所属公厕"
    )
    reason: Mapped[str] = mapped_column(Text, comment="调整原因")
    operator: Mapped[str] = mapped_column(String(60), default="", comment="操作人")
    from_district: Mapped[str] = mapped_column(String(60), default="", comment="调整前所属区域")
    to_district: Mapped[str] = mapped_column(String(60), default="", comment="调整后所属区域")
    from_address: Mapped[str] = mapped_column(String(200), default="", comment="调整前详细地址")
    to_address: Mapped[str] = mapped_column(String(200), default="", comment="调整后详细地址")
    from_longitude: Mapped[float | None] = mapped_column(Float, nullable=True, comment="调整前经度")
    to_longitude: Mapped[float | None] = mapped_column(Float, nullable=True, comment="调整后经度")
    from_latitude: Mapped[float | None] = mapped_column(Float, nullable=True, comment="调整前纬度")
    to_latitude: Mapped[float | None] = mapped_column(Float, nullable=True, comment="调整后纬度")
    effective_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True, comment="生效时间（服务端即时生效）"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="记录时间")

    restroom: Mapped["Restroom"] = relationship(back_populates="adjustments")  # noqa: F821


class SchemaMigration(Base):
    """启动期轻量迁移的版本登记，保证每段迁移只执行一次。"""

    __tablename__ = "schema_migrations"

    version: Mapped[str] = mapped_column(String(64), primary_key=True, comment="迁移版本号")
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="执行时间")
