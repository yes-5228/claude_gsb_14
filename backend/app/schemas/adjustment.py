"""公厕点位调整相关数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.restroom import RestroomBrief


class RestroomRelocationPayload(BaseModel):
    """一次点位调整操作；位置变更的唯一入口，需填写原因与操作人。"""

    district: str = Field(min_length=1, max_length=60, description="调整后所属区域")
    address: str = Field(default="", max_length=200, description="调整后详细地址")
    longitude: float | None = Field(default=None, description="调整后经度")
    latitude: float | None = Field(default=None, description="调整后纬度")
    reason: str = Field(min_length=1, max_length=200, description="调整原因")
    operator: str = Field(min_length=1, max_length=60, description="操作人")
    remark: str | None = Field(default=None, max_length=500, description="调整说明")


class RestroomAdjustmentOut(BaseModel):
    """点位调整记录：完整的前后值。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    restroom_id: int
    district_from: str
    district_to: str
    address_from: str = ""
    address_to: str = ""
    longitude_from: float | None = None
    longitude_to: float | None = None
    latitude_from: float | None = None
    latitude_to: float | None = None
    reason: str
    operator: str = ""
    remark: str | None = None
    created_at: datetime


class RestroomAdjustmentListItem(RestroomAdjustmentOut):
    """全局调整列表项，附带公厕简要信息。"""

    restroom: RestroomBrief | None = None
