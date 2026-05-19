import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Btn, NumberInput, TextInput, SectionTitle } from './UI';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { Package, Play, Stop, X, Clock } from '@phosphor-icons/react';

export default function LotesView() {
  const { user } = useAuth();
  const [batches, setBatches] = useState([]);
  const [active, setActive] = useState(null);
  const [recipes, setRecipes] = useState([]);
  const [showNew, setShowNew] = useState(false);
  const [draft, setDraft] = useState({ kg_entrada: 1000, receta_id: '', observaciones: '' });
  const [closing, setClosing] = useState(false);
  const [closeData, setCloseData] = useState({ kg_salida: 0, observaciones: '' });

  const load = async () => {
    const [bs, ac, rs] = await Promise.all([api.listBatches(), api.activeBatch(), api.listRecipes()]);
    setBatches(bs);
    setActive(ac);
    setRecipes(rs);
  };
  useEffect(() => { load(); const id = setInterval(load, 10000); return () => clearInterval(id); }, []);

  const startBatch = async () => {
    try {
      const recipe = recipes.find(r => r.id === draft.receta_id);
      const body = {
        ...draft,
        receta_nombre: recipe?.nombre,
        operario: user?.username,
      };
      await api.createBatch(body);
      if (recipe) await api.applyRecipe(recipe.id);
      setShowNew(false);
      await load();
    } catch (e) {
      alert(e?.response?.data?.detail || 'Error');
    }
  };

  const closeBatch = async () => {
    try {
      await api.closeBatch(active.id, closeData);
      setClosing(false);
      await load();
    } catch (e) {
      alert(e?.response?.data?.detail || 'Error');
    }
  };

  const cancelBatch = async () => {
    if (!window.confirm('¿Cancelar lote activo?')) return;
    await api.cancelBatch(active.id);
    await load();
  };

  return (
    <div className="space-y-px">
      <Card className="p-5" testid="batch-active-card">
        <SectionTitle kicker="01">Lote activo</SectionTitle>
        {!active && !showNew && (
          <div className="mt-3 flex items-center justify-between">
            <p className="text-sm text-slate-400">No hay lote en curso.</p>
            <Btn testid="batch-new-btn" onClick={() => setShowNew(true)}><span className="inline-flex items-center gap-1"><Play size={13}/> Iniciar lote</span></Btn>
          </div>
        )}
        {showNew && (
          <div className="mt-3 space-y-3" data-testid="batch-new-form">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <NumberInput testid="b-kg" label="Kg entrada" value={draft.kg_entrada} onChange={(v) => setDraft({ ...draft, kg_entrada: v })} min={1} />
              <label className="flex flex-col gap-1">
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Receta</span>
                <select data-testid="b-receta" className="field" value={draft.receta_id} onChange={(e) => setDraft({ ...draft, receta_id: e.target.value })}>
                  <option value="">(sin receta — ajustes manuales)</option>
                  {recipes.map(r => <option key={r.id} value={r.id}>{r.nombre}</option>)}
                </select>
              </label>
              <TextInput testid="b-obs" label="Observaciones" value={draft.observaciones} onChange={(v) => setDraft({ ...draft, observaciones: v })} />
            </div>
            <div className="flex gap-2">
              <Btn testid="b-start" onClick={startBatch}><span className="inline-flex items-center gap-1"><Play size={13}/> Iniciar</span></Btn>
              <Btn testid="b-cancel-new" variant="secondary" onClick={() => setShowNew(false)}>Cancelar</Btn>
            </div>
          </div>
        )}
        {active && (
          <div className="mt-3 space-y-3" data-testid="batch-active">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 font-mono text-xs">
              <Info label="ID" value={active.id} />
              <Info label="Receta" value={active.receta_nombre || '—'} />
              <Info label="Kg entrada" value={`${active.kg_entrada} kg`} />
              <Info label="Operario" value={active.operario} />
              <Info label="Inicio" value={new Date(active.started_at).toLocaleString()} />
            </div>
            {!closing && (
              <div className="flex gap-2">
                <Btn testid="b-close-btn" variant="ai" onClick={() => { setClosing(true); setCloseData({ kg_salida: active.kg_entrada * 0.96, observaciones: active.observaciones }); }}>
                  <span className="inline-flex items-center gap-1"><Stop size={13}/> Cerrar lote</span>
                </Btn>
                <Btn testid="b-cancel-active" variant="danger" onClick={cancelBatch}><X size={13}/></Btn>
              </div>
            )}
            {closing && (
              <div className="space-y-3 border-t pt-3" style={{ borderColor: 'var(--border)' }} data-testid="batch-close-form">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <NumberInput testid="b-close-kg" label="Kg salida" value={closeData.kg_salida} onChange={(v) => setCloseData({ ...closeData, kg_salida: v })} step={0.5} />
                  <TextInput testid="b-close-obs" label="Observaciones finales" value={closeData.observaciones} onChange={(v) => setCloseData({ ...closeData, observaciones: v })} />
                </div>
                <p className="font-mono text-xs text-slate-400">Merma: {active.kg_entrada > 0 ? (((active.kg_entrada - closeData.kg_salida) / active.kg_entrada) * 100).toFixed(2) : '–'}%</p>
                <div className="flex gap-2">
                  <Btn testid="b-close-confirm" onClick={closeBatch}>Cerrar y guardar</Btn>
                  <Btn testid="b-close-cancel" variant="secondary" onClick={() => setClosing(false)}>Volver</Btn>
                </div>
              </div>
            )}
          </div>
        )}
      </Card>

      <Card className="p-5" testid="batch-history">
        <SectionTitle kicker="02">Histórico de lotes</SectionTitle>
        {batches.length === 0 ? (
          <p className="font-mono text-xs text-slate-500 mt-3">Sin lotes registrados todavía.</p>
        ) : (
          <div className="mt-3 border" style={{ borderColor: 'var(--border)' }}>
            <div className="grid grid-cols-7 gap-2 px-3 py-2 border-b font-mono text-[10px] uppercase tracking-wider text-slate-500" style={{ borderColor: 'var(--border)' }}>
              <span>ID</span><span>Estado</span><span>Receta</span><span>Kg in</span><span>Kg out</span><span>Merma</span><span>Operario</span>
            </div>
            {batches.map((b, i) => (
              <div key={b.id} className="grid grid-cols-7 gap-2 px-3 py-2 border-b last:border-b-0 font-mono text-xs" style={{ borderColor: 'var(--border)' }} data-testid={`batch-row-${i}`}>
                <span className="text-slate-200 truncate">{b.id}</span>
                <span className={b.status === 'running' ? 'text-amber-300' : b.status === 'finished' ? 'text-green-400' : 'text-red-400'}>{b.status}</span>
                <span className="text-slate-300 truncate">{b.receta_nombre || '—'}</span>
                <span className="text-slate-300">{b.kg_entrada}</span>
                <span className="text-slate-300">{b.kg_salida ?? '—'}</span>
                <span className="text-amber-300">{b.merma_pct != null ? `${b.merma_pct}%` : '—'}</span>
                <span className="text-slate-400 truncate">{b.operario}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div className="border p-2.5" style={{ borderColor: 'var(--border)' }}>
      <div className="text-slate-500 uppercase text-[10px]">{label}</div>
      <div className="text-slate-200 truncate">{value}</div>
    </div>
  );
}
