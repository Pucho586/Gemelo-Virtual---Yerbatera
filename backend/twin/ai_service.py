"""Asistente IA + detección de anomalías + forecast con Gemini 3 Flash."""
import json
import logging
import os
import statistics
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3-flash-preview"
PROVIDER = "gemini"

SYSTEM_PROMPT = (
    "Sos un ingeniero experto en procesos industriales de yerba mate. "
    "Asistís a un operario que monitorea un gemelo digital con etapas: "
    "Zapecado (~400-600°C), Secado (80-110°C, 30→7% humedad), Canchado "
    "(molienda gruesa) y 4 Cámaras de maduración (T 30-40°C, HR 70-85%, "
    "CO2 ~3000 ppm). Respondé en español rioplatense, breve, técnico y "
    "concreto. Si te pasan datos, usalos; si faltan, pedilos. Usá unidades "
    "del SI. Cuando sugieras cambios, explicá el porqué."
)


def _get_api_key() -> str:
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key:
        raise RuntimeError("Falta EMERGENT_LLM_KEY en backend/.env")
    return key


class AIService:
    """
    Mantiene sesiones de chat y expone helpers de análisis.
    `sessions` es un dict session_id -> LlmChat (una instancia por sesión).
    """

    def __init__(self):
        self.sessions: Dict[str, LlmChat] = {}
        self.session_messages: Dict[str, List[Dict[str, str]]] = {}

    def _get_or_create_chat(self, session_id: str) -> LlmChat:
        if session_id not in self.sessions:
            chat = LlmChat(
                api_key=_get_api_key(),
                session_id=session_id,
                system_message=SYSTEM_PROMPT,
            ).with_model(PROVIDER, GEMINI_MODEL)
            self.sessions[session_id] = chat
            self.session_messages[session_id] = []
        return self.sessions[session_id]

    # ---------- CHAT ----------
    async def chat(self, session_id: str, message: str, context: Dict[str, Any] | None = None) -> str:
        chat = self._get_or_create_chat(session_id)
        text = message
        if context:
            text = (
                f"Estado actual del gemelo (JSON):\n"
                f"```json\n{json.dumps(context, ensure_ascii=False, default=str)}\n```\n\n"
                f"Pregunta del operario: {message}"
            )
        resp = await chat.send_message(UserMessage(text=text))
        # Guardar historial (en memoria)
        self.session_messages[session_id].append({"role": "user", "content": message, "ts": datetime.now(timezone.utc).isoformat()})
        self.session_messages[session_id].append({"role": "assistant", "content": str(resp), "ts": datetime.now(timezone.utc).isoformat()})
        return str(resp)

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        return self.session_messages.get(session_id, [])

    def reset_session(self, session_id: str):
        self.sessions.pop(session_id, None)
        self.session_messages.pop(session_id, None)

    # ---------- ANÁLISIS ----------
    @staticmethod
    def _detect_static_anomalies(state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Reglas determinísticas básicas que corren antes que la IA."""
        out: List[Dict[str, Any]] = []
        z = state["zapecado"]
        if z["temperatura"] > 580:
            out.append({"severity": "high", "stage": "zapecado",
                        "message": f"Temperatura de zapecado peligrosa: {z['temperatura']:.1f} °C (>580)."})
        elif z["temperatura"] > 540 and z["estado_alimentacion"]:
            out.append({"severity": "medium", "stage": "zapecado",
                        "message": f"Zapecado caliente: {z['temperatura']:.1f} °C — revisar vel. de chips ({z['velocidad_chip']})."})
        s = state["secado"]
        if s["humedad"] > 35 and s["estado"]:
            out.append({"severity": "medium", "stage": "secado",
                        "message": f"Humedad alta en secado ({s['humedad']:.1f}%) — aumentar vel. de aire."})
        if s["humedad"] < 6:
            out.append({"severity": "medium", "stage": "secado",
                        "message": f"Yerba sobre-secada ({s['humedad']:.1f}%) — bajar temperatura o vel. de aire."})
        c = state["canchado"]
        if c["tamano_particula"] < 1.0 and c["estado"]:
            out.append({"severity": "low", "stage": "canchado",
                        "message": f"Partícula muy fina ({c['tamano_particula']:.1f} mm) — bajar rpm del molino."})
        for cam in state["camaras"]:
            if cam["co2"] > 5500:
                out.append({"severity": "high", "stage": cam["nombre"],
                            "message": f"CO₂ muy alto ({cam['co2']:.0f} ppm) — encender ventilador YA."})
            elif cam["co2"] > 4200:
                out.append({"severity": "medium", "stage": cam["nombre"],
                            "message": f"CO₂ elevado ({cam['co2']:.0f} ppm) en {cam['nombre']}."})
            if abs(cam["temperatura"] - cam["temperatura_obj"]) > 4:
                out.append({"severity": "low", "stage": cam["nombre"],
                            "message": f"{cam['nombre']}: temperatura desviada {cam['temperatura']:.1f}°C vs obj {cam['temperatura_obj']}°C."})
        return out

    async def analyze_anomalies(self, state: Dict[str, Any], use_ai: bool = True) -> Dict[str, Any]:
        rules = self._detect_static_anomalies(state)
        ai_text = None
        if use_ai and rules:
            try:
                session = f"anomaly-{uuid.uuid4().hex[:8]}"
                chat = LlmChat(
                    api_key=_get_api_key(),
                    session_id=session,
                    system_message=SYSTEM_PROMPT,
                ).with_model(PROVIDER, GEMINI_MODEL)
                prompt = (
                    "Analizá estas anomalías detectadas en el gemelo digital y dame un diagnóstico "
                    "breve (máx 4 frases) con la causa más probable y la acción inmediata recomendada.\n\n"
                    f"Anomalías: {json.dumps(rules, ensure_ascii=False)}\n\n"
                    f"Estado completo: {json.dumps(state, ensure_ascii=False, default=str)}"
                )
                resp = await chat.send_message(UserMessage(text=prompt))
                ai_text = str(resp)
            except Exception as e:
                logger.warning(f"AI anomaly analysis failed: {e}")
                ai_text = f"(IA no disponible: {e})"
        return {"anomalies": rules, "diagnosis": ai_text}

    # ---------- FORECAST ----------
    @staticmethod
    def _linear_forecast(history: List[Dict[str, Any]], path: List[str], horizon_steps: int = 30) -> List[Dict[str, Any]]:
        """Forecast lineal simple por mínimos cuadrados (estadística pura)."""
        if len(history) < 5:
            return []
        ys = []
        for h in history[-60:]:
            v = h
            try:
                for p in path:
                    v = v[p]
                ys.append(float(v))
            except Exception:
                ys.append(None)
        ys = [y for y in ys if y is not None]
        if len(ys) < 5:
            return []
        n = len(ys)
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
        den = sum((xs[i] - mean_x) ** 2 for i in range(n)) or 1e-9
        slope = num / den
        intercept = mean_y - slope * mean_x
        return [{"step": i, "value": round(intercept + slope * (n + i), 2)} for i in range(1, horizon_steps + 1)]

    def forecast(self, history: List[Dict[str, Any]], horizon_steps: int = 30) -> Dict[str, Any]:
        return {
            "horizon_steps": horizon_steps,
            "zapecado_temp": self._linear_forecast(history, ["zapecado", "temperatura"], horizon_steps),
            "secado_temp": self._linear_forecast(history, ["secado", "temperatura"], horizon_steps),
            "secado_hum": self._linear_forecast(history, ["secado", "humedad"], horizon_steps),
            "cam1_co2": self._linear_forecast(history, ["camaras", 0, "co2"], horizon_steps) if history and history[-1]["camaras"] else [],
            "trend_summary": self._trend_summary(history),
        }

    @staticmethod
    def _trend_summary(history: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(history) < 10:
            return {}
        recent = history[-30:]
        try:
            zap = [h["zapecado"]["temperatura"] for h in recent]
            sec_h = [h["secado"]["humedad"] for h in recent]
            return {
                "zapecado_mean": round(statistics.mean(zap), 1),
                "zapecado_stdev": round(statistics.stdev(zap), 2) if len(zap) > 1 else 0.0,
                "secado_humedad_mean": round(statistics.mean(sec_h), 1),
            }
        except Exception:
            return {}
