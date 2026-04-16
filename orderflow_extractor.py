"""
Order Flow Data Extractor for AI Analysis
Extracts Delta, Volume, CVD, OI, VWAP and other advanced context metrics.
Formats as structured text optimized for Claude/AI consumption.

Usage:
    python orderflow_extractor.py -s BTCUSDT -t 5m -c 20
    python orderflow_extractor.py -s ETHUSDT -t 15m -c 30 --clipboard
"""

import argparse
import csv
import requests
import sys
import time
from datetime import datetime, timezone, timedelta

# Create UTC-3 timezone for display formatting
TZ_UTC_MINUS_3 = timezone(timedelta(hours=-3))

# ─── Constants ────────────────────────────────────────────────────────────────
BASE_URL = "https://fapi.binance.com"
VALID_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
TF_TO_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000,
    "15m": 900_000, "30m": 1_800_000, "1h": 3_600_000,
    "2h": 7_200_000, "4h": 14_400_000, "1d": 86_400_000,
}
OI_PERIODS = {"5m", "15m", "30m", "1h", "2h", "4h", "1d"}


# ─── API Functions ────────────────────────────────────────────────────────────

def get_klines(symbol: str, interval: str, limit: int) -> list[dict]:
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    candles = []
    for k in data:
        candles.append({
            "open_time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": int(k[6]),
            "quote_volume": float(k[7]),
            "trades": int(k[8]),
            "taker_buy_volume": float(k[9]),
            "taker_buy_quote_volume": float(k[10]),
        })
    return candles


def get_delta_from_klines(candles: list[dict]) -> list[dict]:
    results = []
    for c in candles:
        buy_vol = c["taker_buy_volume"]
        sell_vol = c["volume"] - buy_vol
        delta = buy_vol - sell_vol
        results.append({
            "buy_vol": round(buy_vol, 4),
            "sell_vol": round(sell_vol, 4),
            "delta": round(delta, 4),
        })
    return results


def get_aggTrades_delta(symbol: str, start_time: int, end_time: int) -> dict:
    buy_vol = 0.0
    sell_vol = 0.0
    current_start = start_time
    
    while current_start < end_time:
        params = {"symbol": symbol, "startTime": current_start, "endTime": end_time, "limit": 1000}
        resp = requests.get(f"{BASE_URL}/fapi/v1/aggTrades", params=params, timeout=10)
        resp.raise_for_status()
        trades = resp.json()
        if not trades: break
            
        for t in trades:
            qty = float(t["q"])
            if t["m"]: sell_vol += qty
            else: buy_vol += qty
        
        last_ts = trades[-1]["T"]
        if last_ts >= end_time or len(trades) < 1000: break
        current_start = last_ts + 1
    
    return {"buy_vol": round(buy_vol, 4), "sell_vol": round(sell_vol, 4), "delta": round(buy_vol - sell_vol, 4)}


def get_open_interest_hist(symbol: str, period: str, limit: int) -> list[dict]:
    url = f"{BASE_URL}/futures/data/openInterestHist"
    params = {"symbol": symbol, "period": period, "limit": limit}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for d in data:
        results.append({
            "timestamp": int(d["timestamp"]),
            "oi": float(d["sumOpenInterest"]),
        })
    return results


def get_current_oi(symbol: str) -> dict:
    url = f"{BASE_URL}/fapi/v1/openInterest"
    params = {"symbol": symbol}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return {"oi": float(data["openInterest"]), "timestamp": int(data["time"])}


# ─── Data Processing ─────────────────────────────────────────────────────────

def build_orderflow_data(symbol: str, timeframe: str, num_candles: int, use_aggtrades: bool = False) -> dict:
    time_now_ms = int(time.time() * 1000)
    today_start_ms = int(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
    ms_since_midnight = time_now_ms - today_start_ms
    
    candles_since_midnight = int(ms_since_midnight / TF_TO_MS.get(timeframe, 300_000)) + 1
    limit_to_fetch = max(num_candles, candles_since_midnight)
    limit_to_fetch = min(limit_to_fetch, 1500)
    
    print(f"  Fetching {limit_to_fetch} candles to get daily VWAP/Session CVD...", file=sys.stderr)
    
    candles = get_klines(symbol, timeframe, limit_to_fetch)
    
    if use_aggtrades:
        print(f"  Computing delta from aggTrades (precise)...", file=sys.stderr)
        deltas = []
        for i, c in enumerate(candles):
            d = get_aggTrades_delta(symbol, c["open_time"], c["close_time"])
            deltas.append(d)
    else:
        print(f"  Computing delta from klines taker data...", file=sys.stderr)
        deltas = get_delta_from_klines(candles)
    
    session_cvd = 0.0
    session_vol = 0.0
    session_vol_price = 0.0
    daily_high = 0.0
    daily_low = float('inf')
    
    processed_rows = []
    
    for i, c in enumerate(candles):
        open_time = c["open_time"]
        dt_utc = datetime.fromtimestamp(open_time / 1000, tz=timezone.utc)
        
        if dt_utc.hour == 0 and dt_utc.minute == 0 and dt_utc.second == 0:
            session_cvd = 0.0
            session_vol = 0.0
            session_vol_price = 0.0
            daily_high = c["high"]
            daily_low = c["low"]
            
        daily_high = max(daily_high, c["high"])
        daily_low = min(daily_low, c["low"])
        
        delta = deltas[i]["delta"]
        session_cvd += delta
        
        typ_price = (c["high"] + c["low"] + c["close"]) / 3
        vol = c["volume"]
        
        session_vol += vol
        session_vol_price += typ_price * vol
        vwap = session_vol_price / session_vol if session_vol > 0 else typ_price
        
        buy_vol = deltas[i]["buy_vol"]
        sell_vol = deltas[i]["sell_vol"]
        buy_pct = (buy_vol / vol * 100) if vol > 0 else 50
        sell_pct = (sell_vol / vol * 100) if vol > 0 else 50
        
        processed_rows.append({
            "time_utc": dt_utc,
            "open": c["open"],
            "high": c["high"],
            "low": c["low"],
            "close": c["close"],
            "volume": vol,
            "buy_vol": buy_vol,
            "sell_vol": sell_vol,
            "buy_pct": buy_pct,
            "sell_pct": sell_pct,
            "delta": delta,
            "delta_pct": (delta / vol * 100) if vol > 0 else 0.0,
            "cvd": session_cvd,
            "vwap": vwap,
            "daily_high": daily_high,
            "daily_low": daily_low,
        })

    # Volumen relativo: vol de cada vela vs promedio de las N anteriores (N = num_candles configurado)
    lookback = num_candles
    for i in range(len(processed_rows)):
        window = processed_rows[max(0, i - lookback):i]
        if window:
            avg_vol = sum(w["volume"] for w in window) / len(window)
            processed_rows[i]["vol_rel"] = processed_rows[i]["volume"] / avg_vol if avg_vol > 0 else 1.0
        else:
            processed_rows[i]["vol_rel"] = 1.0

    final_rows = processed_rows[-num_candles:]
    
    oi_period = timeframe if timeframe in OI_PERIODS else ("5m" if timeframe in ("1m","3m") else "1h")
    oi_period_ms = TF_TO_MS.get(oi_period, 300_000)
    oi_map = {}
    try:
        print(f"  Fetching OI history ({oi_period})...", file=sys.stderr)
        oi_data = get_open_interest_hist(symbol, oi_period, min(num_candles + 5, 500))
        for oi in oi_data: oi_map[oi["timestamp"]] = oi
    except Exception as e:
        print(f"  Warning: OI failed: {e}", file=sys.stderr)

    # Fetch real-time OI and inject as the "close snapshot" of the last candle.
    # Each candle's OI delta = snapshot(close of candle) - snapshot(close of prev candle),
    # i.e. we match each candle to the snapshot at candle_open + 1 period (its close boundary).
    # For the last candle, real-time OI acts as that close snapshot.
    current_oi_data = None
    try:
        current_oi_data = get_current_oi(symbol)
    except Exception:
        pass

    if current_oi_data and final_rows:
        last_close_ts = int(final_rows[-1]["time_utc"].timestamp() * 1000) + oi_period_ms
        oi_map[last_close_ts] = {"timestamp": last_close_ts, "oi": current_oi_data["oi"]}

    for i, r in enumerate(final_rows):
        # Use the snapshot at the CLOSE of this candle (open_ts + 1 period) so that
        # oi_delta reflects activity that happened during the candle, not the previous one.
        close_ts = int(r["time_utc"].timestamp() * 1000) + oi_period_ms
        matched_oi = None
        if oi_map:
            closest_ts = min(oi_map.keys(), key=lambda t: abs(t - close_ts))
            if abs(closest_ts - close_ts) < oi_period_ms * 2:
                matched_oi = oi_map[closest_ts]
        r["oi"] = matched_oi["oi"] if matched_oi else None
        prev_oi = final_rows[i - 1].get("oi") if i > 0 else None
        r["oi_delta"] = (r["oi"] - prev_oi) if (r["oi"] is not None and prev_oi is not None) else None
        r["time"] = r["time_utc"].astimezone(TZ_UTC_MINUS_3).strftime("%H:%M" if timeframe not in ("1d",) else "%Y-%m-%d")

    current_oi = current_oi_data["oi"] if current_oi_data else None
    
    last = final_rows[-1]
    curr_price = last["close"]
    d_high = last["daily_high"]
    d_low = last["daily_low"]
    d_range = d_high - d_low
    if d_range > 0:
        pct_of_range = ((curr_price - d_low) / d_range) * 100
        dist_to_low = ((curr_price - d_low) / curr_price) * 100
        dist_to_high = ((d_high - curr_price) / curr_price) * 100
    else:
        pct_of_range = dist_to_low = dist_to_high = 0

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "num_candles": len(final_rows),
        "generated": datetime.now(TZ_UTC_MINUS_3).strftime("%Y-%m-%d %H:%M UTC-3"),
        "summary": {
            "daily_high": d_high,
            "daily_low": d_low,
            "pct_of_range": pct_of_range,
            "dist_to_high": dist_to_high,
            "dist_to_low": dist_to_low,
            "daily_vwap": last["vwap"],
            "vwap_bias": "Bullish (Above VWAP)" if curr_price > last["vwap"] else "Bearish (Below VWAP)",
            "vwap_dist_pct": ((curr_price - last["vwap"]) / last["vwap"]) * 100,
            "net_delta_session": last["cvd"],
            "session_bias": "Net Buyer" if last["cvd"] > 0 else "Net Seller",
            "current_oi": current_oi
        },
        "rows": final_rows,
    }


# ─── Formatting ──────────────────────────────────────────────────────────────

def format_number(n, decimals=1):
    if n is None: return "N/A"
    abs_n = abs(n)
    sign = "-" if n < 0 else "+" if n > 0 else ""
    if abs_n >= 1_000_000: return f"{sign}{abs_n/1_000_000:.{decimals}f}M"
    elif abs_n >= 1_000: return f"{sign}{abs_n/1_000:.{decimals}f}K"
    else: return f"{sign}{abs_n:.{decimals}f}"

def format_price(p):
    if p >= 1000: return f"{p:,.1f}"
    elif p >= 1: return f"{p:.2f}"
    else: return f"{p:.4f}"

def format_output(data: dict, analysis: dict) -> str:
    s = data["summary"]
    rows = data["rows"]
    
    lines = []
    lines.append("=" * 75)
    lines.append("ORDER FLOW ADVANCED DATA")
    lines.append("=" * 75)
    lines.append(f"Symbol: {data['symbol']} | TF: {data['timeframe']} | Candles: {data['num_candles']}")
    lines.append(f"Generated: {data['generated']}")
    lines.append("")
    
    lines.append("--- DAILY CONTEXT (Since 00:00 UTC) ---")
    lines.append(f"Daily Range:           {format_price(s['daily_low'])} - {format_price(s['daily_high'])}")
    lines.append(f"Current Structure:     Price is at {s['pct_of_range']:.1f}% of Daily Range")
    lines.append(f"Distance to Extrema:   {s['dist_to_low']:.2f}% from Low | {s['dist_to_high']:.2f}% from High")
    lines.append(f"Daily VWAP:            {format_price(s['daily_vwap'])}")
    lines.append(f"VWAP Bias:             {s['vwap_bias']} ({s['vwap_dist_pct']:+.2f}% dev)")
    lines.append(f"Session CVD:           {format_number(s['net_delta_session'])} ({s['session_bias']})")
    if s["current_oi"]:
        lines.append(f"Current OI:            {format_number(s['current_oi'])}")
    
    lines.append("")
    lines.append("--- INTRADAY DATA ---")
    
    has_oi = any(r.get("oi") is not None for r in rows)

    if has_oi:
        header = f"{'Time':<5}| {'Close':>9} | {'H/L':>15} | {'Vol':>6} | {'VRel':>4} | {'Delta':>8} | {'Δ%':>5} | {'B/S %':>9} | {'S-CVD':>8} | {'VWAP':>9} | {'OI Δ':>13}"
    else:
        header = f"{'Time':<5}| {'Close':>9} | {'H/L':>15} | {'Vol':>6} | {'VRel':>4} | {'Delta':>8} | {'Δ%':>5} | {'B/S %':>9} | {'S-CVD':>8} | {'VWAP':>9}"

    lines.append(header)
    lines.append("-" * len(header))

    for r in rows:
        vol_str = format_number(r["volume"])
        delta_str = format_number(r["delta"])
        cvd_str = format_number(r["cvd"])
        vwap_str = format_price(r["vwap"])
        bs_str = f"{r['buy_pct']:.0f}/{r['sell_pct']:.0f}"
        hl_str = f"{format_price(r['high'])}/{format_price(r['low'])}"
        vrel_str = f"{r['vol_rel']:.1f}x"
        dpct_str = f"{r['delta_pct']:+.0f}%"

        if has_oi:
            oi_delta = r.get("oi_delta")
            if oi_delta is not None and r.get("oi") and r["oi"] > 0:
                oi_pct = (oi_delta / (r["oi"] - oi_delta)) * 100 if (r["oi"] - oi_delta) != 0 else 0
                oi_delta_str = f"{format_number(oi_delta)}/{oi_pct:+.2f}%"
            else:
                oi_delta_str = "---"
            line = (f"{r['time']:<5}| {format_price(r['close']):>9} | {hl_str:>15} | {vol_str:>6} | {vrel_str:>4} | "
                    f"{delta_str:>8} | {dpct_str:>5} | {bs_str:>9} | {cvd_str:>8} | {vwap_str:>9} | {oi_delta_str:>13}")
        else:
            line = (f"{r['time']:<5}| {format_price(r['close']):>9} | {hl_str:>15} | {vol_str:>6} | {vrel_str:>4} | "
                    f"{delta_str:>8} | {dpct_str:>5} | {bs_str:>9} | {cvd_str:>8} | {vwap_str:>9}")
        lines.append(line)
    
    lines.append("")
    lines.append("--- AUTO-ANÁLISIS ---")
    
    if analysis["findings"]:
        # Group by severity
        high = [f for f in analysis["findings"] if f["severity"] == "high"]
        medium = [f for f in analysis["findings"] if f["severity"] == "medium"]
        
        if high:
            lines.append("")
            lines.append("⚠ SEÑALES FUERTES:")
            for f in high:
                icon = "🔴" if f["bias"] == "bear" else "🟢" if f["bias"] == "bull" else "🟡"
                lines.append(f"  {icon} [{f['type']}] {f['msg']}")
        
        if medium:
            lines.append("")
            lines.append("📊 CONTEXTO:")
            for f in medium:
                icon = "🔻" if f["bias"] == "bear" else "🔹" if f["bias"] == "bull" else "◽"
                lines.append(f"  {icon} [{f['type']}] {f['msg']}")
    else:
        lines.append("  Sin señales relevantes en las últimas velas.")
    
    lines.append("")
    lines.append(f"═══ SESGO GENERAL: {analysis['overall']} (Bull {analysis['bull_score']} vs Bear {analysis['bear_score']}) ═══")
    lines.append("=" * 75)
    return "\n".join(lines)


# ─── Auto-Analysis Engine ────────────────────────────────────────────────────

def auto_analyze(data: dict) -> dict:
    """Rule-based analysis engine for order flow data."""
    rows = data["rows"]
    s = data["summary"]
    findings = []
    
    if len(rows) < 5:
        return {"findings": [], "overall": "NEUTRAL", "bull_score": 0, "bear_score": 0}
    
    last = rows[-1]
    r5 = rows[-5:]
    avg_vol = sum(r["volume"] for r in rows) / len(rows)
    avg_delta = sum(abs(r["delta"]) for r in rows) / len(rows)
    
    # ── 1. DIVERGENCIA CVD vs PRECIO ──────────────────────────────────────
    prices = [r["close"] for r in r5]
    cvds = [r["cvd"] for r in r5]

    price_up = prices[-1] > prices[0]
    price_down = prices[-1] < prices[0]
    cvd_up = cvds[-1] > cvds[0]
    cvd_down = cvds[-1] < cvds[0]

    # Filtrar divergencias infladas por un spike aislado
    deltas_r5 = [abs(r["delta"]) for r in r5]
    total_abs_delta = sum(deltas_r5)
    max_single_delta = max(deltas_r5) if deltas_r5 else 0
    spike_dominated = total_abs_delta > 0 and (max_single_delta / total_abs_delta) > 0.6

    if not spike_dominated:
        if price_up and cvd_down:
            findings.append({"type": "DIVERGENCIA", "severity": "high", "bias": "bear",
                "msg": f"Precio sube pero CVD cae → compradores débiles, posible reversión bajista"})
        elif price_down and cvd_up:
            findings.append({"type": "DIVERGENCIA", "severity": "high", "bias": "bull",
                "msg": f"Precio baja pero CVD sube → vendedores débiles, posible reversión alcista"})
    
    # ── 2. OI + DELTA (positioning) ───────────────────────────────────────
    oi_vals = [r["oi"] for r in r5 if r.get("oi") is not None]
    oi_change = 0
    oi_pct = 0
    if len(oi_vals) >= 2:
        oi_change = oi_vals[-1] - oi_vals[0]
        oi_pct = (oi_change / oi_vals[0]) * 100 if oi_vals[0] else 0
        net_delta_5 = sum(r["delta"] for r in r5)
        
        if oi_change > 0 and net_delta_5 < 0:
            findings.append({"type": "OI+DELTA", "severity": "high", "bias": "bear",
                "msg": f"OI sube ({oi_pct:+.2f}%) + Delta negativo → nuevos SHORTS entrando"})
        elif oi_change > 0 and net_delta_5 > 0:
            findings.append({"type": "OI+DELTA", "severity": "medium", "bias": "bull",
                "msg": f"OI sube ({oi_pct:+.2f}%) + Delta positivo → nuevos LONGS entrando"})
        elif oi_change < 0 and net_delta_5 > 0:
            findings.append({"type": "OI+DELTA", "severity": "medium", "bias": "bull",
                "msg": f"OI baja ({oi_pct:+.2f}%) + Delta positivo → SHORTS cubriendo"})
        elif oi_change < 0 and net_delta_5 < 0:
            findings.append({"type": "OI+DELTA", "severity": "medium", "bias": "bear",
                "msg": f"OI baja ({oi_pct:+.2f}%) + Delta negativo → LONGS cerrando"})
    
    # ── 3. ABSORCIÓN ──────────────────────────────────────────────────────
    for r in r5:
        candle_range = r["high"] - r["low"]
        if candle_range == 0: continue
        body = abs(r["close"] - r["open"])
        body_pct = (body / candle_range) * 100
        
        if r["buy_pct"] > 62 and r["close"] < r["open"] and body_pct > 25:
            findings.append({"type": "ABSORCIÓN", "severity": "high", "bias": "bear",
                "msg": f"{r['time']}: Compra agresiva ({r['buy_pct']:.0f}%) pero vela ROJA → oferta absorbe demanda"})
        elif r["sell_pct"] > 62 and r["close"] > r["open"] and body_pct > 25:
            findings.append({"type": "ABSORCIÓN", "severity": "high", "bias": "bull",
                "msg": f"{r['time']}: Venta agresiva ({r['sell_pct']:.0f}%) pero vela VERDE → demanda absorbe oferta"})
    
    # ── 4. SPIKE DE VOLUMEN ───────────────────────────────────────────────
    for r in r5:
        if r["volume"] > avg_vol * 2.5:
            bias = "bull" if r["delta"] > 0 else "bear"
            findings.append({"type": "VOLUMEN", "severity": "medium", "bias": bias,
                "msg": f"{r['time']}: Spike de vol ({r['volume']/avg_vol:.1f}x prom) con delta {'positivo → impulso comprador' if r['delta'] > 0 else 'negativo → impulso vendedor'}"})
    
    # ── 5. VWAP ───────────────────────────────────────────────────────────
    vwap_dev = s["vwap_dist_pct"]
    
    if abs(vwap_dev) > 1.0:
        if vwap_dev > 0:
            findings.append({"type": "VWAP", "severity": "medium", "bias": "bear",
                "msg": f"Sobreextendido ARRIBA del VWAP ({vwap_dev:+.2f}%) → posible reversión a la media"})
        else:
            findings.append({"type": "VWAP", "severity": "medium", "bias": "bull",
                "msg": f"Sobreextendido ABAJO del VWAP ({vwap_dev:+.2f}%) → posible reversión a la media"})
    
    # VWAP reclaim / rejection en últimas 3 velas
    for i in range(max(1, len(r5)-3), len(r5)):
        r = r5[i]
        prev = r5[i-1]
        if prev["close"] < prev["vwap"] and r["close"] > r["vwap"] and r["delta"] > 0:
            findings.append({"type": "VWAP", "severity": "high", "bias": "bull",
                "msg": f"{r['time']}: Precio RECUPERA VWAP con delta positivo → señal alcista"})
        elif prev["close"] > prev["vwap"] and r["close"] < r["vwap"] and r["delta"] < 0:
            findings.append({"type": "VWAP", "severity": "high", "bias": "bear",
                "msg": f"{r['time']}: Precio PIERDE VWAP con delta negativo → señal bajista"})
    
    # ── 6. EXHAUSTIÓN ─────────────────────────────────────────────────────
    for i in range(len(r5) - 2):
        spike = r5[i]
        f1 = r5[i+1]
        f2 = r5[i+2]
        
        if abs(spike["delta"]) > avg_delta * 3:
            follow = f1["delta"] + f2["delta"]
            if spike["delta"] > 0 and follow < 0:
                findings.append({"type": "EXHAUSTIÓN", "severity": "high", "bias": "bear",
                    "msg": f"{spike['time']}: Spike alcista ({format_number(spike['delta'])}) sin continuación → exhaustión compradora"})
            elif spike["delta"] < 0 and follow > 0:
                findings.append({"type": "EXHAUSTIÓN", "severity": "high", "bias": "bull",
                    "msg": f"{spike['time']}: Spike bajista ({format_number(spike['delta'])}) sin continuación → exhaustión vendedora"})

    # Neutralizar findings de VOLUMEN del mismo candle que tuvo exhaustion
    exhaustions = [f for f in findings if f["type"] == "EXHAUSTIÓN"]
    for ex in exhaustions:
        ex_time = ex["msg"].split(":")[0]
        findings[:] = [f for f in findings
                       if not (f["type"] == "VOLUMEN" and ex_time in f["msg"])]

    # ── 7. MOMENTUM (persistencia del delta) ──────────────────────────────
    neg_count = sum(1 for r in r5 if r["delta"] < 0)
    pos_count = sum(1 for r in r5 if r["delta"] > 0)
    
    if neg_count >= 4:
        findings.append({"type": "MOMENTUM", "severity": "medium", "bias": "bear",
            "msg": f"Delta negativo en {neg_count}/5 velas → presión vendedora persistente"})
    elif pos_count >= 4:
        findings.append({"type": "MOMENTUM", "severity": "medium", "bias": "bull",
            "msg": f"Delta positivo en {pos_count}/5 velas → presión compradora persistente"})
    
    # ── 8. POSICIÓN EN RANGO DIARIO ───────────────────────────────────────
    pct = s["pct_of_range"]
    if pct > 90:
        findings.append({"type": "RANGO", "severity": "medium", "bias": "bear",
            "msg": f"Precio en {pct:.0f}% del rango diario → cerca del máximo, riesgo de entrar largo"})
    elif pct < 10:
        findings.append({"type": "RANGO", "severity": "medium", "bias": "bull",
            "msg": f"Precio en {pct:.0f}% del rango diario → cerca del mínimo, riesgo de entrar corto"})
    
    # ── 9. SQUEEZE POTENCIAL ──────────────────────────────────────────────
    if len(oi_vals) >= 2 and oi_change > 0:
        highs = [r["high"] for r in r5]
        lows = [r["low"] for r in r5]
        range_5 = max(highs) - min(lows)
        avg_candle_range = sum(r["high"] - r["low"] for r in rows) / len(rows)
        
        if range_5 < avg_candle_range * 3:
            findings.append({"type": "SQUEEZE", "severity": "high", "bias": "neutral",
                "msg": f"OI acumulándose + rango comprimido → posible squeeze inminente"})
    
    # ── 10. TRAPPED TRADERS ───────────────────────────────────────────────
    for r in r5:
        body = abs(r["close"] - r["open"])
        shadow_up = r["high"] - max(r["open"], r["close"])
        shadow_down = min(r["open"], r["close"]) - r["low"]
        
        if r["buy_pct"] > 58 and shadow_up > body * 2 and body > 0:
            findings.append({"type": "TRAMPA", "severity": "medium", "bias": "bear",
                "msg": f"{r['time']}: Longs atrapados → compra agresiva en el high, no se sostuvo"})
        elif r["sell_pct"] > 58 and shadow_down > body * 2 and body > 0:
            findings.append({"type": "TRAMPA", "severity": "medium", "bias": "bull",
                "msg": f"{r['time']}: Shorts atrapados → venta agresiva en el low, fue absorbida"})
    
    # ── SESGO GENERAL ─────────────────────────────────────────────────────
    bull = sum(2 for f in findings if f["bias"] == "bull" and f["severity"] == "high") + \
           sum(1 for f in findings if f["bias"] == "bull" and f["severity"] == "medium")
    bear = sum(2 for f in findings if f["bias"] == "bear" and f["severity"] == "high") + \
           sum(1 for f in findings if f["bias"] == "bear" and f["severity"] == "medium")
    
    diff = bull - bear
    if diff >= 4:   overall = "FUERTE ALCISTA ↑↑"
    elif diff >= 2: overall = "ALCISTA ↑"
    elif diff >= 1: overall = "LEVEMENTE ALCISTA"
    elif diff <= -4: overall = "FUERTE BAJISTA ↓↓"
    elif diff <= -2: overall = "BAJISTA ↓"
    elif diff <= -1: overall = "LEVEMENTE BAJISTA"
    else:            overall = "NEUTRAL ─"
    
    return {"findings": findings, "overall": overall, "bull_score": bull, "bear_score": bear}


def synthesize_action(analysis: dict, summary: dict) -> dict:
    """Synthesize a single actionable narrative from analysis findings."""
    bull = analysis["bull_score"]
    bear = analysis["bear_score"]
    diff = bull - bear

    # Direction
    if "ALCISTA" in analysis["overall"] or "↑" in analysis["overall"]:
        direction = "LONG"
        target_bias = "bull"
        dir_label = "ALCISTA"
    elif "BAJISTA" in analysis["overall"] or "↓" in analysis["overall"]:
        direction = "SHORT"
        target_bias = "bear"
        dir_label = "BAJISTA"
    else:
        direction = "NEUTRAL"
        target_bias = None
        dir_label = "NEUTRAL"

    # Confidence
    gap = abs(diff)
    confidence = "high" if gap >= 4 else "medium" if gap >= 2 else "low"

    # Build narrative from top findings
    if direction == "NEUTRAL" or not analysis["findings"]:
        narrative = "Sin senal dominante — esperar confluencia"
    else:
        # Prefer findings matching the dominant direction, then high severity
        matching = [f for f in analysis["findings"] if f["bias"] == target_bias]
        if not matching:
            matching = [f for f in analysis["findings"] if f["severity"] == "high"]
        # Sort: high severity first, deduplicate by type
        matching.sort(key=lambda f: 0 if f["severity"] == "high" else 1)
        seen_types = set()
        deduped = []
        for f in matching:
            if f["type"] not in seen_types:
                seen_types.add(f["type"])
                deduped.append(f)
        matching = deduped
        # Extract key phrases (after → if present)
        reasons = []
        for f in matching[:3]:
            msg = f["msg"]
            if "→" in msg:
                reasons.append(msg.split("→")[-1].strip())
            else:
                reasons.append(msg)
        narrative = f"Flujo {dir_label} — " + ", ".join(reasons)

    return {"direction": direction, "confidence": confidence, "narrative": narrative}


# ─── CSV Export ───────────────────────────────────────────────────────────────

def export_csv(data: dict, filepath: str, analysis: dict, action: dict = None):
    s = data["summary"]
    rows = data["rows"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Fila 1: cabecera del resumen diario
        writer.writerow([
            "generated", "symbol", "timeframe",
            "daily_low", "daily_high", "pct_range",
            "vwap", "vwap_bias", "vwap_dev_pct",
            "session_cvd", "current_oi"
        ])

        # Fila 2: valores del resumen diario
        writer.writerow([
            data["generated"],
            data["symbol"],
            data["timeframe"],
            round(s["daily_low"], 1),
            round(s["daily_high"], 1),
            round(s["pct_of_range"], 2),
            round(s["daily_vwap"], 1),
            "bull" if "Bullish" in s["vwap_bias"] else "bear",
            round(s["vwap_dist_pct"], 3),
            round(s["net_delta_session"], 2),
            round(s["current_oi"], 0) if s["current_oi"] else ""
        ])

        # Separador
        writer.writerow([])

        # Cabecera de velas
        writer.writerow([
            "time", "close", "high", "low", "volume",
            "delta", "delta_pct", "buy_pct", "sell_pct",
            "cvd", "vwap", "oi", "oi_delta", "vol_rel"
        ])

        # Filas de velas
        for r in rows:
            writer.writerow([
                r["time"],
                round(r["close"], 1),
                round(r["high"], 1),
                round(r["low"], 1),
                round(r["volume"], 2),
                round(r["delta"], 2),
                round(r["delta_pct"], 2),
                round(r["buy_pct"], 1),
                round(r["sell_pct"], 1),
                round(r["cvd"], 2),
                round(r["vwap"], 1),
                round(r["oi"], 0) if r.get("oi") else "",
                round(r["oi_delta"], 2) if r.get("oi_delta") is not None else "",
                round(r["vol_rel"], 2),
            ])

        # Separador
        writer.writerow([])

        # Sección de auto-análisis
        writer.writerow(["analysis"])
        writer.writerow(["type", "severity", "bias", "msg"])
        for f in analysis["findings"]:
            writer.writerow([f["type"], f["severity"], f["bias"], f["msg"]])

        # Separador
        writer.writerow([])

        # Sesgo general
        writer.writerow(["overall", analysis["overall"], analysis["bull_score"], analysis["bear_score"]])

        # Acción sintetizada
        if action:
            writer.writerow(["action", action["direction"], action["confidence"], action["narrative"]])

    print(f"  CSV guardado: {filepath}", file=sys.stderr)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Order Flow Extractor - Advanced Context Metrics")
    parser.add_argument("-s", "--symbol", default="BTCUSDT")
    parser.add_argument("-t", "--timeframe", default="5m", choices=VALID_TIMEFRAMES)
    parser.add_argument("-c", "--candles", type=int, default=20)
    parser.add_argument("--precise", action="store_true")
    parser.add_argument("--clipboard", action="store_true")
    parser.add_argument("-o", "--output", type=str, default=None)
    
    args = parser.parse_args()
    symbol = args.symbol.upper()
    
    print(f"\n🔄 Extracting advanced order flow data...\n", file=sys.stderr)
    try:
        data = build_orderflow_data(symbol, args.timeframe, args.candles, args.precise)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Compute analysis once, pass to both outputs
    analysis = auto_analyze(data)
    action = synthesize_action(analysis, data["summary"])

    output = format_output(data, analysis)
    print(output)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        csv_path = args.output.rsplit(".", 1)[0] + ".csv"
        export_csv(data, csv_path, analysis, action)

    if args.clipboard:
        try:
            import subprocess
            process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
            process.communicate(output.encode('utf-16le'))
            print("\n📋 Copied to clipboard!", file=sys.stderr)
        except Exception as e:
            print(f"\n⚠ Clipboard error: {e}", file=sys.stderr)
            
    print(f"\n✅ Done! ({len(output)} chars)", file=sys.stderr)

if __name__ == "__main__":
    main()
