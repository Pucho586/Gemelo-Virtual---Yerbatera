import React, { useEffect, useState } from 'react';
import { Card, SectionTitle, Metric } from './UI';
import { api } from '../lib/api';

/**
 * Panel de sensores de campo + estado del flujo de masa para una etapa.
 * Sensores derivados del simulador (real-like signals).
 * MassFlow refrescado cada 4s vía /api/massflow.
 */
export default function StageBlock({ stage, state }) {
  const [mf, setMf] = useState(null);

  useEffect(() => {
    const load = () => api.massflowGet().then(setMf).catch(() => {});
    load();
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, []);

  const stageData = state?.[stage] || {};
  const sensors = stageData.sensors || {};
  const mfStage = mf?.stages?.[stage];

  const SENSOR_GROUPS = {
    zapecado: [
      { key: 't_gases_entrada', label: 'T gases (entrada tambor)', unit: '°C', icon: '🔥', desc: 'Termocupla tipo K', color: '#FCA5A5' },
      { key: 't_yerba_salida', label: 'T yerba (salida)', unit: '°C', icon: '🌿', desc: 'Termocupla tipo K', color: '#FBBF24' },
      { key: 'h_salida_nir', label: 'H salida (NIR)', unit: '%', icon: '💧', desc: 'Sensor capacitivo / NIR', color: '#93C5FD' },
      { key: 'vibrometro', label: 'Vibrómetro', unit: 'mm/s', icon: '📳', desc: 'Eje del tambor', color: '#C4B5FD' },
    ],
    secado: [
      { key: 't_aire_entrada', label: 'T aire entrada', unit: '°C', icon: '🔥', desc: 'PT100 / Termocupla K', color: '#FBBF24' },
      { key: 't_aire_salida', label: 'T aire salida', unit: '°C', icon: '💨', desc: 'PT100', color: '#FCA5A5' },
      { key: 't_zona', label: 'T zona cintas', unit: '°C', icon: '🌡', desc: 'PT100 zona', color: '#FBBF24' },
      { key: 'h_final_nir', label: 'H final (NIR)', unit: '%', icon: '💧', desc: 'Higrómetro NIR IR', color: '#93C5FD' },
      { key: 'h_bulbo_humedo', label: 'HR aire extracción', unit: '%', icon: '🌫', desc: 'Bulbo húmedo', color: '#86EFAC' },
    ],
    canchado: [
      { key: 't_rodamientos', label: 'T rodamientos', unit: '°C', icon: '⚙', desc: 'PT100 carcasa', color: '#FBBF24' },
      { key: 'encoder_rpm', label: 'RPM rotor', unit: 'rpm', icon: '🔄', desc: 'Encoder', color: '#86EFAC' },
      { key: 'vibrometro_x', label: 'Vib. X', unit: 'mm/s', icon: '📳', desc: 'Bancada', color: '#C4B5FD' },
      { key: 'vibrometro_y', label: 'Vib. Y', unit: 'mm/s', icon: '📳', desc: 'Bancada', color: '#C4B5FD' },
      { key: 'vibrometro_z', label: 'Vib. Z', unit: 'mm/s', icon: '📳', desc: 'Bancada', color: '#C4B5FD' },
      { key: 'h_nir_salida', label: 'H NIR opcional', unit: '%', icon: '💧', desc: 'Verifica secado', color: '#93C5FD' },
    ],
  };

  const sensorList = SENSOR_GROUPS[stage] || [];

  return (
    <div className="space-y-px">
      {/* Mass flow info */}
      {mfStage && (
        <Card className="p-5" testid={`${stage}-massflow-info`}>
          <SectionTitle kicker="MF">Flujo de masa en esta etapa</SectionTitle>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-px hair-grid mt-3">
            <div className="surface p-3" data-testid={`${stage}-mf-kg`}>
              <Metric label="kg actual" value={mfStage.kg_actual.toFixed(1)} unit="kg"
                      color={mfStage.kg_actual > 0 ? 'var(--amber)' : 'var(--text-2)'} big />
            </div>
            <div className="surface p-3"><Metric label="Acum in (día)" value={mfStage.kg_acum_in.toFixed(0)} unit="kg" /></div>
            <div className="surface p-3"><Metric label="Acum out (día)" value={mfStage.kg_acum_out.toFixed(0)} unit="kg" /></div>
            <div className="surface p-3"><Metric label="Merma acum" value={mfStage.merma_kg_acum.toFixed(1)} unit="kg" color="#FCA5A5" /></div>
            <div className="surface p-3">
              <Metric label="T_in / H_in"
                value={(mfStage.T_in != null ? `${mfStage.T_in.toFixed(1)}°C` : '—') + ' / ' +
                       (mfStage.H_in != null ? `${mfStage.H_in.toFixed(1)}%` : '—')} />
            </div>
          </div>
          {mfStage.kg_actual <= 0 && (
            <p className="mt-2 text-[11px] font-mono text-slate-500">
              Sin masa en esta etapa. Cargá hoja verde y transferí desde la pestaña <span className="text-amber-300">Flujo de masa</span>.
            </p>
          )}
        </Card>
      )}

      {/* Sensores derivados */}
      {sensorList.length > 0 && (
        <Card className="p-5" testid={`${stage}-sensors`}>
          <SectionTitle kicker="S">Sensores de campo (lecturas en vivo)</SectionTitle>
          <p className="text-[11px] font-mono text-slate-500 mt-1">
            Variables derivadas del modelo físico — simulan instrumentación real instalada en planta.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-px hair-grid mt-3">
            {sensorList.map((s) => {
              const v = sensors[s.key];
              return (
                <div key={s.key} className="surface p-3" data-testid={`${stage}-sensor-${s.key}`}>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">
                    {s.icon} {s.label}
                  </div>
                  <div className="font-display text-xl tabular-nums" style={{ color: s.color || 'var(--text)' }}>
                    {v != null ? Number(v).toFixed(s.unit === 'rpm' ? 0 : 1) : '—'}
                    <span className="text-[10px] text-slate-500 ml-1">{s.unit}</span>
                  </div>
                  <div className="text-[9px] font-mono text-slate-500 mt-0.5 leading-tight">{s.desc}</div>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}

/**
 * Versión específica para una cámara puntual (NDIR CO2, PT100 doble, vapor).
 */
export function ChamberSensorsBlock({ cam }) {
  if (!cam) return null;
  const s = cam.sensors || {};
  const items = [
    { key: 'pt100_pared', label: 'PT100 pared', unit: '°C', color: '#FBBF24', desc: 'T en pared' },
    { key: 'pt100_centro_pila', label: 'PT100 centro pila', unit: '°C', color: '#FCA5A5', desc: 'T centro yerba' },
    { key: 'hr_capacitivo', label: 'HR capacitivo', unit: '%', color: '#93C5FD', desc: 'Humedad relativa' },
    { key: 'co2_ndir', label: 'CO₂ NDIR', unit: 'ppm', color: '#86EFAC', desc: 'Sensor infrarrojo' },
    { key: 't_linea_vapor', label: 'T línea vapor', unit: '°C', color: '#67E8F9', desc: 'Si hay inyección' },
    { key: 'caudal_vapor', label: 'Caudal vapor', unit: 'kg/h', color: '#67E8F9', desc: 'Caudalímetro' },
  ];
  return (
    <div className="grid grid-cols-3 md:grid-cols-6 gap-px hair-grid mt-3">
      {items.map(it => {
        const v = s[it.key];
        return (
          <div key={it.key} className="surface p-2.5" data-testid={`cam-${cam.id}-sensor-${it.key}`}>
            <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mb-0.5">{it.label}</div>
            <div className="font-display text-base tabular-nums" style={{ color: it.color }}>
              {v != null ? Number(v).toFixed(it.unit === 'ppm' ? 0 : 1) : '—'}
              <span className="text-[9px] text-slate-500 ml-0.5">{it.unit}</span>
            </div>
            <div className="text-[8px] font-mono text-slate-600 mt-0.5">{it.desc}</div>
          </div>
        );
      })}
    </div>
  );
}
