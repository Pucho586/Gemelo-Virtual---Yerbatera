import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const http = axios.create({ baseURL: API, timeout: 30000 });

export const api = {
  getState: () => http.get('/state').then(r => r.data),
  getHistory: (n = 600) => http.get(`/history?n=${n}`).then(r => r.data),
  servicesStatus: () => http.get('/services/status').then(r => r.data),
  // Controls
  patchZapecado: (body) => http.post('/zapecado', body).then(r => r.data),
  patchSecado: (body) => http.post('/secado', body).then(r => r.data),
  patchCanchado: (body) => http.post('/canchado', body).then(r => r.data),
  patchCamara: (idx, body) => http.post(`/camaras/${idx}`, body).then(r => r.data),
  // Config
  getConfig: () => http.get('/config').then(r => r.data),
  patchConfig: (body) => http.post('/config', body).then(r => r.data),
  // Weather
  getWeather: () => http.get('/weather').then(r => r.data),
  setWeatherLocation: (body) => http.post('/weather/location', body).then(r => r.data),
  searchWeather: (q) => http.get(`/weather/search?q=${encodeURIComponent(q)}`).then(r => r.data),
  // AI
  aiChat: (body) => http.post('/ai/chat', body).then(r => r.data),
  aiHistory: (sid) => http.get(`/ai/history/${sid}`).then(r => r.data),
  aiReset: (sid) => http.post(`/ai/reset/${sid}`).then(r => r.data),
  aiAnomalies: (useAi = true) => http.get(`/ai/anomalies?use_ai=${useAi}`).then(r => r.data),
  aiForecast: (h = 30) => http.get(`/ai/forecast?horizon=${h}`).then(r => r.data),
  // Data
  listDataFiles: () => http.get('/data/files').then(r => r.data),
  downloadCsvUrl: (name) => `${API}/data/download/${encodeURIComponent(name)}`,
  excelUrl: (name) => `${API}/data/excel${name ? `?name=${encodeURIComponent(name)}` : ''}`,
};

// WebSocket URL builder
export const wsUrl = () => {
  const base = BACKEND_URL.replace(/^http/, 'ws');
  return `${base}/api/ws`;
};
