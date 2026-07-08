"""Asistente IA + detección de anomalías + forecast.

Proveedor de IA seleccionable en configuración (config_yerba.yaml → `ai.provider`):
  - "claude"  → SDK oficial `anthropic` (variable ANTHROPIC_API_KEY)
  - "gemini"  → SDK oficial `google-genai`  (variable GEMINI_API_KEY)

Así se puede comparar cuál funciona mejor sin tocar el código.
El historial de conversación se mantiene en memoria (la API es stateless).
"""
import json
import logging
import os
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Modelos por defecto (editables desde config)
DEFAULT_CLAUDE_MODEL = "claude-opus-4-8"
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"

SYSTEM_PROMPT = (
    "Sos un ingeniero experto en procesos industriales de yerba mate. "
    "Asistís a un operario que monitorea un gemelo digital con etapas: "
    "Zapecado (~400-600°C), Secado (80-110°C, 30→7% humedad), Canchado "
    "(molienda gruesa) y 4 Cámaras de maduración (T 30-40°C, HR 70-85%, "
    "CO2 ~3000 ppm). Respondé en español rioplatense, breve, técnico y "
    "concreto. Si te pasan datos, usalos; si faltan, pedilos. Usá unidades "
    "del SI. Cuando sugieras cambios, explicá el porqué."
)

VALID_PROVIDERS = ("claude", "gemini")


class AIService:
    """
    Asistente con proveedor conmutable (Claude / Gemini).
    `session_messages` guarda el historial por sesión en memoria.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.provider: str = (config.get("provider") or os.environ.get("AI_PROVIDER") or "claude").lower()
        if self.provider not in VALID_PROVIDERS:
            self.provider = "claude"
        self.claude_model: str = config.get("claude_model") or DEFAULT_CLAUDE_MODEL
        self.gemini_model: str = config.get("gemini_model") or DEFAULT_GEMINI_MODEL
        self.session_messages: Dict[str, List[Dict[str, str]]] = {}
        self._anthropic = None  # cliente perezoso
        self._genai = None

    # ---------- Selección de proveedor ----------
    def set_provider(self, provider: str) -> str:
        provider = (provider or "").lower()
        if provider not in VALID_PROVIDERS:
            raise ValueError(f"Proveedor inválido: {provider}. Usá uno de {VALID_PROVIDERS}.")
        self.provider = provider
        return self.provider

    def get_config(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "claude_model": self.claude_model,
            "gemini_model": self.gemini_model,
            "providers": [
                {"id": "claude", "label": "Claude (Anthropic)", "model": self.claude_model,
                 "key_env": "ANTHROPIC_API_KEY", "key_present": bool(os.environ.get("ANTHROPIC_API_KEY"))},
                {"id": "gemini", "label": "Google Gemini", "model": self.gemini_model,
                 "key_env": "GEMINI_API_KEY", "key_present": bool(os.environ.get("GEMINI_API_KEY"))},
            ],
        }

    # ---------- Clientes ----------
    def _get_anthropic(self):
        if self._anthropic is None:
            from anthropic import AsyncAnthropic  # import perezoso
            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError("Falta ANTHROPIC_API_KEY en el entorno del backend.")
            self._anthropic = AsyncAnthropic(api_key=key)
        return self._anthropic

    def _get_genai(self):
        if self._genai is None:
            from google import genai  # import perezoso
            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                raise RuntimeError("Falta GEMINI_API_KEY en el entorno del backend.")
            self._genai = genai.Client(api_key=key)
        return self._genai

    # ---------- Llamadas por proveedor ----------
    async def _complete(self, messages: List[Dict[str, str]]) -> str:
        """messages: [{role: 'user'|'assistant', content: str}, ...]"""
        if self.provider == "gemini":
            return await self._complete_gemini(messages)
        return await self._complete_claude(messages)

    async def _complete_claude(self, messages: List[Dict[str, str]]) -> str:
        client = self._get_anthropic()
        resp = await client.messages.create(
            model=self.claude_model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()

    async def _complete_gemini(self, messages: List[Dict[str, str]]) -> str:
        from google.genai import types
        client = self._get_genai()
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages
        ]
        resp = await client.aio.models.generate_content(
            model=self.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
        return (resp.text or "").strip()

    # ---------- CHAT ----------
    async def chat(self, session_id: str, message: str, context: Dict[str, Any] | None = None) -> str:
        history = self.session_messages.setdefault(session_id, [])
        text = message
        if context:
            text = (
                f"Estado actual del gemelo (JSON):\n"
                f"```json\n{json.dumps(context, ensure_ascii=False, default=str)}\n```\n\n"
                f"Pregunta del operario: {message}"
            )
        convo = [{"role": h["role"], "content": h["content"]} for h in history]
        convo.append({"role": "user", "content": text})
        reply = await self._complete(convo)
        # Guardar historial (se guarda el mensaje "limpio", sin el JSON de contexto)
        now = datetime.now(timezone.utc).isoformat()
        history.append({"role": "user", "content": message, "ts": now})
        history.append({"role": "assistant", "content": reply, "ts": now})
        return reply

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        return self.session_messages.get(session_id, [])

    def reset_session(self, session_id: str):
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
                prompt = (
                    "Analizá estas anomalías detectadas en el gemelo digital y dame un diagnóstico "
                    "breve (máx 4 frases) con la causa más probable y la acción inmediata recomendada.\n\n"
                    f"Anomalías: {json.dumps(rules, ensure_ascii=False)}\n\n"
                    f"Estado completo: {json.dumps(state, ensure_ascii=False, default=str)}"
                )
                ai_text = await self._complete([{"role": "user", "content": prompt}])
            except Exception as e:
                logger.warning(f"AI anomaly analysis failed: {e}")
                ai_text = f"(IA no disponible: {e})"
        return {"anomalies": rules, "diagnosis": ai_text, "provider": self.provider}

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
