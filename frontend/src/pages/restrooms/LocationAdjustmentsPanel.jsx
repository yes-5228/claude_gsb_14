import { restroomApi } from '../../api/restrooms.js';
import { useAsync } from '../../hooks/useAsync.js';
import { formatDateTime } from '../../utils/format.js';

function formatCoord(value) {
  return value === null || value === undefined ? '未标注' : Number(value).toFixed(6);
}

function locationText(district, address) {
  return [district, address].filter(Boolean).join(' · ') || '未填写';
}

export default function LocationAdjustmentsPanel({ restroomId, reloadKey }) {
  const { data: records, loading, error } = useAsync(
    () => restroomApi.locationAdjustments(restroomId),
    [restroomId, reloadKey],
  );

  if (loading) return <div className="loading-block">加载中…</div>;
  if (error) return <div className="alert alert-error">{error.message}</div>;
  if (!records?.length) {
    return <div className="empty-block">该公厕暂无点位调整记录</div>;
  }

  return (
    <ol className="adjust-list">
      {records.map((record) => (
        <li key={record.id} className="adjust-item">
          <div className="adjust-flow">
            <div className="adjust-point">
              <span className="muted">调整前</span>
              <strong>{locationText(record.from_district, record.from_address)}</strong>
              <span className="muted">
                {formatCoord(record.from_longitude)} / {formatCoord(record.from_latitude)}
              </span>
            </div>
            <div className="adjust-arrow" aria-hidden="true">
              →
            </div>
            <div className="adjust-point">
              <span className="muted">调整后</span>
              <strong>{locationText(record.to_district, record.to_address)}</strong>
              <span className="muted">
                {formatCoord(record.to_longitude)} / {formatCoord(record.to_latitude)}
              </span>
            </div>
          </div>
          <div className="adjust-meta">
            <span className="tag tag-primary">{record.reason}</span>
            <span className="muted">操作人：{record.operator || '系统'}</span>
            <span className="muted">生效时间：{formatDateTime(record.effective_at)}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}
