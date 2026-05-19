import React, { useEffect, useState } from 'react';
import { X, ArrowRight, ArrowLeft, CheckCircle, GraduationCap } from '@phosphor-icons/react';

/**
 * Tour de primer turno: muestra 6 pasos con instrucciones claras para operar el gemelo.
 * Se autoabre la primera vez (si localStorage no marca "completado"). Reabribible desde header.
 */
export default function TourModal({ onClose, onJumpTab }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    try { localStorage.setItem('yerba_tour_seen', '1'); } catch (e) { /* ignore */ }
  }, []);

  const steps = [
    {
      title: 'Bienvenido al Gemelo Digital de la Yerbatera',
      icon: '👋',
      body: (
        <>
          <p className="text-sm text-slate-300 leading-relaxed">
            Este sistema simula y/o refleja una planta real de yerba mate. Vas a aprender en 6 pasos cómo
            cargar yerba, procesarla y leer los resultados.
          </p>
          <p className="text-xs text-slate-400 mt-3 font-mono">
            En cualquier momento podés cerrar este tour y volver a abrirlo desde el botón <span className="text-amber-300">"Tour"</span> del encabezado.
          </p>
        </>
      ),
    },
    {
      title: '1 · Cargar hoja verde en Recepción',
      icon: '🌿',
      tab: 'massflow',
      body: (
        <>
          <p className="text-sm text-slate-300 leading-relaxed">
            Andá a la pestaña <span className="text-amber-300">"Flujo de masa"</span>. En la card <span className="text-green-400">"Cargar hoja verde"</span>:
          </p>
          <ul className="text-xs text-slate-400 font-mono mt-2 space-y-1 pl-3 leading-relaxed">
            <li>• Ingresá los <span className="text-amber-300">kg</span> de hoja recién cosechada</li>
            <li>• (Opcional) T y H — si los dejás vacíos se usan los del ambiente y 55% de humedad</li>
            <li>• Hacé clic en <span className="text-green-400">"Cargar a Recepción"</span></li>
          </ul>
          <p className="text-xs text-slate-500 mt-3 font-mono">
            La etapa Recepción cambia a <span className="text-green-400">"Listo para pasar"</span> inmediatamente (no tiene tiempo mínimo).
          </p>
        </>
      ),
    },
    {
      title: '2 · Pasar al siguiente paso',
      icon: '➡️',
      tab: 'massflow',
      body: (
        <>
          <p className="text-sm text-slate-300 leading-relaxed">
            Cuando una etapa muestra <span className="text-green-400">"Listo para pasar"</span>, hacé clic en la flecha <span className="text-green-400 font-mono">→</span> entre etapas.
          </p>
          <ul className="text-xs text-slate-400 font-mono mt-2 space-y-1 pl-3 leading-relaxed">
            <li>• Se aplica la <span className="text-red-300">merma</span> típica del paso de origen (configurable)</li>
            <li>• La T y H de salida (de los sensores reales) pasan como condición de entrada de la etapa siguiente</li>
            <li>• Mientras la etapa procesa, el botón <span className="text-slate-400">→</span> queda inhabilitado y ves <span className="text-amber-300">"Procesando..."</span> con barra de avance</li>
          </ul>
          <p className="text-xs text-slate-500 mt-3 font-mono">
            Admin: si necesitás saltear el tiempo (entrenamiento), aparece un botón <span className="text-amber-300">"⚡ forzar"</span>.
          </p>
        </>
      ),
    },
    {
      title: '3 · Monitorear cada etapa',
      icon: '📊',
      body: (
        <>
          <p className="text-sm text-slate-300 leading-relaxed">
            Cada etapa tiene su propia pestaña con gráficos en vivo y sensores derivados:
          </p>
          <ul className="text-xs text-slate-400 font-mono mt-2 space-y-1 pl-3 leading-relaxed">
            <li>• <span className="text-red-300">Zapecado</span>: T entrada/salida tambor, H NIR, vibrómetro</li>
            <li>• <span className="text-amber-300">Secado</span>: T aire entrada/salida/zona, H final NIR, bulbo húmedo</li>
            <li>• <span className="text-blue-300">Canchado</span>: T rodamientos, encoder, vibrómetros XYZ</li>
            <li>• <span className="text-violet-300">Cámaras</span>: PT100 doble, NDIR de CO₂, vapor</li>
          </ul>
          <p className="text-xs text-slate-500 mt-3 font-mono">
            En cada pestaña ves también cuántos kg de masa hay en proceso en esa etapa.
          </p>
        </>
      ),
    },
    {
      title: '4 · Configurar precios, mermas y turnos',
      icon: '⚙️',
      tab: 'ops',
      body: (
        <>
          <p className="text-sm text-slate-300 leading-relaxed">
            En <span className="text-amber-300">"Operaciones"</span> (solo admin) podés tunear el sistema según tu planta real:
          </p>
          <ul className="text-xs text-slate-400 font-mono mt-2 space-y-1 pl-3 leading-relaxed">
            <li>• <span className="text-amber-300">Energía</span>: precio kWh, kg chips, kg yerba venta, PCI chips, turnos por día</li>
            <li>• <span className="text-amber-300">Mantenimiento</span>: umbrales de lubricación / rodamientos / overhaul por componente</li>
            <li>• En <span className="text-amber-300">"Flujo de masa"</span>: mermas % y tiempos mín. de procesamiento por etapa</li>
          </ul>
        </>
      ),
    },
    {
      title: '5 · Probar escenarios "What-if"',
      icon: '🧪',
      tab: 'fase4',
      body: (
        <>
          <p className="text-sm text-slate-300 leading-relaxed">
            En <span className="text-amber-300">"Replay & What-if"</span> podés correr hasta 3 simulaciones paralelas con parámetros distintos del baseline:
          </p>
          <ul className="text-xs text-slate-400 font-mono mt-2 space-y-1 pl-3 leading-relaxed">
            <li>• Elegí un <span className="text-amber-300">preset</span> ("Secado +10°C", "Throughput +20%", etc.)</li>
            <li>• Ponele un nombre y clic en <span className="text-green-400">"Crear escenario"</span></li>
            <li>• Compará OEE, costo/kg, kWh, producción en la tabla en vivo</li>
            <li>• También está disponible vía Modbus units 20-22, OPC UA y MQTT para tu SCADA</li>
          </ul>
        </>
      ),
    },
    {
      title: '6 · Reportes y manuales',
      icon: '📄',
      tab: 'ops',
      body: (
        <>
          <p className="text-sm text-slate-300 leading-relaxed">
            Cuando termines el turno:
          </p>
          <ul className="text-xs text-slate-400 font-mono mt-2 space-y-1 pl-3 leading-relaxed">
            <li>• En <span className="text-amber-300">Operaciones → Reportes</span> generás un PDF mensual o por lote</li>
            <li>• El botón <span className="text-amber-300">"📖 Manual"</span> en el encabezado tiene el Manual de Operaciones y Técnico completos</li>
            <li>• Y este tour siempre podés reabrirlo desde el botón <span className="text-amber-300">"Tour"</span></li>
          </ul>
          <p className="text-sm text-green-400 mt-4 font-mono">
            ¡Listo, ya podés operar! 🎉
          </p>
        </>
      ),
    },
  ];

  const s = steps[step];
  const isLast = step === steps.length - 1;
  const isFirst = step === 0;

  const goTab = () => {
    if (s.tab && onJumpTab) onJumpTab(s.tab);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" data-testid="tour-modal" onClick={onClose}>
      <div
        className="bg-[#0E1411] border w-[92vw] max-w-2xl flex flex-col"
        style={{ borderColor: 'var(--amber)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2 text-amber-300">
            <GraduationCap size={20} />
            <h2 className="font-display text-base font-medium">Tour guiado · Primer turno</h2>
          </div>
          <button onClick={onClose} data-testid="tour-close" className="text-slate-400 hover:text-slate-100">
            <X size={18} />
          </button>
        </div>

        {/* Progress dots */}
        <div className="flex justify-center gap-1 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
          {steps.map((_, i) => (
            <button
              key={i}
              data-testid={`tour-dot-${i}`}
              onClick={() => setStep(i)}
              className={`w-2.5 h-2.5 rounded-full transition-all ${i === step ? 'bg-amber-300 w-6' : i < step ? 'bg-green-400' : 'bg-slate-700'}`}
            />
          ))}
        </div>

        {/* Body */}
        <div className="px-8 py-6 min-h-[280px]">
          <div className="text-5xl mb-3">{s.icon}</div>
          <h3 className="font-display text-xl text-slate-100 mb-3">{s.title}</h3>
          <div data-testid={`tour-step-${step}`}>{s.body}</div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t bg-[#0a0d0c]" style={{ borderColor: 'var(--border)' }}>
          <button
            onClick={() => setStep(s => Math.max(0, s - 1))}
            disabled={isFirst}
            data-testid="tour-prev"
            className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-mono border text-slate-300 hover:text-slate-100 disabled:opacity-30 disabled:cursor-not-allowed"
            style={{ borderColor: 'var(--border)' }}
          >
            <ArrowLeft size={12}/> Anterior
          </button>
          <div className="flex items-center gap-2">
            {s.tab && (
              <button
                onClick={goTab}
                data-testid="tour-goto-tab"
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-mono border text-amber-300 hover:bg-amber-500/10 border-amber-500/40"
              >
                Ir a la pestaña →
              </button>
            )}
            {!isLast ? (
              <button
                onClick={() => setStep(s => Math.min(steps.length - 1, s + 1))}
                data-testid="tour-next"
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-mono border text-green-300 hover:bg-green-500/10 border-green-500/40"
              >
                Siguiente <ArrowRight size={12}/>
              </button>
            ) : (
              <button
                onClick={onClose}
                data-testid="tour-finish"
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-mono border text-green-300 hover:bg-green-500/10 border-green-500/40"
              >
                <CheckCircle size={12} weight="fill"/> Terminar
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
