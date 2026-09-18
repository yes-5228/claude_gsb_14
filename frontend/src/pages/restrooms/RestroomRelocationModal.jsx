import { useState } from 'react';

import { restroomApi } from '../../api/restrooms.js';
import Field from '../../components/Field.jsx';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../components/Toast.jsx';

const EMPTY = {
  district: '',
  address: '',
  longitude: '',
  latitude: '',
  reason: '',
  operator: '',
  remark: '',
};

function formatCoord(value) {
  return value === null || value === undefined || value === '' ? '未记录' : Number(value).toFixed(6);
}

export default function RestroomRelocationModal({ restroom, onClose, onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState(() => ({
    ...EMPTY,
    district: restroom?.district ?? '',
    address: restroom?.address ?? '',
    longitude: restroom?.longitude ?? '',
    latitude: restroom?.latitude ?? '',
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const setValue = (key) => (event) => {
    const target = event.target;
    const value = target.type === 'number' ? target.value : target.value;
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.district.trim()) {
      setError('调整后的所属区域必填');
      return;
    }
    if (!form.reason.trim()) {
      setError('请填写调整原因');
      return;
    }
    if (!form.operator.trim()) {
      setError('请填写操作人');
      return;
    }
    const longitude = form.longitude === '' ? null : Number(form.longitude);
    const latitude = form.latitude === '' ? null : Number(form.latitude);
    if ((form.longitude !== '' && Number.isNaN(longitude)) || (form.latitude !== '' && Number.isNaN(latitude))) {
      setError('经纬度需为数字，或留空不记录');
      return;
    }
    if (
      !window.confirm('确认调整该公厕点位？\n\n历史巡查与问题将保留原位置归属、不会迁移，调整会留痕可查。')
    ) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await restroomApi.relocate(restroom.id, {
        district: form.district.trim(),
        address: form.address.trim(),
        longitude,
        latitude,
        reason: form.reason.trim(),
        operator: form.operator.trim(),
        remark: form.remark.trim() || null,
      });
      toast.success('点位已调整，历史记录保留原位置归属');
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
      title={`点位调整 - ${restroom?.code ?? ''}`}
      onClose={onClose}
      width={820}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            取消
          </button>
          <button type="submit" form="relocation-form" className="btn btn-warning" disabled={saving}>
            {saving ? '调整中…' : '确认调整点位'}
          </button>
        </>
      }
    >
      <div className="alert alert-info">
        调整只改变公厕当前位置；历史巡查与问题按各自发生时的位置保留，按区域统计前后连续。
      </div>
      {error ? <div className="alert alert-error">{error}</div> : null}

      <div className="detail-list" style={{ marginBottom: 14 }}>
        <div className="detail-item">
          <div className="label">当前区域</div>
          <div className="value">{restroom?.district ?? '-'}</div>
        </div>
        <div className="detail-item">
          <div className="label">当前地址</div>
          <div className="value">{restroom?.address || '-'}</div>
        </div>
        <div className="detail-item">
          <div className="label">当前经纬度</div>
          <div className="value">
            {formatCoord(restroom?.longitude)} , {formatCoord(restroom?.latitude)}
          </div>
        </div>
      </div>

      <form id="relocation-form" className="form-grid" onSubmit={submit}>
        <Field label="调整后所属区域 *">
          <input value={form.district} onChange={setValue('district')} placeholder="如：城南区" />
        </Field>
        <Field label="操作人 *">
          <input value={form.operator} onChange={setValue('operator')} placeholder="执行调整的人员" />
        </Field>
        <Field label="调整后经度" hint="可选，留空表示不记录">
          <input
            type="number"
            step="0.000001"
            value={form.longitude}
            onChange={setValue('longitude')}
          />
        </Field>
        <Field label="调整后纬度" hint="可选，留空表示不记录">
          <input
            type="number"
            step="0.000001"
            value={form.latitude}
            onChange={setValue('latitude')}
          />
        </Field>
        <Field label="调整后详细地址" full>
          <input value={form.address} onChange={setValue('address')} placeholder="路名 + 门牌或明显参照物" />
        </Field>
        <Field label="调整原因 *" full>
          <input value={form.reason} onChange={setValue('reason')} placeholder="如：行政区划调整 / 道路改造 / 公厕迁建" />
        </Field>
        <Field label="调整说明" full>
          <textarea rows="2" value={form.remark} onChange={setValue('remark')} />
        </Field>
      </form>
    </Modal>
  );
}
