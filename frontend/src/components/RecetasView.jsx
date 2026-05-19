import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Btn, NumberInput, TextInput, SectionTitle } from './UI';
import { api } from '../lib/api';
import { useAuth, isAdmin } from '../lib/auth';
import { ForkKnife, Check, Trash, Plus } from '@phosphor-icons/react';

export default function RecetasView() {
  const { user } = useAuth();
  const [recipes, setRecipes] = useState([]);
  const [applied, setApplied] = useState(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState(null);

  const load = () => api.listRecipes().then(setRecipes);
  useEffect(() => { load(); }, []);

  const onApply = async (id) => {
    try {
      await api.applyRecipe(id);
      setApplied(id);
      setTimeout(() => setApplied(null), 3500);
    } catch (e) { console.warn(e); }
  };

  const onDelete = async (id) => {
    if (!window.confirm('¿Eliminar receta personalizada?')) return;
    await api.deleteRecipe(id);
    load();
  };

  const blank = () => ({
    id: '',
    nombre: '',
    descripcion: '',
    color: '#FCD34D',
    zapecado: { target_temp: 480, velocidad_tambor: 18, velocidad_chip: 40 },
    secado: { target_temp: 95, target_humedad: 8.0, velocidad_aire: 3.0 },
    canchado: { target_particula: 4.0, velocidad_molino: 70 },
    camaras: { temperatura_objetivo: 30, humedad_objetivo: 75, co2_objetivo: 2800, dias_maduracion: 180 },
  });

  const saveDraft = async () => {
    if (!draft.id || !draft.nombre) {
      alert('Falta id y nombre'); return;
    }
    await api.createRecipe(draft);
    setCreating(false);
    setDraft(null);
    load();
  };

  return (
    <div className="space-y-px">
      <Card className="p-5" testid="recetas-header">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <SectionTitle kicker="01">Recetas industriales</SectionTitle>
            <p className="font-mono text-xs text-slate-500">Aplicar una receta configura los setpoints de las 4 etapas + las 4 cámaras de maduración en un click.</p>
          </div>
          {isAdmin(user) && !creating && (
            <Btn testid="receta-nueva" variant="ai" onClick={() => { setDraft(blank()); setCreating(true); }}>
              <span className="inline-flex items-center gap-1"><Plus size={13}/> Nueva receta</span>
            </Btn>
          )}
        </div>
      </Card>

      {creating && draft && (
        <Card className="p-5" testid="receta-form">
          <SectionTitle kicker="·">Nueva receta personalizada</SectionTitle>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
            <TextInput testid="r-id" label="ID" value={draft.id} onChange={(v) => setDraft({ ...draft, id: v })} placeholder="mi-yerba" />
            <TextInput testid="r-nombre" label="Nombre" value={draft.nombre} onChange={(v) => setDraft({ ...draft, nombre: v })} placeholder="Yerba Especial" />
            <TextInput testid="r-color" label="Color" value={draft.color} onChange={(v) => setDraft({ ...draft, color: v })} placeholder="#FCD34D" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-4">
            <RecipeSection title="Zapecado">
              <NumberInput testid="r-z-tt" label="Target T" unit="°C" value={draft.zapecado.target_temp} onChange={(v) => setDraft({ ...draft, zapecado: { ...draft.zapecado, target_temp: v } })} />
              <NumberInput testid="r-z-vt" label="Tambor" unit="rpm" value={draft.zapecado.velocidad_tambor} onChange={(v) => setDraft({ ...draft, zapecado: { ...draft.zapecado, velocidad_tambor: v } })} />
              <NumberInput testid="r-z-vc" label="Chips" unit="kg/h" value={draft.zapecado.velocidad_chip} onChange={(v) => setDraft({ ...draft, zapecado: { ...draft.zapecado, velocidad_chip: v } })} />
            </RecipeSection>
            <RecipeSection title="Secado">
              <NumberInput testid="r-s-tt" label="Target T" unit="°C" value={draft.secado.target_temp} onChange={(v) => setDraft({ ...draft, secado: { ...draft.secado, target_temp: v } })} />
              <NumberInput testid="r-s-th" label="Target HR" unit="%" value={draft.secado.target_humedad} onChange={(v) => setDraft({ ...draft, secado: { ...draft.secado, target_humedad: v } })} step={0.5} />
              <NumberInput testid="r-s-va" label="Aire" unit="m/s" value={draft.secado.velocidad_aire} onChange={(v) => setDraft({ ...draft, secado: { ...draft.secado, velocidad_aire: v } })} step={0.1} />
            </RecipeSection>
            <RecipeSection title="Canchado">
              <NumberInput testid="r-c-tp" label="Target part." unit="mm" value={draft.canchado.target_particula} onChange={(v) => setDraft({ ...draft, canchado: { ...draft.canchado, target_particula: v } })} step={0.1} />
              <NumberInput testid="r-c-vm" label="Molino" unit="rpm" value={draft.canchado.velocidad_molino} onChange={(v) => setDraft({ ...draft, canchado: { ...draft.canchado, velocidad_molino: v } })} />
            </RecipeSection>
            <RecipeSection title="Cámaras">
              <NumberInput testid="r-cam-t" label="Obj T" unit="°C" value={draft.camaras.temperatura_objetivo} onChange={(v) => setDraft({ ...draft, camaras: { ...draft.camaras, temperatura_objetivo: v } })} />
              <NumberInput testid="r-cam-h" label="Obj HR" unit="%" value={draft.camaras.humedad_objetivo} onChange={(v) => setDraft({ ...draft, camaras: { ...draft.camaras, humedad_objetivo: v } })} />
              <NumberInput testid="r-cam-co2" label="Obj CO₂" unit="ppm" value={draft.camaras.co2_objetivo} onChange={(v) => setDraft({ ...draft, camaras: { ...draft.camaras, co2_objetivo: v } })} step={50} />
              <NumberInput testid="r-cam-d" label="Días madur." value={draft.camaras.dias_maduracion} onChange={(v) => setDraft({ ...draft, camaras: { ...draft.camaras, dias_maduracion: v } })} />
            </RecipeSection>
          </div>
          <div className="flex gap-2 mt-4">
            <Btn testid="r-save" onClick={saveDraft}><span className="inline-flex items-center gap-1"><Check size={13}/> Guardar</span></Btn>
            <Btn testid="r-cancel" variant="secondary" onClick={() => { setCreating(false); setDraft(null); }}>Cancelar</Btn>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-px hair-grid">
        {recipes.map((r) => (
          <Card key={r.id} className="p-5" testid={`receta-card-${r.id}`}>
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3" style={{ background: r.color || '#FCD34D' }} />
                <div>
                  <h4 className="font-display text-base font-medium text-slate-100">{r.nombre}</h4>
                  <p className="font-mono text-[10px] text-slate-500 uppercase tracking-wider">{r.id}{r.custom ? ' · personalizada' : ''}</p>
                </div>
              </div>
              <div className="flex gap-2">
                <Btn testid={`r-apply-${r.id}`} variant={applied === r.id ? 'ai' : 'primary'} onClick={() => onApply(r.id)}>
                  <span className="inline-flex items-center gap-1">{applied === r.id ? <><Check size={12}/> Aplicada</> : <><ForkKnife size={12}/> Aplicar</>}</span>
                </Btn>
                {r.custom && isAdmin(user) && (
                  <Btn testid={`r-del-${r.id}`} variant="danger" onClick={() => onDelete(r.id)}><Trash size={12}/></Btn>
                )}
              </div>
            </div>
            <p className="text-xs text-slate-400 mb-4">{r.descripcion}</p>
            <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
              <div><span className="text-slate-500">Zap T:</span> <span className="text-slate-200">{r.zapecado?.target_temp}°C</span></div>
              <div><span className="text-slate-500">Tambor:</span> <span className="text-slate-200">{r.zapecado?.velocidad_tambor} rpm</span></div>
              <div><span className="text-slate-500">Sec T:</span> <span className="text-slate-200">{r.secado?.target_temp}°C</span></div>
              <div><span className="text-slate-500">Sec HR:</span> <span className="text-slate-200">{r.secado?.target_humedad}%</span></div>
              <div><span className="text-slate-500">Partícula:</span> <span className="text-slate-200">{r.canchado?.target_particula} mm</span></div>
              <div><span className="text-slate-500">Molino:</span> <span className="text-slate-200">{r.canchado?.velocidad_molino} rpm</span></div>
              <div><span className="text-slate-500">Cam T:</span> <span className="text-slate-200">{r.camaras?.temperatura_objetivo}°C</span></div>
              <div><span className="text-slate-500">Cam HR:</span> <span className="text-slate-200">{r.camaras?.humedad_objetivo}%</span></div>
              <div><span className="text-slate-500">CO₂:</span> <span className="text-slate-200">{r.camaras?.co2_objetivo} ppm</span></div>
              <div><span className="text-slate-500">Madur.:</span> <span className="text-slate-200">{r.camaras?.dias_maduracion} días</span></div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function RecipeSection({ title, children }) {
  return (
    <div className="border p-3" style={{ borderColor: 'var(--border)' }}>
      <h5 className="font-mono text-[10px] uppercase tracking-wider text-slate-500 mb-2">{title}</h5>
      <div className="space-y-2">{children}</div>
    </div>
  );
}
