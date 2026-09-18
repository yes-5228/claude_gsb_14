"""公厕台账相关数据结构。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import RestroomGrade, RestroomStatus


class RestroomBrief(BaseModel):
    """其他模块引用公厕时的精简信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    district: str
    address: str = ""


class RestroomBase(BaseModel):
    name: str = Field(min_length=1, max_length=120, description="公厕名称")
    district: str = Field(min_length=1, max_length=60, description="所属区域")
    address: str = Field(default="", max_length=200, description="详细地址")
    grade: RestroomGrade = Field(default=RestroomGrade.SECOND, description="公厕等级")
    status: RestroomStatus = Field(default=RestroomStatus.NORMAL, description="开放状态")
    manager: str = Field(default="", max_length=60, description="保洁责任人")
    manager_phone: str = Field(default="", max_length=30, description="联系电话")
    open_hours: str = Field(default="06:00-22:00", max_length=60, description="开放时间")
    stall_count: int = Field(default=0, ge=0, description="蹲位数量")
    basin_count: int = Field(default=0, ge=0, description="洗手盆数量")
    has_accessible: bool = Field(default=True, description="是否有无障碍设施")
    longitude: float | None = Field(default=None, description="经度")
    latitude: float | None = Field(default=None, description="纬度")
    remark: str | None = Field(default=None, max_length=500, description="备注")


class RestroomCreate(RestroomBase):
    code: str | None = Field(default=None, max_length=32, description="公厕编号，留空自动生成")


class RestroomUpdate(BaseModel):
    """局部更新，仅提交需要变更的字段。

    点位信息（所属区域/地址/经纬度）不在此处修改，需走点位调整流程，
    以便保留原值并记录调整流水；提交这些字段会被拒绝。
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    grade: RestroomGrade | None = None
    status: RestroomStatus | None = None
    manager: str | None = Field(default=None, max_length=60)
    manager_phone: str | None = Field(default=None, max_length=30)
    open_hours: str | None = Field(default=None, max_length=60)
    stall_count: int | None = Field(default=None, ge=0)
    basin_count: int | None = Field(default=None, ge=0)
    has_accessible: bool | None = None
    remark: str | None = Field(default=None, max_length=500)


class RestroomOut(RestroomBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    created_at: datetime
    updated_at: datetime


class RestroomDetail(RestroomOut):
    """台账详情，附带巡查与问题的汇总信息。"""

    inspection_count: int = 0
    latest_inspection_time: datetime | None = None
    latest_inspection_score: float | None = None
    avg_score: float | None = None
    open_issue_count: int = 0
    total_issue_count: int = 0
    location_adjustment_count: int = 0


class LocationAdjustmentCreate(BaseModel):
    """点位调整入参；调整即时生效，生效时间由服务端记录。"""

    to_district: str = Field(min_length=1, max_length=60, description="调整后所属区域")
    to_address: str = Field(default="", max_length=200, description="调整后详细地址")
    to_longitude: float | None = Field(default=None, ge=-180, le=180, description="调整后经度")
    to_latitude: float | None = Field(default=None, ge=-90, le=90, description="调整后纬度")
    reason: str = Field(min_length=1, max_length=500, description="调整原因")
    operator: str = Field(default="", max_length=60, description="操作人")


class LocationAdjustmentOut(BaseModel):
    """点位调整流水。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    restroom_id: int
    reason: str
    operator: str
    from_district: str
    to_district: str
    from_address: str
    to_address: str
    from_longitude: float | None = None
    to_longitude: float | None = None
    from_latitude: float | None = None
    to_latitude: float | None = None
    effective_at: datetime
    created_at: datetime
