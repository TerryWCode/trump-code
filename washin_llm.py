"""Washin 統一 LLM Gateway — ClawAPI 優先，直打 Gemini fallback。

三個 Python 專案共用此模組（prnews、trump-code、jp-headline）。
在 VPS 上走 localhost:3000 打 ClawAPI（零延遲），
ClawAPI 不可用時自動 fallback 到直打 Gemini API。

用法：
    from washin_llm import call_llm
    result = call_llm("翻譯以下內容：...", strategy="fast")
    print(result["text"])
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ClawAPI 端點（同台 VPS 走 localhost）
CLAWAPI_URL = os.environ.get("CLAWAPI_URL", "http://localhost:3000")
CLAWAPI_KEY = os.environ.get("CLAWAPI_KEY", "")

# Gemini 直打 fallback
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_KEYS_EXTRA = os.environ.get("GEMINI_API_KEYS_EXTRA", "")
_GEMINI_FLASH_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
    "/models/{model}:generateContent"
)

# 熔斷器：連續 N 次 ClawAPI 失敗就暫時跳過
_claw_fail_count = 0
_claw_circuit_open_until = 0.0
_CLAW_CIRCUIT_THRESHOLD = 3
_CLAW_CIRCUIT_WAIT = 60  # 秒


def _get_gemini_keys() -> list[str]:
    """取得所有 Gemini API key。"""
    keys = [GEMINI_API_KEY] if GEMINI_API_KEY else []
    if GEMINI_API_KEYS_EXTRA:
        keys.extend(k.strip() for k in GEMINI_API_KEYS_EXTRA.split(",") if k.strip())
    return keys


_gemini_key_idx = 0


def _next_gemini_key() -> str:
    """輪流取 Gemini key。"""
    global _gemini_key_idx
    keys = _get_gemini_keys()
    if not keys:
        raise RuntimeError("沒有可用的 GEMINI_API_KEY")
    _gemini_key_idx = (_gemini_key_idx + 1) % len(keys)
    return keys[_gemini_key_idx]


def _call_clawapi(
    prompt: str,
    *,
    system: str = "",
    strategy: str = "fast",
    max_tokens: int = 2000,
    temperature: float = 0.3,
    timeout: int = 60,
) -> dict[str, Any] | None:
    """嘗試透過 ClawAPI 呼叫 LLM。失敗回傳 None。"""
    global _claw_fail_count, _claw_circuit_open_until

    # 熔斷器檢查
    if time.time() < _claw_circuit_open_until:
        return None

    try:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if CLAWAPI_KEY:
            headers["Authorization"] = f"Bearer {CLAWAPI_KEY}"

        body: dict[str, Any] = {
            "prompt": prompt,
            "strategy": strategy,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            body["system"] = system

        resp = requests.post(
            f"{CLAWAPI_URL}/api/v2/llm",
            json=body,
            headers=headers,
            timeout=timeout,
        )

        if resp.status_code == 200:
            data = resp.json()
            _claw_fail_count = 0  # 重置熔斷
            return {
                "text": data.get("text", data.get("result", "")),
                "model": data.get("model", "clawapi"),
                "source": "clawapi",
                "tokens": data.get("tokens_used", 0),
            }

        logger.warning("ClawAPI LLM %d: %s", resp.status_code, resp.text[:100])
        _claw_fail_count += 1

    except Exception as e:
        logger.warning("ClawAPI LLM 連線失敗: %s", e)
        _claw_fail_count += 1

    # 達到熔斷閾值
    if _claw_fail_count >= _CLAW_CIRCUIT_THRESHOLD:
        _claw_circuit_open_until = time.time() + _CLAW_CIRCUIT_WAIT
        logger.warning("ClawAPI 熔斷 %d 秒", _CLAW_CIRCUIT_WAIT)

    return None


def _call_gemini_direct(
    prompt: str,
    *,
    model: str = "gemini-2.5-flash",
    max_tokens: int = 2000,
    temperature: float = 0.3,
    timeout: int = 45,
) -> dict[str, Any]:
    """直打 Gemini API（fallback）。"""
    keys = _get_gemini_keys()
    if not keys:
        raise RuntimeError("沒有可用的 GEMINI_API_KEY，且 ClawAPI 不可用")

    last_error = ""
    for _ in range(len(keys)):
        key = _next_gemini_key()
        url = _GEMINI_FLASH_URL.format(model=model) + f"?key={key}"

        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }

        try:
            resp = requests.post(url, json=body, timeout=timeout)

            if resp.status_code == 429:
                logger.warning("Gemini 429，換 key 重試")
                continue

            if resp.status_code == 200:
                data = resp.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                return {
                    "text": text,
                    "model": model,
                    "source": "gemini-direct",
                    "tokens": data.get("usageMetadata", {}).get("totalTokenCount", 0),
                }

            last_error = f"HTTP {resp.status_code}: {resp.text[:100]}"
            logger.warning("Gemini 錯誤: %s", last_error)

        except Exception as e:
            last_error = str(e)
            logger.warning("Gemini 連線失敗: %s", e)

    raise RuntimeError(f"Gemini 所有 key 都失敗: {last_error}")


def call_llm(
    prompt: str,
    *,
    system: str = "",
    strategy: str = "fast",
    model: str = "gemini-2.5-flash",
    max_tokens: int = 2000,
    temperature: float = 0.3,
    timeout: int = 60,
) -> dict[str, Any]:
    """統一 LLM 呼叫入口。

    優先走 ClawAPI（同台 VPS localhost，多供應商 fallback），
    ClawAPI 不可用時 fallback 到直打 Gemini API。

    回傳：{"text": str, "model": str, "source": "clawapi"|"gemini-direct", "tokens": int}
    """
    # 第一層：ClawAPI
    result = _call_clawapi(
        prompt,
        system=system,
        strategy=strategy,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    if result and result.get("text"):
        return result

    # 第二層：Gemini 直打
    return _call_gemini_direct(
        prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=min(timeout, 45),
    )
