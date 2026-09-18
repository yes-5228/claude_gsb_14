import { Link } from 'react-router-dom';

import { restroomApi } from '../../api/restrooms.js';
import DataTable from '../../components/DataTable.jsx';
import Field from '../../components/Field.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Pagination from '../../components/Pagination.jsx';
import { useAsync } from '../../hooks/useAsync.js';
import { useListQuery } from '../../hooks/useListQuery.js';
import { formatDateTime } from '../../utils/format.js';

const DEFAULT_FILTERS = { keyword: '', district: '', date_from: '', date_to: '' };

function ChangeText({ from, to }) {
  const changed = (from || '') !== (to || '');
  return (
    <span className="location-change">
      <span className="muted">{from || '-'}</span>
      <span className="arrow">→</span>
      <span className={changed ? 'to' : 'muted'}>{to || '-'}</span>
    </span>
  );
}

export default function AdjustmentListPage() {
  const list = useListQuery((params) => restroomApi.allAdjustments(params), DEFAULT_FILTERS, 10);
  const { data: districts } = useAsync(() => restroomApi.districts(), []);

  return (
    <>
      <PageHeader
        title="点位调整记录"
        description="公厕点位（区域 / 地址 / 经纬度）调整的全局留痕；历史巡查与问题按发生时位置保留"
        actions={
          <Link className="btn" to="/restrooms">
            返回公厕台账
          </Link>
        }
      />
      <div className="content">
        <section className="card">
          <div className="filter-bar">
            <Field label="关键字" full>
              <input
                value={list.filters.keyword}
                placeholder="调整原因 / 说明 / 操作人"
                onChange={(event) => list.updateFilter('keyword', event.target.value)}
              />
            </Field>
            <Field label="所属区域" hint="命中迁出或迁入区域">
              <select
                value={list.filters.district}
                onChange={(event) => list.updateFilter('district', event.target.value)}
              >
                <option value="">全部</option>
                {(districts || []).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </Field>
            <Field label="开始日期">
              <input
                type="date"
                value={list.filters.date_from}
                onChange={(event) => list.updateFilter('date_from', event.target.value)}
              />
            </Field>
            <Field label="结束日期">
              <input
                type="date"
                value={list.filters.date_to}
                onChange={(event) => list.updateFilter('date_to', event.target.value)}
              />
            </Field>
            <button type="button" className="btn" onClick={list.resetFilters}>
              重置
            </button>
          </div>
        </section>

        <section className="card">
          <DataTable
            loading={list.loading}
            error={list.error}
            rows={list.items}
            emptyText="暂无点位调整记录"
            columns={[
              {
                key: 'created_at',
                title: '生效时间',
                render: (row) => formatDateTime(row.created_at),
              },
              {
                key: 'restroom',
                title: '公厕',
                wrap: true,
                render: (row) =>
                  row.restroom ? (
                    <Link to={`/restrooms/${row.restroom.id}`}>
                      {row.restroom.name}（{row.restroom.code}）
                    </Link>
                  ) : (
                    '-'
                  ),
              },
              {
                key: 'district',
                title: '区域变化',
                render: (row) => <ChangeText from={row.district_from} to={row.district_to} />,
              },
              {
                key: 'address',
                title: '地址变化',
                wrap: true,
                render: (row) => <ChangeText from={row.address_from} to={row.address_to} />,
              },
              { key: 'reason', title: '调整原因', wrap: true },
              { key: 'operator', title: '操作人' },
            ]}
          />
          <Pagination meta={list.meta} onPageChange={list.setPage} />
        </section>
      </div>
    </>
  );
}
