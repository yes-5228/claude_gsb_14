import { http } from './client.js';

const RESOURCE = '/restrooms';

export const restroomApi = {
  list: (params) => http.get(RESOURCE, params),
  detail: (id) => http.get(`${RESOURCE}/${id}`),
  create: (payload) => http.post(RESOURCE, payload),
  update: (id, payload) => http.patch(`${RESOURCE}/${id}`, payload),
  remove: (id, params) => http.delete(`${RESOURCE}/${id}`, params),
  districts: () => http.get(`${RESOURCE}/meta/districts`),
  // 点位调整：执行调整 / 单座调整历史 / 全局调整记录查询
  relocate: (id, payload) => http.post(`${RESOURCE}/${id}/location-adjustments`, payload),
  adjustments: (id, params) => http.get(`${RESOURCE}/${id}/location-adjustments`, params),
  allAdjustments: (params) => http.get(`${RESOURCE}/location-adjustments`, params),
};
