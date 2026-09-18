import { useState } from 'react';

import { restroomApi } from '../../api/restrooms.js';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../components/Toast.jsx';

function formatCoord(value) {
  return value === null || value === undefined || value === '' ? '未标注' : Number(value).toFixed(6);
}

export default function LocationAdjustModal({ restroom, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState({
    to_district: restroom?.district ?? '',
    to_address: restroom?.address ?? '',
    to_longitude: restroom?.longitude ?? '',
    to_latitude: restroom?.latitude ?? '',
    reason: '',
    operator: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const setValue = (key) => (event) => {
    const { value } = event.target;
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.to_district.trim()) {
      setError('调整后的所属区域不能为空');
      return;
    }
    if (!form.reason.trim()) {
      setError('请填写调整原因');
      return;
    }
    setSaving(true);
    setError(null);
    const payload = {
      to_district: form.to_district.trim(),
      to_address: form.to_address.trim(),
      to_longitude: form.to_longitude === '' ? null : Number(form.to_longitude),
      to_latitude: form.to_latitude === '' ? null : Number(form.to_latitude),
      reason: form.reason.trim(),
      operator: form.operator.trim(),
    };
    if (
      (payload.to_longitude !== null && Number.isNaN(payload.to_longitude)) ||
      (payload.to_latitude !== null && Number.isNaN(payload.to_latitude))
    ) {
      setError('经纬度需为数字，或留空表示不标注');
      setSaving(false);
      return;
    }
    try {
      await restroomApi.adjustLocation(restroom.id, payload);
      toast.success('点位已调整，历史记录保留原位置');
      onSaved();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={`点位调整 - ${restroom.code}`}
      onClose={onClose}
      width={760}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="location-adjust-form" className="btn btn-primary" disabled={saving}>
            {saving ? '提交中…' : '确认调整'}
          </button>
        </>
      }
    >
      <div className="alert alert-info">
        调整即时生效；调整前的历史巡查与问题仍归属原点位，按区域统计在调整前后保持连续。
      </div>
      {error ? <div className="alert alert-error">{error}</div> : null}
      <form id="location-adjust-form" className="form-grid" onSubmit={submit}>
        <Field label="当前所属区域">
          <input value={restroom.district || ''} disabled readOnly />
        </Field>
        <Field label="当前详细地址">
          <input value={restroom.address || ''} disabled readOnly />
        </Field>
        <Field label="当前经纬度">
          <input
            value={`${formatCoord(restroom.longitude)} / ${formatCoord(restroom.latitude)}`}
            disabled
            readOnly
          />
        </Field>
        <Field label="调整后所属区域 *">
          <input value={form.to_district} onChange={setValue('to_district')} placeholder="如：城南区" />
        </Field>
        <Field label="调整后详细地址" full>
          <input value={form.to_address} onChange={setValue('to_address')} placeholder="路名 + 门牌或明显参照物" />
        </Field>
        <Field label="调整后经度" hint="留空表示不标注">
          <input
            type="number"
            step="0.000001"
            value={form.to_longitude}
            onChange={setValue('to_longitude')}
            placeholder="如 120.123456"
          />
        </Field>
        <Field label="调整后纬度" hint="留空表示不标注">
          <input
            type="number"
            step="0.000001"
            value={form.to_latitude}
            onChange={setValue('to_latitude')}
            placeholder="如 30.123456"
          />
        </Field>
        <Field label="调整原因 *" full>
          <textarea
            rows="2"
            value={form.reason}
            onChange={setValue('reason')}
            placeholder="如：行政区划调整 / 道路更名 / 坐标纠偏"
          />
        </Field>
        <Field label="操作人">
          <input value={form.operator} onChange={setValue('operator')} placeholder="执行人姓名" />
        </Field>
      </form>
    </Modal>
  );
}
