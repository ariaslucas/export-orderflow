#!/usr/bin/env python3
"""Signal Bot — Alertas automáticas de trading BTCUSDT via Telegram.

Lee el CSV del orderflow extractor, aplica scoring híbrido
(reglas propias + analysis del extractor), y manda notificación
a Telegram cuando detecta señales fuertes cerca de niveles clave.
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    print("Error: 'requests' no está instalado. Ejecutá: pip install requests", file=sys.stderr)
    sys.exit(1)

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UTC_MINUS_3 = timezone(timedelta(hours=-3))

log = logging.getLogger("signal_bot")


def load_config(path: str) -> dict:
    """Carga y valida config.json."""
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    required = [
        "csv_path", "poll_interval_seconds", "telegram_token", "telegram_chat_id",
        "proximidad_pct", "riesgo_usd", "min_score", "cooldown_minutos",
    ]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ValueError(f"Campos faltantes en config.json: {', '.join(missing)}")

    # Niveles: requeridos solo si no hay Notion configurado
    has_notion = cfg.get("notion_token") and cfg.get("notion_page_id")
    if not has_notion:
        for k in ("niveles_resistencia", "niveles_soporte"):
            if k not in cfg:
                raise ValueError(f"Falta '{k}' en config.json (o configurá notion_token + notion_page_id)")

    # Defaults para opcionales
    cfg.setdefault("niveles_resistencia", [])
    cfg.setdefault("niveles_soporte", [])
    cfg.setdefault("watchdog_minutos", 3)
    cfg.setdefault("sonido_enabled", True)
    cfg.setdefault("log_path", "signal_log.csv")
    cfg.setdefault("notion_cache_segundos", 60)

    return cfg


# ── NOTION LEVELS ─────────────────────────────────────────────────────────────

_notion_cache: dict = {"resistance": [], "support": [], "ts": 0.0}


def fetch_notion_levels(token: str, page_id: str, cache_seconds: int) -> tuple[list[float], list[float]]:
    """Lee niveles de resistencia y soporte desde la página Notion.

    Parsea tablas bajo headings '## Resistencias' y '## Soportes'.
    Cachea el resultado por cache_seconds para no llamar la API en cada ciclo.
    Retorna (resistencias, soportes). En caso de error retorna listas vacías.
    """
    global _notion_cache

    if time.time() - _notion_cache["ts"] < cache_seconds:
        return _notion_cache["resistance"], _notion_cache["support"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
    }

    try:
        # Obtener bloques hijos de la página
        resp = requests.get(
            f"https://api.notion.com/v1/blocks/{page_id.replace('-', '')}/children",
            headers=headers, timeout=10,
        )
        if resp.status_code != 200:
            log.warning("Notion API error %d: %s", resp.status_code, resp.text[:200])
            return _notion_cache["resistance"], _notion_cache["support"]

        blocks = resp.json().get("results", [])

        resistance: list[float] = []
        support: list[float] = []
        current_section: str | None = None

        for block in blocks:
            btype = block.get("type", "")

            # Detectar sección por heading
            if btype == "heading_2":
                text = "".join(t.get("plain_text", "") for t in block["heading_2"].get("rich_text", []))
                if "Resistencia" in text:
                    current_section = "resistance"
                elif "Soporte" in text:
                    current_section = "support"
                else:
                    current_section = None

            # Parsear tabla
            elif btype == "table" and current_section in ("resistance", "support"):
                table_id = block["id"]
                rows_resp = requests.get(
                    f"https://api.notion.com/v1/blocks/{table_id}/children",
                    headers=headers, timeout=10,
                )
                if rows_resp.status_code != 200:
                    continue

                rows = rows_resp.json().get("results", [])
                for row in rows[1:]:  # skip header row
                    cells = row.get("table_row", {}).get("cells", [])
                    if not cells:
                        continue
                    price_text = "".join(t.get("plain_text", "") for t in cells[0])
                    price_text = price_text.replace(",", "").replace(".", "").strip()
                    try:
                        price = float(price_text)
                        if price > 0:
                            if current_section == "resistance":
                                resistance.append(price)
                            else:
                                support.append(price)
                    except ValueError:
                        continue

        _notion_cache = {"resistance": resistance, "support": support, "ts": time.time()}
        log.info("Notion levels: R=%s | S=%s", resistance, support)
        return resistance, support

    except requests.RequestException as e:
        log.warning("Notion request falló: %s — usando niveles cacheados", e)
        return _notion_cache["resistance"], _notion_cache["support"]


# ── CSV PARSER ────────────────────────────────────────────────────────────────

def parse_csv(filepath: str) -> dict | None:
    """Parsea el CSV multi-sección del extractor.

    Retorna dict con keys: summary, candles, findings, overall, action.
    Retorna None si el archivo no existe o está vacío.
    """
    if not os.path.exists(filepath):
        log.warning("CSV no encontrado: %s", filepath)
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        log.warning("CSV vacío: %s", filepath)
        return None

    # Dividir en secciones por filas vacías
    sections = []
    current = []
    for row in rows:
        if not row or all(cell.strip() == "" for cell in row):
            if current:
                sections.append(current)
                current = []
        else:
            current.append(row)
    if current:
        sections.append(current)

    if len(sections) < 2:
        log.warning("CSV con formato inesperado (menos de 2 secciones)")
        return None

    result = {"summary": {}, "candles": [], "findings": [], "overall": {}, "action": {}}

    # Sección 0: Summary
    if len(sections[0]) >= 2:
        headers = sections[0][0]
        values = sections[0][1]
        result["summary"] = dict(zip(headers, values))

    # Sección 1: Candle data
    if len(sections) >= 2 and len(sections[1]) >= 2:
        candle_headers = sections[1][0]
        for row in sections[1][1:]:
            candle = {}
            for h, v in zip(candle_headers, row):
                if h == "time":
                    candle[h] = v
                else:
                    try:
                        candle[h] = float(v) if v.strip() != "" else None
                    except ValueError:
                        candle[h] = None
            result["candles"].append(candle)

    # Sección 2: Analysis findings
    if len(sections) >= 3:
        sec = sections[2]
        # Primera fila puede ser ["analysis"], segunda es header
        start = 0
        if sec[0] == ["analysis"] or (len(sec[0]) == 1 and sec[0][0].strip().lower() == "analysis"):
            start = 1
        if start < len(sec) and len(sec[start]) >= 4:
            # Header: type, severity, bias, msg
            for row in sec[start + 1:]:
                if len(row) >= 4:
                    result["findings"].append({
                        "type": row[0],
                        "severity": row[1],
                        "bias": row[2],
                        "msg": row[3],
                    })

    # Sección 3: Overall + Action
    if len(sections) >= 4:
        for row in sections[3]:
            if row and row[0] == "overall" and len(row) >= 4:
                result["overall"] = {
                    "bias": row[1],
                    "bull_score": _safe_float(row[2]),
                    "bear_score": _safe_float(row[3]),
                }
            elif row and row[0] == "action" and len(row) >= 4:
                result["action"] = {
                    "direction": row[1],
                    "confidence": row[2],
                    "narrative": row[3],
                }

    return result


def _safe_float(val) -> float | None:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_generated_timestamp(s: str) -> datetime | None:
    """Parsea '2026-04-06 18:24 UTC-3' a datetime aware."""
    try:
        # Remover sufijo de timezone
        clean = s.strip()
        if "UTC-3" in clean:
            clean = clean.replace("UTC-3", "").strip()
            return datetime.strptime(clean, "%Y-%m-%d %H:%M").replace(tzinfo=UTC_MINUS_3)
        elif "UTC" in clean:
            clean = clean.replace("UTC", "").strip()
            return datetime.strptime(clean, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        return datetime.strptime(clean, "%Y-%m-%d %H:%M").replace(tzinfo=UTC_MINUS_3)
    except (ValueError, AttributeError):
        log.warning("No se pudo parsear timestamp: %s", s)
        return None


# ── SCORING ENGINE ────────────────────────────────────────────────────────────

def compute_signal(candles: list[dict], findings: list[dict],
                   resistance: list[float], support: list[float],
                   proximity_pct: float) -> dict:
    """Scoring híbrido: reglas propias + analysis del extractor.

    Retorna dict con bear_score, bull_score, reasons, nearest levels, price.
    """
    last5 = candles[-5:]
    last = candles[-1]
    price = last["close"]

    bear_score = 0
    bull_score = 0
    bear_reasons = []
    bull_reasons = []
    # Detalle por regla: (label_bear, ok_bear, label_bull, ok_bull)
    rules_detail = []

    # ── Regla 1: Delta persistente (3+ de 5 velas) ──
    neg_count = sum(1 for c in last5 if c.get("delta") is not None and c["delta"] < 0)
    pos_count = sum(1 for c in last5 if c.get("delta") is not None and c["delta"] > 0)

    r1_bear = neg_count >= 3
    r1_bull = pos_count >= 3
    if r1_bear:
        bear_score += 1
        bear_reasons.append(f"Δ neg {neg_count}/5 velas")
    if r1_bull:
        bull_score += 1
        bull_reasons.append(f"Δ pos {pos_count}/5 velas")
    rules_detail.append((f"Δ neg {neg_count}/5", r1_bear, f"Δ pos {pos_count}/5", r1_bull))

    # ── Regla 2: OI + Delta (positioning) ──
    oi_first = last5[0].get("oi")
    oi_last = last5[-1].get("oi")
    net_delta = sum(c.get("delta", 0) or 0 for c in last5)

    r2_bear = False
    r2_bull = False
    if oi_first is not None and oi_last is not None:
        if oi_last > oi_first and net_delta < 0:
            bear_score += 1
            bear_reasons.append("OI↑ + Δ neg")
            r2_bear = True
        if oi_last < oi_first and net_delta > 0:
            bull_score += 1
            bull_reasons.append("OI↓ + Δ pos")
            r2_bull = True
    rules_detail.append(("OI↑+Δneg", r2_bear, "OI↓+Δpos", r2_bull))

    # ── Regla 3: VWAP alignment ──
    vwap = last.get("vwap")
    r3_bear = False
    r3_bull = False
    if vwap is not None and price is not None:
        if price > vwap:
            bear_score += 1
            bear_reasons.append("VWAP↑")
            r3_bear = True
        elif price < vwap:
            bull_score += 1
            bull_reasons.append("VWAP↓")
            r3_bull = True
    rules_detail.append(("P>VWAP", r3_bear, "P<VWAP", r3_bull))

    # ── Regla 4: Proximidad a nivel ──
    nearest_r = _find_nearest_level(price, resistance)
    nearest_s = _find_nearest_level(price, support)

    near_resistance = False
    near_support = False

    if nearest_r is not None and abs(price - nearest_r) / nearest_r <= proximity_pct:
        bear_score += 1
        bear_reasons.append(f"Cerca R: {nearest_r:,.0f}")
        near_resistance = True

    if nearest_s is not None and abs(price - nearest_s) / nearest_s <= proximity_pct:
        bull_score += 1
        bull_reasons.append(f"Cerca S: {nearest_s:,.0f}")
        near_support = True

    rules_detail.append(("Cerca R", near_resistance, "Cerca S", near_support))

    # ── Regla 5: Analysis confirma (≥2 findings con mismo bias) ──
    bear_findings = [f for f in findings if f.get("bias") == "bear"]
    bull_findings = [f for f in findings if f.get("bias") == "bull"]

    r5_bear = len(bear_findings) >= 2
    r5_bull = len(bull_findings) >= 2
    if r5_bear:
        bear_score += 1
        types = list(set(f["type"] for f in bear_findings))[:3]
        bear_reasons.append(f"Analysis: {' + '.join(types)}")
    if r5_bull:
        bull_score += 1
        types = list(set(f["type"] for f in bull_findings))[:3]
        bull_reasons.append(f"Analysis: {' + '.join(types)}")
    rules_detail.append(("2+bear", r5_bear, "2+bull", r5_bull))

    # ── Regla 6: Analysis tiene high severity ──
    bear_high = any(f.get("severity") == "high" and f.get("bias") == "bear" for f in findings)
    bull_high = any(f.get("severity") == "high" and f.get("bias") == "bull" for f in findings)

    if bear_high:
        bear_score += 1
        high_types = [f["type"] for f in findings if f.get("severity") == "high" and f.get("bias") == "bear"]
        bear_reasons.append(f"High: {high_types[0]}")
    if bull_high:
        bull_score += 1
        high_types = [f["type"] for f in findings if f.get("severity") == "high" and f.get("bias") == "bull"]
        bull_reasons.append(f"High: {high_types[0]}")
    rules_detail.append(("High bear", bear_high, "High bull", bull_high))

    return {
        "bear_score": bear_score,
        "bull_score": bull_score,
        "bear_reasons": bear_reasons,
        "bull_reasons": bull_reasons,
        "rules_detail": rules_detail,
        "near_resistance": near_resistance,
        "near_support": near_support,
        "nearest_resistance": nearest_r,
        "nearest_support": nearest_s,
        "price": price,
        "neg_count": neg_count,
        "pos_count": pos_count,
    }


def _find_nearest_level(price: float, levels: list[float]) -> float | None:
    """Encuentra el nivel más cercano al precio."""
    if not levels:
        return None
    return min(levels, key=lambda lv: abs(price - lv))


# ── TRIGGER + ANTI-SPAM ──────────────────────────────────────────────────────

def should_alert(signal: dict, min_score: int) -> tuple[bool, str | None]:
    """Determina si se debe enviar alerta. Retorna (should_send, direction)."""
    bear_ok = signal["bear_score"] >= min_score and signal["near_resistance"]
    bull_ok = signal["bull_score"] >= min_score and signal["near_support"]

    if bear_ok and bull_ok:
        # Priorizar mayor score; si empatan, bear
        if signal["bull_score"] > signal["bear_score"]:
            return True, "BULL"
        return True, "BEAR"
    elif bear_ok:
        return True, "BEAR"
    elif bull_ok:
        return True, "BULL"
    return False, None


def check_cooldown(level: float, last_alerts: dict, cooldown_minutes: int) -> bool:
    """Retorna True si se puede enviar (cooldown expirado o primera vez)."""
    if level not in last_alerts:
        return True
    elapsed = time.time() - last_alerts[level]
    return elapsed >= cooldown_minutes * 60


def clean_old_alerts(last_alerts: dict, cooldown_minutes: int):
    """Limpia entradas viejas del anti-spam."""
    cutoff = time.time() - cooldown_minutes * 120  # 2x cooldown
    stale = [lv for lv, ts in last_alerts.items() if ts < cutoff]
    for lv in stale:
        del last_alerts[lv]


# ── SL + POSITION SIZING ─────────────────────────────────────────────────────

def compute_sl_and_size(price: float, direction: str,
                        resistance: list[float], support: list[float],
                        risk_usd: float, trigger_level: float) -> dict:
    """Calcula SL sugerido y tamaño de posición.

    Para BEAR: SL = siguiente resistencia ARRIBA del nivel que triggereó.
    Para BULL: SL = siguiente soporte ABAJO del nivel que triggereó.
    """
    if direction == "BEAR":
        # SL = siguiente resistencia ARRIBA del trigger level
        levels_above = sorted([r for r in resistance if r > trigger_level + 1])
        if levels_above:
            sl_price = levels_above[0]
        else:
            sl_price = trigger_level * 1.005  # 0.5% arriba como fallback
    else:
        # SL = siguiente soporte ABAJO del trigger level
        levels_below = sorted([s for s in support if s < trigger_level - 1], reverse=True)
        if levels_below:
            sl_price = levels_below[0]
        else:
            sl_price = trigger_level * 0.995  # 0.5% abajo como fallback

    distance = abs(sl_price - price)
    if distance < 1:
        distance = 1  # Evitar division by zero

    contracts = int(risk_usd * 1000 / distance)

    return {
        "sl_price": sl_price,
        "distance": distance,
        "contracts": contracts,
    }


# ── MENSAJE TELEGRAM ──────────────────────────────────────────────────────────

def format_alert_message(direction: str, signal: dict, sl_info: dict,
                         risk_usd: float) -> str:
    """Construye el mensaje de alerta para Telegram."""
    price = signal["price"]
    is_bear = direction == "BEAR"
    neg = signal["neg_count"]
    pos = signal["pos_count"]

    if is_bear:
        emoji = "\U0001f534"  # 🔴
        label = "SEÑAL BAJISTA"
        score = signal["bear_score"]
        nivel = f"Resistencia: {signal['nearest_resistance']:,.0f}"
        checks_labels = [
            (signal["rules_detail"][0][1], f"Delta vendedor {neg}/5 velas"),
            (signal["rules_detail"][1][1], "OI sube + presion vendedora"),
            (signal["rules_detail"][2][1], "Precio sobre VWAP"),
            (signal["rules_detail"][3][1], f"Cerca resistencia {signal['nearest_resistance']:,.0f}"),
            (signal["rules_detail"][4][1], "Analisis confirma (2+ findings bear)"),
            (signal["rules_detail"][5][1], "Finding high severity bear"),
        ]
    else:
        emoji = "\U0001f7e2"  # 🟢
        label = "SEÑAL ALCISTA"
        score = signal["bull_score"]
        nivel = f"Soporte: {signal['nearest_support']:,.0f}"
        checks_labels = [
            (signal["rules_detail"][0][3], f"Delta comprador {pos}/5 velas"),
            (signal["rules_detail"][1][3], "OI baja + presion compradora"),
            (signal["rules_detail"][2][3], "Precio bajo VWAP"),
            (signal["rules_detail"][3][3], f"Cerca soporte {signal['nearest_support']:,.0f}"),
            (signal["rules_detail"][4][3], "Analisis confirma (2+ findings bull)"),
            (signal["rules_detail"][5][3], "Finding high severity bull"),
        ]

    check_lines = [
        f"{'  \u2705' if ok else '  \u274c'} {desc}"
        for ok, desc in checks_labels
    ]

    lines = [
        f"{emoji} {label} — Score {score}/6",
        f"Precio: {price:,.0f} | {nivel}",
        "",
        *check_lines,
        "",
        f"SL: {sl_info['sl_price']:,.0f} | Distancia: {sl_info['distance']:.0f} pts",
        f"Contratos (${risk_usd:.0f}): {sl_info['contracts']}",
        "\u2192 Abrir 1M en pantalla",
    ]

    return "\n".join(lines)


def send_telegram(token: str, chat_id: str, message: str) -> bool:
    """Envía mensaje a Telegram. Retorna True si fue exitoso."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
        }, timeout=10)
        if resp.status_code == 200:
            log.info("Telegram enviado OK")
            return True
        elif resp.status_code == 429:
            retry = resp.json().get("parameters", {}).get("retry_after", 30)
            log.warning("Telegram rate limit — retry en %ds", retry)
            return False
        else:
            log.error("Telegram error %d: %s", resp.status_code, resp.text)
            return False
    except requests.RequestException as e:
        log.error("Telegram request falló: %s", e)
        return False


# ── SIGNAL LOG ────────────────────────────────────────────────────────────────

def log_signal(log_path: str, direction: str, signal: dict, sl_info: dict):
    """Append alerta a signal_log.csv."""
    file_exists = os.path.exists(log_path)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp", "precio", "direccion", "score",
                "nivel_cercano", "sl", "distancia", "contratos",
            ])

        level = signal["nearest_resistance"] if direction == "BEAR" else signal["nearest_support"]
        score = signal["bear_score"] if direction == "BEAR" else signal["bull_score"]
        now = datetime.now(UTC_MINUS_3).strftime("%Y-%m-%d %H:%M:%S")

        writer.writerow([
            now,
            f"{signal['price']:.1f}",
            direction,
            score,
            f"{level:.0f}" if level else "",
            f"{sl_info['sl_price']:.0f}",
            f"{sl_info['distance']:.0f}",
            sl_info["contracts"],
        ])


# ── SONIDO ────────────────────────────────────────────────────────────────────

def beep(direction: str):
    """Emite sonido en Windows. Bear=800Hz, Bull=1200Hz."""
    try:
        import winsound
        freq = 800 if direction == "BEAR" else 1200
        winsound.Beep(freq, 500)
        time.sleep(0.1)
        winsound.Beep(freq, 500)
    except (ImportError, RuntimeError):
        pass  # No Windows o sin audio


# ── WATCHDOG ──────────────────────────────────────────────────────────────────

def check_watchdog(generated_ts: datetime | None, watchdog_minutes: int,
                   watchdog_sent: bool, cfg: dict, dry_run: bool) -> bool:
    """Verifica si el extractor está caído. Retorna nuevo estado de watchdog_sent."""
    if generated_ts is None:
        return watchdog_sent

    now = datetime.now(UTC_MINUS_3)
    age_minutes = (now - generated_ts).total_seconds() / 60

    if age_minutes > watchdog_minutes:
        if not watchdog_sent:
            msg = (
                f"\u26a0\ufe0f WATCHDOG: Extractor sin actualizar hace {age_minutes:.0f} min\n"
                f"\u00daltimo dato: {generated_ts.strftime('%H:%M:%S')}"
            )
            if dry_run:
                log.warning("WATCHDOG (dry-run): %s", msg)
            else:
                send_telegram(cfg["telegram_token"], cfg["telegram_chat_id"], msg)
            return True  # watchdog_sent = True
    else:
        if watchdog_sent:
            log.info("Extractor recuperado — datos frescos")
        return False  # Reset

    return watchdog_sent


# ── TEST MODE ─────────────────────────────────────────────────────────────────

def send_test_message(cfg: dict):
    """Envía mensaje de prueba a Telegram."""
    msg = (
        "\u2705 Signal Bot — Test de conexión\n"
        f"Timestamp: {datetime.now(UTC_MINUS_3).strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"CSV path: {cfg['csv_path']}\n"
        f"Resistencias: {cfg['niveles_resistencia']}\n"
        f"Soportes: {cfg['niveles_soporte']}\n"
        f"Min score: {cfg['min_score']} | Cooldown: {cfg['cooldown_minutos']}min"
    )
    ok = send_telegram(cfg["telegram_token"], cfg["telegram_chat_id"], msg)
    if ok:
        print("Test enviado OK — revisá Telegram")
    else:
        print("Error al enviar test — revisá token y chat_id", file=sys.stderr)


# ── MAIN LOOP ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Signal Bot — Alertas BTCUSDT")
    parser.add_argument("--config", default=os.path.join(SCRIPT_DIR, "config.json"),
                        help="Path a config.json")
    parser.add_argument("--test", action="store_true",
                        help="Enviar mensaje de prueba y salir")
    parser.add_argument("--dry-run", action="store_true",
                        help="Correr sin enviar a Telegram (solo consola)")
    parser.add_argument("--verbose", action="store_true",
                        help="Logging en DEBUG")
    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Config
    try:
        cfg = load_config(args.config)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        log.error("Error cargando config: %s", e)
        sys.exit(1)

    log.info("Signal Bot iniciado")
    log.info("CSV: %s", cfg["csv_path"])
    if cfg.get("notion_token") and cfg.get("notion_page_id"):
        log.info("Niveles: Notion (page %s)", cfg["notion_page_id"][:8] + "...")
    else:
        log.info("Resistencias: %s", cfg["niveles_resistencia"])
        log.info("Soportes: %s", cfg["niveles_soporte"])
    log.info("Min score: %d | Cooldown: %d min | Poll: %ds",
             cfg["min_score"], cfg["cooldown_minutos"], cfg["poll_interval_seconds"])

    if args.dry_run:
        log.info("MODO DRY-RUN — no se enviarán alertas a Telegram")

    # Test mode
    if args.test:
        send_test_message(cfg)
        return

    # Estado
    last_alerts: dict[float, float] = {}
    last_generated: str | None = None
    watchdog_sent = False

    # Resolve log_path relativo al script
    log_path = cfg["log_path"]
    if not os.path.isabs(log_path):
        log_path = os.path.join(SCRIPT_DIR, log_path)

    while True:
        try:
            # Leer + parsear CSV
            data = parse_csv(cfg["csv_path"])
            if data is None:
                log.debug("Sin datos, reintentando...")
                time.sleep(cfg["poll_interval_seconds"])
                continue

            # Verificar timestamp
            generated = data["summary"].get("generated", "")
            if generated == last_generated:
                log.debug("Datos sin cambios (generated=%s)", generated)
                # Watchdog check incluso si no hay datos nuevos
                generated_ts = parse_generated_timestamp(generated) if generated else None
                watchdog_sent = check_watchdog(
                    generated_ts, cfg.get("watchdog_minutos", 3),
                    watchdog_sent, cfg, args.dry_run,
                )
                time.sleep(cfg["poll_interval_seconds"])
                continue

            last_generated = generated
            generated_ts = parse_generated_timestamp(generated)
            log.info("Nuevos datos: %s", generated)

            # Watchdog
            watchdog_sent = check_watchdog(
                generated_ts, cfg.get("watchdog_minutos", 3),
                watchdog_sent, cfg, args.dry_run,
            )

            # Verificar suficientes velas
            candles = data["candles"]
            if len(candles) < 5:
                log.info("Solo %d velas, necesito 5+", len(candles))
                time.sleep(cfg["poll_interval_seconds"])
                continue

            # Verificar que el último candle tiene close
            if candles[-1].get("close") is None:
                log.warning("Última vela sin precio de cierre")
                time.sleep(cfg["poll_interval_seconds"])
                continue

            # Niveles: Notion si está configurado, sino config.json
            if cfg.get("notion_token") and cfg.get("notion_page_id"):
                resistance, support = fetch_notion_levels(
                    cfg["notion_token"], cfg["notion_page_id"],
                    cfg.get("notion_cache_segundos", 60),
                )
                if not resistance and not support:
                    log.warning("Notion sin niveles — usando config.json")
                    resistance = cfg["niveles_resistencia"]
                    support = cfg["niveles_soporte"]
            else:
                resistance = cfg["niveles_resistencia"]
                support = cfg["niveles_soporte"]

            # Scoring
            signal = compute_signal(
                candles,
                data["findings"],
                resistance,
                support,
                cfg["proximidad_pct"],
            )

            log.debug("Bear: %d/6 %s | Bull: %d/6 %s | Precio: %.1f",
                       signal["bear_score"], signal["bear_reasons"],
                       signal["bull_score"], signal["bull_reasons"],
                       signal["price"])

            # Trigger
            should_send, direction = should_alert(signal, cfg["min_score"])
            if not should_send:
                log.debug("Sin señal suficiente")
                time.sleep(cfg["poll_interval_seconds"])
                continue

            # Nivel que triggereó
            if direction == "BEAR":
                trigger_level = signal["nearest_resistance"]
            else:
                trigger_level = signal["nearest_support"]

            # Anti-spam
            if trigger_level is not None and not check_cooldown(
                    trigger_level, last_alerts, cfg["cooldown_minutos"]):
                log.info("Cooldown activo para nivel %.0f — suprimido", trigger_level)
                time.sleep(cfg["poll_interval_seconds"])
                continue

            # SL + sizing
            sl_info = compute_sl_and_size(
                signal["price"], direction,
                resistance, support,
                cfg["riesgo_usd"], trigger_level or signal["price"],
            )

            # Formatear mensaje
            msg = format_alert_message(direction, signal, sl_info, cfg["riesgo_usd"])

            score = signal["bear_score"] if direction == "BEAR" else signal["bull_score"]
            log.info("ALERTA %s — Score %d/6 — Precio %.0f", direction, score, signal["price"])

            if args.dry_run:
                print("\n" + "=" * 50)
                print(msg)
                print("=" * 50 + "\n")
            else:
                sent = send_telegram(cfg["telegram_token"], cfg["telegram_chat_id"], msg)
                if sent and trigger_level is not None:
                    last_alerts[trigger_level] = time.time()

            # Sonido
            if cfg.get("sonido_enabled", True):
                beep(direction)

            # Log a CSV
            log_signal(log_path, direction, signal, sl_info)

            # Limpiar anti-spam viejo
            clean_old_alerts(last_alerts, cfg["cooldown_minutos"])

        except KeyboardInterrupt:
            log.info("Signal Bot detenido por usuario")
            break
        except Exception:
            log.exception("Error en ciclo principal — continuando")

        time.sleep(cfg["poll_interval_seconds"])


if __name__ == "__main__":
    main()
