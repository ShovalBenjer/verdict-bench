"""Typed provider boundary. Every provider returns DecisionResult; every
parse/IO failure is recorded, never swallowed (boundary-contracts rule)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class DecisionResult:
    decision: str | None       # APPROVE | HOLD | REJECT | None
    reasoning: str | None
    confidence: float | None
    raw_output: str
    contract_ok: bool          # strict: raw strips to a single parseable {...}
    tokens_in: int | None
    tokens_out: int | None
    latency_ms: int
    error: str | None = None


VALID = {"APPROVE", "HOLD", "REJECT"}


def parse_contract(raw: str) -> tuple[str | None, str | None, float | None, bool, str | None]:
    """Strict first: whole output is one JSON object. Fallback: extract the
    first {...} block (recorded as contract violation, decision still graded)."""
    s = raw.strip()
    strict = s.startswith("{") and s.endswith("}")
    candidate = s if strict else None
    if candidate is None:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            candidate = m.group(0)
    if candidate is None:
        return None, None, None, False, "no JSON object in output"
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError as e:
        return None, None, None, False, f"JSON parse error: {e}"
    decision = obj.get("decision")
    if decision not in VALID:
        return None, obj.get("reasoning"), obj.get("confidence"), False, f"invalid decision: {decision!r}"
    conf = obj.get("confidence")
    conf = float(conf) if isinstance(conf, (int, float)) else None
    return decision, obj.get("reasoning"), conf, strict, None


def _env(name: str) -> str:
    v = os.environ.get(name, "")
    if not v:
        # .env fallback without exporting to the process environment broadly
        env_path = os.path.expanduser("~/.env")
        if os.path.exists(env_path):
            with open(env_path) as fh:
                for line in fh:
                    if line.startswith(name + "="):
                        v = line.split("=", 1)[1].strip().strip('"')
                        break
    if not v:
        raise RuntimeError(f"missing credential {name}")
    return v


def call_claude_cli(model: str, system_prompt: str, case_json: str, timeout: int = 180, retries: int = 1) -> DecisionResult:
    """Claude via the claude CLI in headless print mode (external process,
    subscription auth). --output-format json carries usage metadata."""
    t0 = time.monotonic()
    try:
        proc = subprocess.run(  # noqa: PLW1510 -- check= deliberately omitted,
            # non-zero returncode is inspected below and returned as a typed
            # DecisionResult(error=...); check=True would raise instead and
            # bypass that handling.
            # --strict-mcp-config added 2026-08-24: without it the CLI loads
            # the account's MCP connector tool definitions into the request,
            # which had grown to ~447k tokens and made EVERY call die with
            # terminal_reason=prompt_too_long (caught by the judge smoke; the
            # error rode inside an is_error envelope, rc=0). An eval
            # subprocess should be isolated from the operator's connector
            # surface regardless, so this is a correctness fix, not a
            # workaround.
            ["claude", "-p", "--model", model, "--output-format", "json",
             "--append-system-prompt", system_prompt,
             "--strict-mcp-config", "--tools", ""],
            input=f"Decide this case:\n{case_json}",
            capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode != 0 and retries > 0:
            return call_claude_cli(model, system_prompt, case_json, timeout, retries - 1)
        latency = int((time.monotonic() - t0) * 1000)
        if proc.returncode != 0:
            return DecisionResult(None, None, None,
                                  (proc.stderr + "|" + proc.stdout)[:2000], False,
                                  None, None, latency, f"claude CLI rc={proc.returncode}")
        try:
            envelope = json.loads(proc.stdout)
            text = envelope.get("result", proc.stdout)
            usage = envelope.get("usage", {}) or {}
            tin = usage.get("input_tokens")
            tout = usage.get("output_tokens")
        except json.JSONDecodeError:
            text, tin, tout = proc.stdout, None, None
        decision, reasoning, conf, ok, err = parse_contract(text)
        return DecisionResult(decision, reasoning, conf, text, ok, tin, tout, latency, err)
    except subprocess.TimeoutExpired:
        return DecisionResult(None, None, None, "", False, None, None,
                              int((time.monotonic() - t0) * 1000), "timeout")


def _openai_compat(url: str, key: str, model: str, system_prompt: str,
                   case_json: str, timeout: int = 120,
                   retries_429: int = 2) -> DecisionResult:
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Decide this case:\n{case_json}"},
        ],
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        # 429 gets a bounded retry with backoff, mirroring the retry-once
        # discipline the claude CLI path already has (added 2026-08-24 when
        # glm-5.3 rate-limited the first smoke call). Any other HTTP error
        # is returned typed, never retried blind.
        if e.code == 429 and retries_429 > 0:
            retry_after = e.headers.get("Retry-After") if e.headers else None
            try:
                delay = min(float(retry_after), 60.0) if retry_after else 10.0
            except ValueError:
                delay = 10.0
            time.sleep(delay)
            return _openai_compat(url, key, model, system_prompt, case_json,
                                  timeout, retries_429 - 1)
        return DecisionResult(None, None, None, e.read().decode()[:2000], False,
                              None, None, int((time.monotonic() - t0) * 1000), f"HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return DecisionResult(None, None, None, "", False, None, None,
                              int((time.monotonic() - t0) * 1000), str(e))
    latency = int((time.monotonic() - t0) * 1000)
    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        return DecisionResult(None, None, None, json.dumps(payload)[:2000], False,
                              None, None, latency, f"unexpected response shape: {e}")
    usage = payload.get("usage", {}) or {}
    decision, reasoning, conf, ok, err = parse_contract(text)
    return DecisionResult(decision, reasoning, conf, text, ok,
                          usage.get("prompt_tokens"), usage.get("completion_tokens"),
                          latency, err)


def call_gemini(model: str, system_prompt: str, case_json: str, timeout: int = 120) -> DecisionResult:
    key = _env("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = json.dumps({
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": f"Decide this case:\n{case_json}"}]}],
        "generationConfig": {"temperature": 0.2},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return DecisionResult(None, None, None, e.read().decode()[:2000], False,
                              None, None, int((time.monotonic() - t0) * 1000), f"HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return DecisionResult(None, None, None, "", False, None, None,
                              int((time.monotonic() - t0) * 1000), str(e))
    latency = int((time.monotonic() - t0) * 1000)
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as e:
        return DecisionResult(None, None, None, json.dumps(payload)[:2000], False,
                              None, None, latency, f"unexpected response shape: {e}")
    usage = payload.get("usageMetadata", {}) or {}
    decision, reasoning, conf, ok, err = parse_contract(text)
    return DecisionResult(decision, reasoning, conf, text, ok,
                          usage.get("promptTokenCount"), usage.get("candidatesTokenCount"),
                          latency, err)


def call_nvidia(model: str, system_prompt: str, case_json: str) -> DecisionResult:
    return _openai_compat("https://integrate.api.nvidia.com/v1/chat/completions",
                          _env("NVIDIA_API_KEY"), model, system_prompt, case_json, timeout=240)


def call_qwen(model: str, system_prompt: str, case_json: str) -> DecisionResult:
    """DashScope international, OpenAI-compatible mode. Model id verified
    against the live /models list 2026-08-24 (qwen3.8-max is the current
    flagship this key serves; the cn endpoint returns an empty list)."""
    return _openai_compat("https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
                          _env("QWEN_API_KEY"), model, system_prompt, case_json, timeout=240)


def call_zai(model: str, system_prompt: str, case_json: str) -> DecisionResult:
    """Z.AI open platform, OpenAI-compatible chat/completions. Model id
    verified against the live /models list 2026-08-24 (glm-5.3 newest)."""
    return _openai_compat("https://api.z.ai/api/paas/v4/chat/completions",
                          _env("Z_AI_KEY"), model, system_prompt, case_json, timeout=240)


PROVIDERS = {
    "claude-sonnet": lambda s, c: call_claude_cli("claude-sonnet-5", s, c),
    "claude-haiku": lambda s, c: call_claude_cli("claude-haiku-4-5-20251001", s, c),
    "gemini-flash": lambda s, c: call_gemini("gemini-2.5-flash", s, c),
    "gemini-pro": lambda s, c: call_gemini("gemini-2.5-pro", s, c),
    "llama-3.3-70b": lambda s, c: call_nvidia("meta/llama-3.3-70b-instruct", s, c),
    "qwen3.8-max": lambda s, c: call_qwen("qwen3.8-max", s, c),
    # glm-5.3 wired 2026-08-24 and immediately money-blocked on BOTH routes
    # (Z.AI error 1113 insufficient balance; DashScope free tier exhausted).
    # Kept registered so the recorded error rows stay reproducible; recharging
    # is an operator decision. Nemotron fills the current-open roster slot
    # per SPEC.md's own roster policy ("qwen3 or nemotron").
    "glm-5.3": lambda s, c: call_zai("glm-5.3", s, c),
    "nemotron-super-49b": lambda s, c: call_nvidia("nvidia/llama-3.3-nemotron-super-49b-v1", s, c),
}
