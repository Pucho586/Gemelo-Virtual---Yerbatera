import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const http = axios.create({ baseURL: API, timeout: 30000, withCredentials: true });

// Bearer token de respaldo (cookies funcionan, pero esto es robusto)
let _token = null;
export const setAuthToken = (token) => {
  _token = token;
  if (token) {
    http.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    try { localStorage.setItem('yerba_token', token); } catch (e) { /* ignore */ }
  } else {
    delete http.defaults.headers.common['Authorization'];
    try { localStorage.removeItem('yerba_token'); } catch (e) { /* ignore */ }
  }
};
const stored = (() => { try { return localStorage.getItem('yerba_token'); } catch (e) { return null; } })();
if (stored) setAuthToken(stored);

export const api = {
  // Auth
  login: (body) => http.post('/auth/login', body).then(r => r.data),
  logout: () => http.post('/auth/logout').then(r => r.data),
  me: () => http.get('/auth/me').then(r => r.data),
  changePassword: (body) => http.post('/auth/change-password', body).then(r => r.data),
  recover: (body) => http.post('/auth/recover', body).then(r => r.data),
  listUsers: () => http.get('/auth/users').then(r => r.data),
  // Twin
  getState: () => http.get('/state').then(r => r.data),
  getHistory: (n = 600) => http.get(`/history?n=${n}`).then(r => r.data),
  servicesStatus: () => http.get('/services/status').then(r => r.data),
  // Mode + throughput
  getMode: () => http.get('/mode').then(r => r.data),
  setMode: (mode) => http.post('/mode', { mode }).then(r => r.data),
  setThroughput: (kgh) => http.post('/throughput', { kgh }).then(r => r.data),
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
  // Recipes
  listRecipes: () => http.get('/recipes').then(r => r.data),
  applyRecipe: (id) => http.post(`/recipes/${id}/apply`).then(r => r.data),
  createRecipe: (body) => http.post('/recipes', body).then(r => r.data),
  deleteRecipe: (id) => http.delete(`/recipes/${id}`).then(r => r.data),
  // Batches
  listBatches: () => http.get('/batches').then(r => r.data),
  activeBatch: () => http.get('/batches/active').then(r => r.data),
  createBatch: (body) => http.post('/batches', body).then(r => r.data),
  closeBatch: (id, body) => http.post(`/batches/${id}/close`, body).then(r => r.data),
  cancelBatch: (id) => http.post(`/batches/${id}/cancel`).then(r => r.data),
  // FASE 2: External sources, drift, calibration, audit
  externalStatus: () => http.get('/external/status').then(r => r.data),
  configureExternal: (section, body) => http.post(`/external/${section}`, body).then(r => r.data),
  getDrift: () => http.get('/drift').then(r => r.data),
  calibrationAnalyze: (csv) => http.post('/calibration/analyze', { csv }).then(r => r.data),
  calibrationApply: (calibration) => http.post('/calibration/apply', { calibration }).then(r => r.data),
  auditLog: (limit = 200, username = null) => http.get(`/audit?limit=${limit}${username ? `&username=${username}` : ''}`).then(r => r.data),
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
