import React, { useEffect, useRef, useState } from 'react';
import { Card, CardHeader, Btn } from './UI';
import { api } from '../lib/api';
import { Sparkle, ArrowClockwise, Warning, ChartLineUp, PaperPlaneTilt } from '@phosphor-icons/react';

const SESSION_KEY = 'yerba_ai_session_id';

function getSessionId() {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = `web-${Math.random().toString(36).slice(2, 12)}`;
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export default function AIPanel() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [sessionId] = useState(getSessionId());
  const [anomalies, setAnomalies] = useState([]);
  const [diagnosis, setDiagnosis] = useState(null);
  const [loadingAnom, setLoadingAnom] = useState(false);
  const [forecast, setForecast] = useState(null);
  const [loadingFc, setLoadingFc] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    api.aiHistory(sessionId).then(setMessages).catch(() => {});
    refreshAnomalies(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    const optimistic = [...messages, { role: 'user', content: text }];
    setMessages(optimistic);
    setSending(true);
    try {
      const res = await api.aiChat({ message: text, session_id: sessionId, include_state: true });
      setMessages(res.history);
    } catch (e) {
      setMessages([...optimistic, { role: 'assistant', content: `Error: ${e?.response?.data?.detail || e.message}` }]);
    } finally {
      setSending(false);
    }
  };

  const resetChat = async () => {
    await api.aiReset(sessionId);
    setMessages([]);
  };

  const refreshAnomalies = async (useAi = true) => {
    setLoadingAnom(true);
    try {
      const r = await api.aiAnomalies(useAi);
      setAnomalies(r.anomalies || []);
      setDiagnosis(r.diagnosis);
    } catch (e) {
      setDiagnosis(`Error: ${e?.message}`);
    } finally {
      setLoadingAnom(false);
    }
  };

  const refreshForecast = async () => {
    setLoadingFc(true);
    try {
      const r = await api.aiForecast(20);
      setForecast(r);
    } catch (e) { console.warn(e); }
    setLoadingFc(false);
  };

  const sevColor = (sev) => sev === 'high' ? 'text-red-400 border-red-500/30' : sev === 'medium' ? 'text-amber-400 border-amber-500/30' : 'text-slate-300 border-slate-600/40';

  return (
    <div className="space-y-px">
      <Card className="p-0" testid="ai-anomalies-card">
        <CardHeader
          title="Anomalías detectadas"
          subtitle="Reglas determinísticas + diagnóstico con Gemini 3 Flash"
          action={
            <div className="flex items-center gap-2">
              <Btn testid="ai-refresh-anomalies" variant="secondary" onClick={() => refreshAnomalies(true)} disabled={loadingAnom}>
                <span className="inline-flex items-center gap-1"><ArrowClockwise size={12}/> {loadingAnom ? 'Analizando...' : 'Re-analizar'}</span>
              </Btn>
            </div>
          }
        />
        <div className="p-4 sm:p-5 space-y-3">
          {anomalies.length === 0 && (
            <p className="font-mono text-xs text-slate-500">Sin anomalías. El gemelo está dentro de rangos.</p>
          )}
          {anomalies.map((a, i) => (
            <div key={i} className={`border-l-2 pl-3 py-1 ${sevColor(a.severity)}`} data-testid={`ai-anom-${i}`}>
              <div className="font-mono text-[10px] uppercase tracking-wider opacity-80">{a.severity} · {a.stage}</div>
              <div className="text-sm text-slate-200">{a.message}</div>
            </div>
          ))}
          {diagnosis && (
            <div className="mt-4 border border-amber-300/30 bg-amber-300/5 p-4" data-testid="ai-diagnosis">
              <div className="flex items-center gap-1.5 mb-1.5"><Sparkle size={14} className="text-amber-300"/><span className="font-mono text-[10px] uppercase tracking-wider text-amber-300">Diagnóstico IA</span></div>
              <p className="text-sm text-slate-200 whitespace-pre-wrap">{diagnosis}</p>
            </div>
          )}
        </div>
      </Card>

      <Card className="p-0" testid="ai-chat-card">
        <CardHeader
          title="Chat con el gemelo"
          subtitle="Preguntá sobre el estado, causas o sugerencias operativas"
          action={
            <Btn testid="ai-reset-chat" variant="secondary" onClick={resetChat}>Limpiar</Btn>
          }
        />
        <div ref={scrollRef} className="p-4 sm:p-5 max-h-[420px] min-h-[260px] overflow-y-auto space-y-3" data-testid="ai-messages">
          {messages.length === 0 && (
            <div className="space-y-2">
              <p className="text-xs text-slate-500 font-mono">Probá:</p>
              {[
                '¿Por qué el zapecado está subiendo?',
                '¿La humedad del secado es razonable para hoy?',
                '¿En qué cámara debería encender el ventilador?',
                'Sugerí una receta de yerba más suave',
              ].map((q, i) => (
                <button key={i} onClick={() => setInput(q)} className="block text-xs text-slate-300 hover:text-amber-300 transition-colors font-mono" data-testid={`ai-suggestion-${i}`}>
                  → {q}
                </button>
              ))}
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`} data-testid={`ai-msg-${i}`}>
              <div className={`max-w-[88%] px-3 py-2 text-sm whitespace-pre-wrap ${m.role === 'user' ? 'bg-slate-50 text-slate-900' : 'bg-[#1A1E1C] text-slate-200 border-l-2 border-amber-300/60'}`}>
                {m.content}
              </div>
            </div>
          ))}
          {sending && <div className="text-xs font-mono text-amber-300/70" data-testid="ai-thinking">Gemini está pensando...</div>}
        </div>
        <div className="border-t p-3 flex items-center gap-2" style={{ borderColor: 'var(--border)' }}>
          <input
            data-testid="ai-input"
            className="flex-1 field"
            placeholder="Preguntá al gemelo..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            disabled={sending}
          />
          <Btn testid="ai-send" variant="ai" onClick={send} disabled={sending || !input.trim()}>
            <span className="inline-flex items-center gap-1"><PaperPlaneTilt size={13}/> Enviar</span>
          </Btn>
        </div>
      </Card>

      <Card className="p-0" testid="ai-forecast-card">
        <CardHeader
          title="Predicción (forecast lineal)"
          subtitle="Tendencia de las próximas N muestras a partir del histórico"
          action={<Btn testid="ai-refresh-forecast" variant="secondary" onClick={refreshForecast} disabled={loadingFc}><span className="inline-flex items-center gap-1"><ChartLineUp size={13}/> Calcular</span></Btn>}
        />
        <div className="p-4 sm:p-5 space-y-3 font-mono text-xs">
          {!forecast && <p className="text-slate-500">Tocá "Calcular" para generar la predicción.</p>}
          {forecast && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div><div className="text-slate-500 uppercase text-[10px]">Zap T media</div><div className="text-slate-200">{forecast.trend_summary?.zapecado_mean ?? '–'} °C</div></div>
                <div><div className="text-slate-500 uppercase text-[10px]">Zap σ</div><div className="text-slate-200">{forecast.trend_summary?.zapecado_stdev ?? '–'}</div></div>
                <div><div className="text-slate-500 uppercase text-[10px]">Sec HR media</div><div className="text-slate-200">{forecast.trend_summary?.secado_humedad_mean ?? '–'} %</div></div>
                <div><div className="text-slate-500 uppercase text-[10px]">Horizonte</div><div className="text-slate-200">{forecast.horizon_steps} pasos</div></div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[11px]">
                <ForecastList title="Zapecado T" rows={forecast.zapecado_temp} unit="°C" />
                <ForecastList title="Secado HR" rows={forecast.secado_hum} unit="%" />
              </div>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}

function ForecastList({ title, rows, unit }) {
  if (!rows || !rows.length) return null;
  const first = rows[0]?.value;
  const last = rows[rows.length - 1]?.value;
  const trend = last - first;
  const trendColor = Math.abs(trend) < 0.1 ? 'text-slate-400' : trend > 0 ? 'text-red-400' : 'text-green-400';
  return (
    <div className="border" style={{ borderColor: 'var(--border)' }}>
      <div className="px-3 py-1.5 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
        <span className="uppercase tracking-wider text-slate-400">{title}</span>
        <span className={trendColor}>Δ {trend > 0 ? '+' : ''}{trend.toFixed(2)} {unit}</span>
      </div>
      <div className="p-2 grid grid-cols-5 gap-1 text-center">
        {rows.slice(0, 10).map((r, i) => (
          <div key={i}><span className="text-slate-500">+{r.step}</span> <span className="text-slate-200">{r.value.toFixed(1)}</span></div>
        ))}
      </div>
    </div>
  );
}
