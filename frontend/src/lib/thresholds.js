/*
 * Umbrales de operación centralizados.
 * Derivados de backend/twin/alarms.py y config_yerba.yaml para que las
 * zonas de color de gauges y gráficos coincidan EXACTAMENTE con las alarmas.
 *
 * zones: tramos monótonos evaluados con "value <= upTo" (ver Gauges.zoneFor).
 */
const OK = 'var(--green)';
const WARN = 'var(--amber)';
const BAD = 'var(--red)';

export const TH = {
  zapecado_temp: {
    min: 300, max: 650, unit: '°C', target: 450, label: 'Temperatura',
    zones: [
      { upTo: 540, color: OK },   // operación normal
      { upTo: 580, color: WARN }, // alarma high (alarms.py)
      { upTo: 650, color: BAD },  // alarma urgent >580
    ],
  },
  secado_temp: {
    min: 0, max: 130, unit: '°C', target: 90, label: 'Temperatura',
    zones: [
      { upTo: 105, color: OK },
      { upTo: 118, color: WARN },
      { upTo: 130, color: BAD },
    ],
  },
  secado_hum: {
    // Ideal 6–30%. <6 = sobre-secada (high). >35 = secado ineficiente (medium).
    min: 0, max: 50, unit: '%', target: 30, label: 'Humedad yerba',
    zones: [
      { upTo: 6, color: BAD },
      { upTo: 30, color: OK },
      { upTo: 35, color: WARN },
      { upTo: 50, color: BAD },
    ],
  },
  canchado_part: {
    // <1.0 mm fuera de spec (demasiado fina).
    min: 0, max: 15, unit: 'mm', target: 3, label: 'Partícula',
    zones: [
      { upTo: 1.0, color: WARN },
      { upTo: 8, color: OK },
      { upTo: 12, color: WARN },
      { upTo: 15, color: BAD },
    ],
  },
  camara_temp: {
    min: 0, max: 60, unit: '°C', target: 30, label: 'Temperatura',
    zones: [
      { upTo: 42, color: OK },
      { upTo: 50, color: WARN },
      { upTo: 60, color: BAD },
    ],
  },
  camara_hum: {
    min: 0, max: 100, unit: '%', target: 75, label: 'Humedad',
    zones: [
      { upTo: 60, color: WARN },
      { upTo: 88, color: OK },
      { upTo: 100, color: WARN },
    ],
  },
  camara_co2: {
    // >4200 medium, >5500 urgent (alarms.py). Objetivo ~2800 ppm.
    min: 0, max: 8000, unit: 'ppm', target: 2800, label: 'CO₂',
    zones: [
      { upTo: 4200, color: OK },
      { upTo: 5500, color: WARN },
      { upTo: 8000, color: BAD },
    ],
  },
};

// Banda de operación "óptima" (verde) para pintar en los gráficos de línea.
export const OK_BAND = {
  zap_t: [null, 540],
  sec_t: [null, 105],
  sec_h: [6, 30],
  cam_t: [null, 42],
  cam_co2: [null, 4200],
};
