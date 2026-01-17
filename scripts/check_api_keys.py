#!/usr/bin/env python3
"""
Check Gemini API keys health without printing full secrets.

Default behavior:
- Loads API keys from SQLite DB (t_settings.API_KEYS).
- Calls GET /v1beta/models?key=... to validate each key.
- Prints only a summary and masked identifiers (last 4 chars).

This script does NOT delete or mutate keys unless you add that behavior yourself.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse, urlunparse

import aiohttp


GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


APIKeyData = Union[str, Dict[str, Any]]


@dataclass(frozen=True)
class KeyResult:
    index: int
    key_last4: str
    status: str
    http_status: Optional[int] = None
    reason: Optional[str] = None
    message: Optional[str] = None


def _mask_last4(key: str) -> str:
    key = key or ""
    return key[-4:] if len(key) >= 4 else key


def _extract_key_and_proxy_port(key_data: APIKeyData) -> Tuple[str, Optional[int]]:
    if isinstance(key_data, str):
        return key_data, None
    api_key = str(key_data.get("key", "") or "")
    proxy_port = key_data.get("proxy_port")
    try:
        proxy_port_int = int(proxy_port) if proxy_port is not None else None
    except (TypeError, ValueError):
        proxy_port_int = None
    return api_key, proxy_port_int


def _build_proxy_url(base: str, proxy_port: Optional[int]) -> Optional[str]:
    if not proxy_port:
        return None
    base = (base or "").strip()
    if not base:
        return None

    if "{port}" in base:
        return base.replace("{port}", str(proxy_port))

    parsed = urlparse(base)
    if not parsed.scheme:
        # If user provided host:port without scheme, assume http.
        parsed = urlparse("http://" + base)

    # If base already has a port, replace it; otherwise, set it.
    netloc = parsed.netloc
    if "@" in netloc:
        auth, hostport = netloc.rsplit("@", 1)
    else:
        auth, hostport = None, netloc

    if ":" in hostport:
        host = hostport.split(":", 1)[0]
    else:
        host = hostport

    new_hostport = f"{host}:{proxy_port}"
    new_netloc = f"{auth}@{new_hostport}" if auth else new_hostport

    return urlunparse(parsed._replace(netloc=new_netloc))


def _parse_error_reason_and_message(body_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Best-effort extraction of a stable 'reason' from Google-style error payloads.
    """
    if not body_text:
        return None, None

    try:
        body = json.loads(body_text)
    except Exception:
        lowered = body_text.lower()
        if "consumer_suspended" in lowered or "suspended" in lowered:
            return "CONSUMER_SUSPENDED", body_text[:200]
        if "api key not valid" in lowered or "api_key_invalid" in lowered:
            return "API_KEY_INVALID", body_text[:200]
        return None, body_text[:200]

    error = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return None, (body_text[:200] if body_text else None)

    message = error.get("message")
    status = error.get("status")

    reason: Optional[str] = None
    details = error.get("details")
    if isinstance(details, list):
        for detail in details:
            if not isinstance(detail, dict):
                continue
            # Common pattern: ErrorInfo
            if isinstance(detail.get("reason"), str):
                reason = detail["reason"]
                break
            # Some responses put reason under "errorInfo"
            error_info = detail.get("errorInfo")
            if isinstance(error_info, dict) and isinstance(error_info.get("reason"), str):
                reason = error_info["reason"]
                break

    # Fallback heuristics
    msg_low = str(message or "").lower()
    if not reason:
        if "consumer_suspended" in msg_low or "suspended" in msg_low:
            reason = "CONSUMER_SUSPENDED"
        elif "api key not valid" in msg_low or "api_key_invalid" in msg_low:
            reason = "API_KEY_INVALID"
        elif isinstance(status, str) and status:
            reason = status

    return reason, (str(message)[:200] if message else None)


def classify_result(http_status: int, reason: Optional[str], message: Optional[str]) -> str:
    if http_status == 200:
        return "valid"
    if http_status == 429:
        return "rate_limited"
    if http_status in (401,):
        return "invalid"
    if http_status == 403:
        reason_upper = (reason or "").upper()
        msg_low = (message or "").lower()
        if "CONSUMER_SUSPENDED" in reason_upper or "consumer_suspended" in msg_low:
            return "suspended"
        if "API_KEY_INVALID" in reason_upper or "api key not valid" in msg_low:
            return "invalid"
        if "SERVICE_DISABLED" in reason_upper:
            return "service_disabled"
        return "forbidden"
    if 500 <= http_status <= 599:
        return "server_error"
    return f"http_{http_status}"


def load_api_keys_from_db(db_path: str) -> List[APIKeyData]:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM t_settings WHERE key = 'API_KEYS'")
        row = cur.fetchone()
        if not row or not row[0]:
            return []
        return json.loads(row[0])
    finally:
        conn.close()


def load_api_keys_from_env(env_path: str) -> List[APIKeyData]:
    if not os.path.exists(env_path):
        return []
    api_keys_raw: Optional[str] = None
    with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("API_KEYS="):
                api_keys_raw = s.split("=", 1)[1].strip()
                break
    if api_keys_raw is None:
        return []
    if (api_keys_raw.startswith('"') and api_keys_raw.endswith('"')) or (
        api_keys_raw.startswith("'") and api_keys_raw.endswith("'")
    ):
        api_keys_raw = api_keys_raw[1:-1]
    return json.loads(api_keys_raw)


async def check_one(
    session: aiohttp.ClientSession,
    index: int,
    key_data: APIKeyData,
    proxy_base_url: str,
    timeout_s: float,
) -> KeyResult:
    api_key, proxy_port = _extract_key_and_proxy_port(key_data)
    key_last4 = _mask_last4(api_key)
    proxy_url = _build_proxy_url(proxy_base_url, proxy_port)

    url = f"{GEMINI_API_BASE}/models"
    params = {"key": api_key}

    try:
        timeout = aiohttp.ClientTimeout(total=timeout_s)
        async with session.get(url, params=params, proxy=proxy_url, timeout=timeout) as resp:
            body_text = await resp.text()
            reason, message = _parse_error_reason_and_message(body_text)
            status = classify_result(resp.status, reason, message)
            return KeyResult(
                index=index,
                key_last4=key_last4,
                status=status,
                http_status=resp.status,
                reason=reason,
                message=message,
            )
    except asyncio.TimeoutError:
        return KeyResult(index=index, key_last4=key_last4, status="timeout")
    except Exception as e:
        return KeyResult(index=index, key_last4=key_last4, status="error", message=str(e)[:200])


async def check_all(
    api_keys: List[APIKeyData],
    concurrency: int,
    proxy_base_url: str,
    timeout_s: float,
) -> List[KeyResult]:
    connector = aiohttp.TCPConnector(limit=concurrency, limit_per_host=concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        semaphore = asyncio.Semaphore(concurrency)

        async def run_one(i: int, kd: APIKeyData) -> KeyResult:
            async with semaphore:
                return await check_one(
                    session=session,
                    index=i,
                    key_data=kd,
                    proxy_base_url=proxy_base_url,
                    timeout_s=timeout_s,
                )

        tasks = [run_one(i, kd) for i, kd in enumerate(api_keys)]
        return await asyncio.gather(*tasks)


def _summarize(results: List[KeyResult]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Gemini API keys (safe output).")
    parser.add_argument("--source", choices=["db", "env"], default="db")
    parser.add_argument("--db-path", default="data/gemini_balance.db")
    parser.add_argument("--env-path", default=".env")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--output", default="")
    parser.add_argument("--print-banned", action="store_true", help="Print suspended/invalid/forbidden keys (masked).")

    args = parser.parse_args()

    if args.source == "db":
        api_keys = load_api_keys_from_db(args.db_path)
    else:
        api_keys = load_api_keys_from_env(args.env_path)

    if not api_keys:
        print("No API_KEYS found.")
        return 2

    proxy_base_url = os.getenv("BASE_PROXY_URL", "")

    started = datetime.now(timezone.utc).isoformat()
    results = asyncio.run(
        check_all(
            api_keys=api_keys,
            concurrency=max(1, args.concurrency),
            proxy_base_url=proxy_base_url,
            timeout_s=max(1.0, args.timeout),
        )
    )
    counts = _summarize(results)

    print(f"Checked {len(results)} keys.")
    print("Counts:", json.dumps(counts, ensure_ascii=False))

    banned_statuses = {"suspended", "invalid", "forbidden", "service_disabled"}
    banned = [r for r in results if r.status in banned_statuses]

    if args.print_banned and banned:
        for r in banned:
            extra = f" reason={r.reason}" if r.reason else ""
            print(f"banned index={r.index} last4={r.key_last4} status={r.status}{extra}")

    if args.output:
        report = {
            "checked_at": started,
            "source": args.source,
            "total": len(results),
            "counts": counts,
            "banned_total": len(banned),
            "results": [asdict(r) for r in results],
        }
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Wrote report: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

