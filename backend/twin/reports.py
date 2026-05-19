"""Generación de reportes PDF: mensual y por lote."""
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

REPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="Heading", fontSize=18, leading=22, textColor=colors.HexColor("#1a1a1a"), spaceAfter=12, fontName="Helvetica-Bold"))
    s.add(ParagraphStyle(name="Sub", fontSize=12, leading=16, textColor=colors.HexColor("#666"), spaceAfter=8))
    s.add(ParagraphStyle(name="KPILabel", fontSize=8, leading=10, textColor=colors.HexColor("#888"), fontName="Helvetica"))
    s.add(ParagraphStyle(name="KPIVal", fontSize=16, leading=18, textColor=colors.HexColor("#1a1a1a"), fontName="Helvetica-Bold"))
    s.add(ParagraphStyle(name="Foot", fontSize=8, leading=10, textColor=colors.HexColor("#999"), alignment=2))
    return s


def _header(title: str, subtitle: str, styles):
    return [
        Paragraph(title, styles["Heading"]),
        Paragraph(subtitle, styles["Sub"]),
    ]


def _kpi_grid(items: List[tuple], styles):
    data = []
    row = []
    for i, (label, value) in enumerate(items):
        cell = [Paragraph(label.upper(), styles["KPILabel"]), Paragraph(str(value), styles["KPIVal"])]
        row.append(cell)
        if (i + 1) % 4 == 0:
            data.append(row); row = []
    if row:
        while len(row) < 4:
            row.append("")
        data.append(row)
    t = Table(data, colWidths=[4 * cm] * 4)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f5f3")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dcdcdc")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dcdcdc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _section_title(text: str, styles):
    return Paragraph(f"<b>{text}</b>",
                     ParagraphStyle(name="ST", parent=styles["Sub"], fontSize=12, textColor=colors.HexColor("#1a1a1a"), spaceAfter=6, spaceBefore=14))


def _table(headers: List[str], rows: List[List[Any]]):
    data = [headers] + rows
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a1a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafaf9")]),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dcdcdc")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e8e8e6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def build_monthly_report(data: Dict[str, Any], filepath: Path | None = None) -> Path:
    """Genera reporte mensual con OEE, lotes, alarmas, energía."""
    styles = _styles()
    out = filepath or (REPORTS_DIR / f"reporte_mensual_{datetime.now(timezone.utc).strftime('%Y%m')}.pdf")
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    story = []
    story += _header("Reporte Mensual · Gemelo Digital Yerba Mate",
                     f"Período: {data.get('period', '–')} · Planta: {data.get('plant', 'Yerbatera')}", styles)

    # KPIs principales
    oee = data.get("oee", {})
    story.append(_section_title("Resumen ejecutivo", styles))
    story.append(_kpi_grid([
        ("OEE", f"{(oee.get('oee', 0) * 100):.1f}%"),
        ("Disponibilidad", f"{(oee.get('availability', 0) * 100):.1f}%"),
        ("Rendimiento", f"{(oee.get('performance', 0) * 100):.1f}%"),
        ("Calidad", f"{(oee.get('quality', 0) * 100):.1f}%"),
        ("Producción", f"{data.get('kg_produced', 0):.0f} kg"),
        ("Costo total", f"$ {data.get('energy_cost_ars', 0):,.0f}"),
        ("Costo/kg", f"$ {data.get('cost_per_kg_ars', 0):,.0f}"),
        ("Margen/kg", f"$ {data.get('margin_per_kg_ars', 0):,.0f}"),
    ], styles))

    # Lotes
    story.append(_section_title("Lotes del período", styles))
    batches = data.get("batches", [])
    if batches:
        rows = []
        for b in batches[:30]:
            rows.append([
                b.get("id", "")[:20],
                b.get("status", ""),
                (b.get("receta_nombre") or "—")[:25],
                f"{b.get('kg_entrada', 0):.0f}",
                f"{b.get('kg_salida', '–') if b.get('kg_salida') is not None else '–'}",
                f"{b.get('merma_pct', '–') if b.get('merma_pct') is not None else '–'}",
                (b.get("operario") or "")[:14],
            ])
        story.append(_table(["ID", "Estado", "Receta", "Kg in", "Kg out", "Merma %", "Operario"], rows))
    else:
        story.append(Paragraph("Sin lotes en el período.", styles["Sub"]))

    # Alarmas
    story.append(PageBreak())
    story.append(_section_title("Top alarmas del período", styles))
    alarms = data.get("alarms", [])
    if alarms:
        rows = []
        for a in alarms[:30]:
            rows.append([
                a.get("ts", "")[:19].replace("T", " "),
                a.get("priority", "")[:8],
                a.get("name", "")[:42],
                a.get("tag", "")[:22],
                a.get("status", "")[:16],
                (a.get("acked_by") or "—")[:14],
            ])
        story.append(_table(["Fecha", "Prio", "Alarma", "Tag", "Estado", "ACK por"], rows))
    else:
        story.append(Paragraph("Sin alarmas en el período.", styles["Sub"]))

    # Energía
    story.append(_section_title("Consumo energético por componente", styles))
    energy_rows = []
    for comp, kwh in data.get("kwh_by_component", {}).items():
        hours = data.get("runtime_hours", {}).get(comp, 0.0)
        energy_rows.append([comp, f"{hours:.1f}", f"{kwh:.1f}", f"$ {kwh * data.get('kwh_price', 120):,.0f}"])
    if energy_rows:
        story.append(_table(["Componente", "Horas marcha", "kWh", "Costo ARS"], energy_rows))
    story.append(Paragraph(f"Gas natural: {data.get('gas_m3', 0):.1f} m³ ($ {data.get('gas_cost_ars', 0):,.0f})",
                           styles["Sub"]))

    # Mantenimiento
    story.append(_section_title("Mantenimiento pendiente", styles))
    maint = data.get("maintenance", {}).get("items", [])
    pending = [m for m in maint if m["status"] in ("warning", "due")]
    if pending:
        rows = [[m["componente"], m["accion"], f"{m['horas_marcha']:.0f}", f"{m['umbral_h']:.0f}", m["status"].upper()]
                for m in pending]
        story.append(_table(["Componente", "Acción", "h marcha", "h umbral", "Estado"], rows))
    else:
        story.append(Paragraph("Sin mantenimiento pendiente.", styles["Sub"]))

    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(f"Generado por Yerbatera Industrial Twin · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", styles["Foot"]))

    doc.build(story)
    return out


def build_batch_report(batch: Dict[str, Any], ops_summary: Dict[str, Any], filepath: Path | None = None) -> Path:
    styles = _styles()
    out = filepath or (REPORTS_DIR / f"lote_{batch.get('id', 'sin_id').replace('/', '_')}.pdf")
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    story = []
    story += _header(f"Reporte de Lote · {batch.get('id')}",
                     f"Receta: {batch.get('receta_nombre', '—')} · Estado: {batch.get('status', '—')}", styles)

    merma = batch.get("merma_pct")
    story.append(_kpi_grid([
        ("Kg entrada", f"{batch.get('kg_entrada', 0):.0f}"),
        ("Kg salida", f"{batch.get('kg_salida', '—') if batch.get('kg_salida') is not None else '—'}"),
        ("Merma %", f"{merma if merma is not None else '—'}"),
        ("Operario", batch.get("operario", "—")),
    ], styles))

    story.append(_section_title("Datos", styles))
    rows = [
        ["Inicio", batch.get("started_at", "—")],
        ["Fin", batch.get("finished_at", "—") or "—"],
        ["Receta ID", batch.get("receta_id", "—") or "—"],
        ["Observaciones", batch.get("observaciones", "—") or "—"],
    ]
    story.append(_table(["Campo", "Valor"], rows))

    if ops_summary:
        story.append(_section_title("Contexto operativo al momento del cierre", styles))
        oee = ops_summary.get("oee", {})
        story.append(_kpi_grid([
            ("OEE", f"{(oee.get('oee', 0) * 100):.1f}%"),
            ("Costo/kg actual", f"$ {ops_summary.get('cost_per_kg_ars', 0):,.0f}"),
            ("Margen/kg", f"$ {ops_summary.get('margin_per_kg_ars', 0):,.0f}"),
            ("Total kWh acum", f"{ops_summary.get('total_kwh', 0):.0f}"),
        ], styles))

    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(f"Generado por Yerbatera Industrial Twin · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", styles["Foot"]))

    doc.build(story)
    return out
