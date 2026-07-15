"""Claude-agent surrogate call (Windows-native twin of TreeSearchGen's
utils/get_claude_agent.py): powershell wrapper strips the stale user-level
ANTHROPIC_API_KEY so claude.exe runs on the claude.ai subscription login.

call_agent(prompt, model="sonnet") -> reply text.
call_agent_json(...) -> dict parsed from the outermost JSON object, with a
validation-feedback retry loop. Images: reference them in the prompt as
Windows paths and tell the agent to Read them (allowed tool = Read only).
"""
import json
import re
import subprocess
import sys
import time
import uuid

from comp_paths import BRIDGE_DIR

POWERSHELL = "powershell.exe"
CLAUDE_EXE = r"C:\Users\T\.local\bin\claude.exe"
CALL_TIMEOUT_S = 900


def extract_json(text):
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e <= s:
        raise ValueError(f"no JSON object in reply: {text[:200]!r}")
    return text[s:e + 1]


def call_agent(prompt, model="sonnet", timeout=CALL_TIMEOUT_S, tag="call"):
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{tag}_{uuid.uuid4().hex[:8]}"
    pf = BRIDGE_DIR / f"{stem}.txt"
    pf.write_text(prompt, encoding="utf-8")
    ps = (
        "$OutputEncoding=[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
        "Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue; "
        "Remove-Item Env:ANTHROPIC_AUTH_TOKEN -ErrorAction SilentlyContinue; "
        f"Set-Location '{BRIDGE_DIR}'; "
        f"Get-Content -Raw -Encoding UTF8 '{pf.name}' | "
        f"& '{CLAUDE_EXE}' -p --model {model} --allowedTools Read"
    )
    t0 = time.time()
    proc = subprocess.run([POWERSHELL, "-NoProfile", "-Command", ps],
                          capture_output=True, timeout=timeout)
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    (BRIDGE_DIR / f"{stem}_reply.txt").write_text(out, encoding="utf-8")
    if proc.returncode != 0 or not out:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"bridge exit {proc.returncode}: {err[:400] or out[:400]}")
    print(f"[bridge] {tag} ok in {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
    return out


def call_agent_json(prompt, validate=None, attempts=3, **kw):
    """validate(dict) should raise with a helpful message on bad structure."""
    last = None
    p = prompt
    for i in range(1, attempts + 1):
        try:
            reply = call_agent(p, **kw)
            obj = json.loads(extract_json(reply))
            if validate:
                validate(obj)
            return obj
        except Exception as e:
            last = e
            print(f"[bridge] attempt {i} invalid: {e}", file=sys.stderr, flush=True)
            p = (f"{prompt}\n\nYour previous reply failed with this error, "
                 f"output ONLY the corrected JSON object:\n{e}")
    raise RuntimeError(f"bridge JSON failed after {attempts} attempts: {last}")
