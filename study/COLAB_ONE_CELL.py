# ===== ARL-MCP effectiveness study: ONE CELL (needs Colab secret DEEPSEEK_API_KEY) =====
MODE = "pilot"        # "pilot" = 20 stratified tasks x 6 conditions (120 calls). "main" = 150 tasks x 6 conditions (900 calls).
QWEN_MODEL = "qwen-plus"; DEEPSEEK_MODEL = "deepseek-chat"
import os, subprocess, sys, shutil
subprocess.run([sys.executable,"-m","pip","-q","install","ai-rule-learning-mcp==0.2.7","mcp<2","pandas","statsmodels"],check=True)
from google.colab import userdata
def _k(*names):
    for n in names:
        try:
            v = userdata.get(n)
            if v: return v
        except Exception: pass
    raise SystemExit(f"missing Colab secret, tried: {names} (enable Notebook access for the secret)")
os.environ["DEEPSEEK_API_KEY"] = _k("DEEPSEEK_API_KEY","DEEPSEEK","deepseek")
os.environ["QWEN_MODEL"] = QWEN_MODEL; os.environ["DEEPSEEK_MODEL"] = DEEPSEEK_MODEL
os.environ["ARL_OUT"] = f"arl_{MODE}_out"
if MODE == "pilot": shutil.rmtree(os.environ["ARL_OUT"], ignore_errors=True)
SRC = r'''
#!/usr/bin/env python3
"""ARL-MCP effectiveness study harness (DRAFT, pre-registration pending).

Subcommands
  selftest                 unit-test the compliance checkers (no network)
  build-tasks              write tasks.jsonl (150 held-out tasks, seeded)
  learn                    run the REAL tool (pinned) in a clean HOME; write rules_B0.txt / rules_B.txt
  run  --model deepseek|qwen [--limit N] [--conds A,B0,B,C,D] [--reps 1]
                           query the model; append to raw_results.jsonl (resumable)
  analyze                  per-condition rates, Wilson CIs, paired exact McNemar vs A (Holm), mixed-model if statsmodels

Keys (never printed/stored): DEEPSEEK_API_KEY, DASHSCOPE_API_KEY. Optional base-URL overrides:
DEEPSEEK_BASE_URL, DASHSCOPE_BASE_URL (default: intl endpoint).
"""
import argparse, ast, asyncio, hashlib, io, json, math, os, random, re, sys, tempfile, time, tokenize, urllib.request, urllib.error
from pathlib import Path

SEED = 20261028
OUT = Path(os.environ.get("ARL_OUT", "arl_study_out"))

# ---------------------------------------------------------------- rules (10 families)
FAMILIES = {
 "F01_no_comments": ("correction",  "Never include comments or docstrings in code."),
 "F02_type_hints":  ("preference",  "Annotate every function parameter and return type."),
 "F03_snake_case":  ("preference",  "Use snake_case for all function, parameter and variable names."),
 "F04_no_print":    ("correction",  "Never call print(); return values instead."),
 "F05_no_else":     ("correction",  "Never use the else keyword, including conditional expressions; use early returns."),
 "F06_short_funcs": ("preference",  "Keep every function at most 10 non-blank lines including the def line."),
 "F07_pathlib":     ("repeated_context", "Use pathlib.Path for file paths; never use os.path."),
 "F08_fstrings":    ("repeated_context", "Build strings with f-strings only; never use .format() or % formatting."),
 "F09_valueerror":  ("incomplete_response", "Reject invalid input by raising ValueError."),
 "F10_single_block":("correction",  "Respond with exactly one fenced python code block and no text outside it."),
}
NATURAL = {
 "F01_no_comments": "You added comments and docstrings again. I never want comments or docstrings in my code.",
 "F02_type_hints": "Your function had no type hints. I want every parameter and the return value annotated.",
 "F03_snake_case": "You used camelCase names. I want snake_case for every function, parameter and variable.",
 "F04_no_print": "You used print() again. Return the value instead of printing it.",
 "F05_no_else": "You used the else keyword again, even in a one-line conditional. I never want else; use early returns.",
 "F06_short_funcs": "That function was far too long. Keep every function to 10 non-blank lines at most.",
 "F07_pathlib": "You used os.path again. I always want pathlib.Path for file paths.",
 "F08_fstrings": "You used .format() for a string. I only want f-strings, never .format() or % formatting.",
 "F09_valueerror": "You ignored the invalid input case. Invalid input must raise ValueError.",
 "F10_single_block": "You wrote explanations around the code. Reply with exactly one python code block and nothing else.",
}
PLACEBO = ("Documentation hygiene note: archival catalogues are usually arranged by acquisition date, and "
           "reading-room staff prefer acid-free folders. Seasonal humidity logs are reviewed quarterly; "
           "cataloguers rotate between the east and west wings every few weeks. Visitors sign a register at "
           "the front desk. Lamp replacement requests go through the facilities office. ")

# ---------------------------------------------------------------- task specs
GENERIC = [
 "Write a function that returns the n-th Fibonacci number.",
 "Write a function that checks whether a string is a palindrome, ignoring case and spaces.",
 "Write a function that merges two sorted lists into one sorted list.",
 "Write a function that counts word frequencies in a text.",
 "Write a function that flattens a nested list of integers.",
 "Write a function that returns the median of a list of numbers.",
 "Write a function that removes duplicates from a list while keeping order.",
 "Write a function that rotates a list by k positions to the right.",
 "Write a function that returns the greatest common divisor of two integers.",
 "Write a function that converts a Roman numeral to an integer.",
 "Write a function that groups words by their sorted letters (anagram groups).",
 "Write a function that transposes a matrix given as a list of lists.",
 "Write a function that returns all prime numbers up to n.",
 "Write a function that finds the longest common prefix of a list of strings.",
 "Write a function that computes the running average of a list.",
 "Write a function that returns the second largest distinct number in a list.",
 "Write a function that checks whether brackets in a string are balanced.",
 "Write a function that converts a decimal number to binary text.",
 "Write a function that computes the Levenshtein distance between two strings.",
 "Write a function that returns the k most frequent items of a list.",
 "Write a function that computes the dot product of two vectors.",
 "Write a function that chunks a list into pieces of size n.",
 "Write a function that capitalises the first letter of every word in a sentence.",
 "Write a function that finds two numbers in a list that sum to a target.",
 "Write a function that returns the intersection of two lists without duplicates.",
 "Write a function that reverses the words in a sentence.",
 "Write a function that computes factorial iteratively.",
 "Write a function that checks if a number is a perfect square.",
 "Write a function that returns the digits of an integer as a list.",
 "Write a function that finds the index of the maximum value in a list.",
]
PATH = [
 "Write a function that returns the file extension of a given path string.",
 "Write a function that lists all .txt files in a directory.",
 "Write a function that reads a text file and returns its lines.",
 "Write a function that joins a base directory and a filename into a full path.",
 "Write a function that returns the parent directory name of a file path.",
 "Write a function that checks whether a file exists and is non-empty.",
 "Write a function that returns the file name without its extension.",
 "Write a function that creates a directory (including parents) if missing.",
 "Write a function that returns the total size in bytes of all files in a directory.",
 "Write a function that writes a list of strings to a file, one per line.",
 "Write a function that replaces the extension of a path with .bak.",
 "Write a function that finds the newest file in a directory.",
 "Write a function that returns the absolute path of a relative file path.",
 "Write a function that copies a file's text content to a new file.",
 "Write a function that returns all subdirectory names of a directory.",
]
FORMAT = [
 "Write a function that returns a greeting message containing a name and an age.",
 "Write a function that formats a price in dollars with two decimals, e.g. 'Total: $12.50'.",
 "Write a function that builds a log line with a timestamp string, level and message.",
 "Write a function that returns 'Item X of Y' for given integers.",
 "Write a function that formats a duration in seconds as 'HH:MM:SS'.",
 "Write a function that builds an error message including a field name and a bad value.",
 "Write a function that returns a user summary string from name, email and role.",
 "Write a function that formats a percentage with one decimal and a percent sign.",
 "Write a function that builds a SQL-like display string 'SELECT cols FROM table' from a table and columns (for display only).",
 "Write a function that renders a 2D point as '(x, y)'.",
 "Write a function that builds a filename like 'report_2024_03.csv' from a year and month.",
 "Write a function that produces a progress string like '45/100 (45%)'.",
 "Write a function that formats a temperature reading with unit, e.g. '21.5 C'.",
 "Write a function that returns a header line padded to a given width with the title centered.",
 "Write a function that builds a URL from host, port and path.",
]
VALIDATE = [
 "Write a function that computes the square root of a number and must reject negative input.",
 "Write a function that returns the average of a list and must reject an empty list.",
 "Write a function that converts a percentage string to a float and must reject malformed input.",
 "Write a function that returns the n-th element of a sequence and must reject negative n.",
 "Write a function that computes a discount price and must reject discounts outside 0-100.",
 "Write a function that parses an integer age and must reject values outside 0-150.",
 "Write a function that divides two numbers and must reject a zero divisor.",
 "Write a function that takes a month number and must reject values outside 1-12.",
 "Write a function that computes BMI and must reject non-positive height or weight.",
 "Write a function that creates a slug from a title and must reject an empty title.",
 "Write a function that converts a hex string to an integer and must reject non-hex characters.",
 "Write a function that returns the last k items of a list and must reject negative k.",
 "Write a function that computes compound interest and must reject a negative principal.",
 "Write a function that takes an RGB triple and must reject components outside 0-255.",
 "Write a function that returns the n-th prime and must reject n < 1.",
]
POOLS = {"F07_pathlib": PATH, "F08_fstrings": FORMAT, "F09_valueerror": VALIDATE}
N_PER_FAMILY = 15

def build_tasks():
    rng = random.Random(SEED)
    tasks = []
    for fam in FAMILIES:
        pool = POOLS.get(fam, GENERIC)
        specs = rng.sample(pool, N_PER_FAMILY)
        for i, s in enumerate(specs):
            tasks.append({"task_id": f"{fam}_{i:02d}", "family": fam, "spec_id": hashlib.sha1(s.encode()).hexdigest()[:8], "prompt": s})
    return tasks

# ---------------------------------------------------------------- response -> code, checkers
FENCE = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.S)

def extract(resp):
    """-> (code | None, n_blocks, prose_outside:str)"""
    blocks = FENCE.findall(resp)
    if blocks:
        prose = FENCE.sub("", resp).strip()
        return "\n".join(blocks), len(blocks), prose
    try:
        ast.parse(resp)
        return resp, 0, ""
    except SyntaxError:
        return None, 0, resp.strip()

def _funcs(tree): return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

def c_no_comments(code, tree, resp, nb, prose):
    for t in tokenize.generate_tokens(io.StringIO(code).readline):
        if t.type == tokenize.COMMENT: return False
    nodes = [tree] + [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    return not any(ast.get_docstring(n, clean=False) is not None for n in nodes)

def c_type_hints(code, tree, *_):
    fs = _funcs(tree)
    if not fs: return False
    for f in fs:
        a = f.args
        params = a.posonlyargs + a.args + a.kwonlyargs + ([a.vararg] if a.vararg else []) + ([a.kwarg] if a.kwarg else [])
        for i, p in enumerate(params):
            if p.arg in ("self", "cls") and i == 0: continue
            if p.annotation is None: return False
        if f.returns is None: return False
    return True

SNAKE = re.compile(r"^_*[a-z][a-z0-9_]*_*$|^__[a-z0-9_]+__$|^_+$")
def c_snake(code, tree, *_):
    names = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(n.name)
            a = n.args
            names += [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]
        elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store): names.append(n.id)
    return all(SNAKE.match(x) for x in names)

def c_no_print(code, tree, *_):
    return not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print" for n in ast.walk(tree))

def c_no_else(code, tree, *_):
    for t in tokenize.generate_tokens(io.StringIO(code).readline):
        if t.type == tokenize.NAME and t.string == "else": return False
    return True

def c_short(code, tree, *_):
    lines = code.splitlines()
    fs = _funcs(tree)
    if not fs: return False
    for f in fs:
        seg = lines[f.lineno - 1:f.end_lineno]
        if sum(1 for l in seg if l.strip()) > 10: return False
    return True

def c_pathlib(code, tree, *_):
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and n.attr == "path" and isinstance(n.value, ast.Name) and n.value.id == "os": return False
        if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("os.path"): return False
        if isinstance(n, ast.ImportFrom) and n.module == "os" and any(a.name == "path" for a in n.names): return False
        if isinstance(n, ast.Import) and any(a.name.startswith("os.path") for a in n.names): return False
    return True

def c_fstrings(code, tree, *_):
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "format" and isinstance(n.func.value, ast.Constant) and isinstance(n.func.value.value, str): return False
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod) and isinstance(n.left, ast.Constant) and isinstance(n.left.value, str): return False
    return True

def c_valueerror(code, tree, *_):
    for n in ast.walk(tree):
        if isinstance(n, ast.Raise) and n.exc is not None:
            e = n.exc.func if isinstance(n.exc, ast.Call) else n.exc
            if isinstance(e, ast.Name) and e.id == "ValueError": return True
    return False

def c_single_block(code, tree, resp, nb, prose):
    return nb == 1 and prose == ""

CHECKERS = {"F01_no_comments": c_no_comments, "F02_type_hints": c_type_hints, "F03_snake_case": c_snake,
            "F04_no_print": c_no_print, "F05_no_else": c_no_else, "F06_short_funcs": c_short,
            "F07_pathlib": c_pathlib, "F08_fstrings": c_fstrings, "F09_valueerror": c_valueerror,
            "F10_single_block": c_single_block}

def grade(family, resp):
    """-> ('pass'|'fail'|'invalid', reason). invalid = empty/unparseable (reported separately, sensitivity-analysed)."""
    if not resp or not resp.strip(): return "invalid", "empty"
    code, nb, prose = extract(resp)
    if code is None: return "invalid", "no_code"
    try: tree = ast.parse(code)
    except SyntaxError: return "invalid", "syntax_error"
    try: ok = CHECKERS[family](code, tree, resp, nb, prose)
    except Exception as e: return "invalid", f"checker_error:{type(e).__name__}"
    return ("pass" if ok else "fail"), ""

def side_metrics(resp):
    """Over-application / side-effect measures (computed on every valid response)."""
    code, nb, prose = extract(resp or "")
    try: tree = ast.parse(code) if code else None
    except SyntaxError: tree = None
    if tree is None: return None
    imp = any((isinstance(n, ast.ImportFrom) and n.module == "pathlib") or (isinstance(n, ast.Import) and any(a.name == "pathlib" for a in n.names)) for n in ast.walk(tree))
    return {"n_funcs": len(_funcs(tree)), "n_lines": sum(1 for l in code.splitlines() if l.strip()), "imports_pathlib": imp,
            "raises_valueerror": c_valueerror(code, tree), "prose_chars": len(prose)}

def selftest():
    G = lambda s: "```python\n" + s + "\n```"
    cases = [
     ("F01_no_comments", G("def f(x):\n    return x"), "pass"), ("F01_no_comments", G("def f(x):\n    # hi\n    return x"), "fail"),
     ("F01_no_comments", G('def f(x):\n    """doc"""\n    return x'), "fail"),
     ("F02_type_hints", G("def f(x: int) -> int:\n    return x"), "pass"), ("F02_type_hints", G("def f(x: int):\n    return x"), "fail"),
     ("F03_snake_case", G("def my_func(a_b):\n    camelVar = 1\n    return a_b"), "fail"), ("F03_snake_case", G("def my_func(a_b):\n    v = 1\n    return a_b"), "pass"),
     ("F04_no_print", G("def f():\n    print(1)"), "fail"), ("F04_no_print", G("def f():\n    return 1"), "pass"),
     ("F05_no_else", G("def f(x):\n    return 1 if x else 2"), "fail"), ("F05_no_else", G("def f(x):\n    if x:\n        return 1\n    return 2"), "pass"),
     ("F06_short_funcs", G("def f():\n" + "\n".join(f"    a{i} = {i}" for i in range(11))), "fail"), ("F06_short_funcs", G("def f():\n    return 1"), "pass"),
     ("F07_pathlib", G("import os\ndef f(p):\n    return os.path.join(p, 'a')"), "fail"), ("F07_pathlib", G("from pathlib import Path\ndef f(p):\n    return Path(p) / 'a'"), "pass"),
     ("F07_pathlib", G("from os.path import join\ndef f(p):\n    return join(p,'a')"), "fail"),
     ("F08_fstrings", G("def f(a):\n    return 'x {}'.format(a)"), "fail"), ("F08_fstrings", G("def f(a):\n    return 'x %s' % a"), "fail"), ("F08_fstrings", G("def f(a):\n    return f'x {a}'"), "pass"),
     ("F09_valueerror", G("def f(x):\n    if x < 0:\n        raise ValueError('neg')\n    return x"), "pass"), ("F09_valueerror", G("def f(x):\n    if x < 0:\n        raise TypeError('neg')\n    return x"), "fail"),
     ("F10_single_block", G("def f(): pass"), "pass"), ("F10_single_block", "Here:\n" + G("def f(): pass"), "fail"), ("F10_single_block", G("def f(): pass") + "\n" + G("def g(): pass"), "fail"),
     ("F01_no_comments", "", "invalid"), ("F01_no_comments", "I cannot do that.", "invalid"), ("F01_no_comments", G("def f(:"), "invalid"),
    ]
    bad = 0
    for fam, resp, exp in cases:
        got, _ = grade(fam, resp)
        if got != exp: bad += 1; print("FAIL", fam, repr(resp[:50]), "expected", exp, "got", got)
    t = build_tasks(); assert len(t) == 150 and len({x["task_id"] for x in t}) == 150
    print(f"selftest: {len(cases)-bad}/{len(cases)} checker cases ok; tasks={len(t)}")
    return bad == 0

# ---------------------------------------------------------------- learning with the REAL tool
def _txt(r): return "\n".join(getattr(c, "text", "") for c in r.content)

async def _learn(version_note):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    keep = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR")}  # no API keys to the tool
    res = {}
    for label, learn in (("B0", False), ("B", True), ("E", True)):
        home = tempfile.mkdtemp(prefix=f"arl_{label}_")
        env = dict(keep, HOME=home, USERPROFILE=home)
        p = StdioServerParameters(command="ai-rule-learning-mcp", args=[], env=env)
        async with stdio_client(p) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                log = []
                if learn:
                    for fam, (ft, hint) in FAMILIES.items():
                        args = {"feedback_type": ft, "description": f"user feedback: {fam}", "rule_hint": hint} if label == "B" else {"feedback_type": ft, "description": NATURAL[fam]}
                        out = _txt(await s.call_tool("record_feedback", args))
                        log.append({"family": fam, "tool_output": out})
                rules = _txt(await s.call_tool("get_guardrail_rules", {}))
        res[label] = {"rules_text": rules, "log": log}
    return res

def cmd_learn():
    OUT.mkdir(exist_ok=True)
    res = asyncio.run(_learn(""))
    for lab in ("B0", "B", "E"):
        (OUT / f"rules_{lab}.txt").write_text(res[lab]["rules_text"])
    (OUT / "learn_log_E.json").write_text(json.dumps(res["E"]["log"], ensure_ascii=False, indent=1))
    e_hits = [f for f in FAMILIES if any(w in res["E"]["rules_text"].lower() for w in {"F01_no_comments":["comment"],"F02_type_hints":["annotat","type hint"],"F03_snake_case":["snake"],"F04_no_print":["print"],"F05_no_else":["else"],"F06_short_funcs":["10"],"F07_pathlib":["pathlib"],"F08_fstrings":["f-string"],"F09_valueerror":["valueerror"],"F10_single_block":["one python code block","single"]}[f])]
    print(f"E (natural feedback, no rule_hint): {len(res['E']['rules_text'])} chars; families whose specific instruction appears in injected text: {len(e_hits)}/10 -> {e_hits}")
    (OUT / "learn_log.json").write_text(json.dumps(res["B"]["log"], ensure_ascii=False, indent=1))
    miss = [f for f, (_, h) in FAMILIES.items() if h not in res["B"]["rules_text"]]
    import importlib.metadata as im
    (OUT / "tool_version.txt").write_text(f"ai-rule-learning-mcp=={im.version('ai-rule-learning-mcp')}\nmcp=={im.version('mcp')}\n")
    print("tool version:", (OUT / "tool_version.txt").read_text().split()[0])
    print(f"B0 (defaults only): {len(res['B0']['rules_text'])} chars; B (after learning): {len(res['B']['rules_text'])} chars")
    print("learned instructions missing from injected text:", miss or "none")
    if miss: print("!! check learn_log.json: the tool may have rewritten/dropped some hints; report this as a finding.")

# ---------------------------------------------------------------- model backends (OpenAI-compatible)
BACKENDS = {
 "deepseek": dict(url=lambda: os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com") + "/chat/completions", key="DEEPSEEK_API_KEY", model=lambda: os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")),
 "qwen": dict(url=lambda: os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1") + "/chat/completions", key="DASHSCOPE_API_KEY", model=lambda: os.environ.get("QWEN_MODEL", "qwen-plus")),
}

def call_model(backend, system, user, temperature=0.0, retries=4):
    b = BACKENDS[backend]; key = (os.environ.get(b["key"]) or "").strip()
    if not key: sys.exit(f"missing env {b['key']}")
    body = json.dumps({"model": b["model"](), "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                       "temperature": temperature, "max_tokens": 2500, "stream": False}).encode()
    for i in range(retries):
        req = urllib.request.Request(b["url"](), body, {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read())
            return {"text": d["choices"][0]["message"].get("content") or "", "usage": d.get("usage", {}), "model_returned": d.get("model"), "finish": d["choices"][0].get("finish_reason")}
        except urllib.error.HTTPError as e:
            msg = e.read()[:200].decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503) and i < retries - 1: time.sleep(2 ** (i + 1)); continue
            return {"text": "", "error": f"http{e.code}:{msg.replace(key,'***')}"}
        except Exception as e:
            if i < retries - 1: time.sleep(2 ** (i + 1)); continue
            return {"text": "", "error": f"{type(e).__name__}:{str(e).replace(key,'***')[:150]}"}

BASE_SYS = "You are a coding assistant. Answer the user's request with Python code."
def system_for(cond):
    if cond == "A": return BASE_SYS
    if cond == "B0": return BASE_SYS + "\n\n" + (OUT / "rules_B0.txt").read_text()
    if cond == "B": return BASE_SYS + "\n\n" + (OUT / "rules_B.txt").read_text()
    if cond == "E": return BASE_SYS + "\n\n" + (OUT / "rules_E.txt").read_text()
    if cond == "C":  # length-matched placebo (to rules_B.txt)
        n = len((OUT / "rules_B.txt").read_text()); t = (PLACEBO * (n // len(PLACEBO) + 1))[:n]
        return BASE_SYS + "\n\n## Notes\n" + t
    if cond == "D":  # manual plain-text memory of the 10 instructions
        return BASE_SYS + "\n\n## User preferences\n" + "\n".join(f"- {h}" for _, h in FAMILIES.values())
    raise ValueError(cond)

QWEN_ENDPOINTS = ["https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "https://dashscope.aliyuncs.com/compatible-mode/v1", "https://dashscope-us.aliyuncs.com/compatible-mode/v1"]

def preflight(model):
    cands = [None] if model != "qwen" or os.environ.get("DASHSCOPE_BASE_URL") else QWEN_ENDPOINTS
    for base in cands:
        if base: os.environ["DASHSCOPE_BASE_URL"] = base
        r = call_model(model, "You are a test.", "Reply with the word OK.", retries=1)
        if not r.get("error") and r["text"].strip():
            print(f"preflight {model}: OK ({BACKENDS[model]['url']()}, model {BACKENDS[model]['model']()})"); return
        print(f"preflight {model} failed at {BACKENDS[model]['url']()}: {r.get('error')}")
    sys.exit(f"PREFLIGHT FAILED for {model}: fix key/model/endpoint before running (nothing written).")

def cmd_run(a):
    preflight(a.model)
    tasks = [json.loads(l) for l in (OUT / "tasks.jsonl").read_text().splitlines()]
    if a.limit:
        rg = random.Random(SEED); per = max(1, a.limit // len(FAMILIES)); sel = []
        for f in FAMILIES: sel += rg.sample([t for t in tasks if t["family"] == f], per)
        tasks = sel
    conds = a.conds.split(",")
    rf = OUT / "raw_results.jsonl"
    done = set()
    if rf.exists():
        for l in rf.read_text().splitlines():
            r = json.loads(l); done.add((r["model"], r["cond"], r["task_id"], r["rep"]))
    sysmap = {c: system_for(c) for c in conds}
    from concurrent.futures import ThreadPoolExecutor
    jobs = [(rep, t, c) for rep in range(a.reps) for t in tasks for c in conds if (a.model, c, t["task_id"], rep) not in done]
    def work(j):
        rep, t, c = j
        return j, call_model(a.model, sysmap[c], t["prompt"])
    n = 0
    with rf.open("a") as fh, ThreadPoolExecutor(max_workers=a.workers) as ex:
        for (rep, t, c), r in ex.map(work, jobs):
            if r.get("error"): print("API error (not saved, rerun resumes):", r["error"][:120]); continue
            status, reason = grade(t["family"], r["text"])
            rec = {"model": a.model, "model_returned": r.get("model_returned"), "cond": c, "task_id": t["task_id"], "family": t["family"], "spec_id": t["spec_id"],
                   "rep": rep, "status": status, "reason": reason, "usage": r.get("usage"), "finish": r.get("finish"), "response": r["text"], "ts": time.time(),
                   "system_sha1": hashlib.sha1(sysmap[c].encode()).hexdigest()[:10], "side": side_metrics(r["text"])}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n"); fh.flush(); n += 1
            if n % 50 == 0: print(f"{n}/{len(jobs)} calls", flush=True)
    print(f"done, {n} new calls -> {rf}")

# ---------------------------------------------------------------- analysis
def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"),) * 2
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d, (c + m) / d

def mcnemar_exact(b, c):
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)

def cmd_analyze():
    rows = [json.loads(l) for l in (OUT / "raw_results.jsonl").read_text().splitlines()]
    models = sorted({r["model"] for r in rows}); conds = sorted({r["cond"] for r in rows})
    report = []
    for m in models:
        R = [r for r in rows if r["model"] == m and r["rep"] == 0]
        print(f"\n=== {m} ===  (rep 0 only; invalid reported, excluded from primary; sensitivity = invalid counted as fail)")
        by = {}
        for r in R: by.setdefault(r["cond"], {})[r["task_id"]] = r["status"]
        for c in conds:
            d = by.get(c, {}); n_inv = sum(v == "invalid" for v in d.values()); v = [x for x in d.values() if x != "invalid"]
            k = sum(x == "pass" for x in v); lo, hi = wilson(k, len(v))
            sens = sum(x == "pass" for x in d.values()) / max(1, len(d))
            print(f"  {c:3s} pass {k}/{len(v)} = {k/max(1,len(v)):.3f} [{lo:.3f},{hi:.3f}]  invalid={n_inv}  sens(inv=fail)={sens:.3f}")
        tests = []
        for c in conds:
            if c == "A" or "A" not in by or c not in by: continue
            ids = [t for t in by["A"] if t in by[c] and by["A"][t] != "invalid" and by[c][t] != "invalid"]
            b = sum(by["A"][t] == "fail" and by[c][t] == "pass" for t in ids); cc = sum(by["A"][t] == "pass" and by[c][t] == "fail" for t in ids)
            tests.append((c, b, cc, len(ids), mcnemar_exact(b, cc)))
        order = sorted(range(len(tests)), key=lambda i: tests[i][4])
        holm = {}; run = 0.0
        for rank, i in enumerate(order):
            run = max(run, min(1.0, tests[i][4] * (len(tests) - rank))); holm[i] = run
        for i, (c, b, cc, n, p) in enumerate(tests):
            print(f"  {c} vs A: fixed={b} broken={cc} paired n={n}  exact McNemar p={p:.4g}  Holm p={holm[i]:.4g}")
        fam = {}
        for r in R:
            if r["status"] != "invalid": fam.setdefault((r["family"], r["cond"]), []).append(r["status"] == "pass")
        print("  per-family pass rate:")
        for f in FAMILIES:
            print("   ", f, "  ".join(f"{c}={sum(fam.get((f,c),[]))}/{len(fam.get((f,c),[]))}" for c in conds))
    for m in models:
        print(f"\n--- {m}: over-application on tasks where the rule is NOT the target (valid responses, rep 0) ---")
        for c in conds:
            rr = [r for r in rows if r["model"] == m and r["cond"] == c and r["rep"] == 0 and r.get("side")]
            nonp = [r for r in rr if r["family"] != "F07_pathlib"]; nonv = [r for r in rr if r["family"] != "F09_valueerror"]
            if rr: print(f"  {c:3s} pathlib imported (non-F07): {sum(r['side']['imports_pathlib'] for r in nonp)}/{len(nonp)}  ValueError raised (non-F09): {sum(r['side']['raises_valueerror'] for r in nonv)}/{len(nonv)}  mean funcs {sum(r['side']['n_funcs'] for r in rr)/len(rr):.2f}  mean lines {sum(r['side']['n_lines'] for r in rr)/len(rr):.1f}")
    try:
        import pandas as pd, statsmodels.formula.api as smf
        df = pd.DataFrame([{k: r[k] for k in ("model", "cond", "task_id", "spec_id")} | {"y": int(r["status"] == "pass")} for r in rows if r["status"] != "invalid" and r["rep"] == 0])
        print("\nMixed-effects (variance-component logit, spec_id random intercept) — exploratory; check convergence.")
        df["cond"] = pd.Categorical(df["cond"], categories=["A"] + [c for c in sorted(df["cond"].unique()) if c != "A"])
        md = smf.logit("y ~ C(cond) + C(model)", df).fit(disp=0, cov_type="cluster", cov_kwds={"groups": df["spec_id"].astype("category").cat.codes})
        print(md.summary().tables[1])
    except Exception as e:
        print("\n(mixed/cluster model skipped:", type(e).__name__, ")")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    for n in ("selftest", "build-tasks", "learn", "analyze"): sp.add_parser(n)
    r = sp.add_parser("run"); r.add_argument("--model", required=True, choices=list(BACKENDS)); r.add_argument("--limit", type=int, default=0)
    r.add_argument("--conds", default="A,B0,B,C,D,E"); r.add_argument("--reps", type=int, default=1); r.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(); OUT.mkdir(exist_ok=True)
    if a.cmd == "selftest": sys.exit(0 if selftest() else 1)
    elif a.cmd == "build-tasks":
        t = build_tasks(); (OUT / "tasks.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in t)); print(len(t), "tasks ->", OUT / "tasks.jsonl")
    elif a.cmd == "learn": cmd_learn()
    elif a.cmd == "run": cmd_run(a)
    elif a.cmd == "analyze": cmd_analyze()
'''
open("arl_study.py","w").write(SRC.lstrip("\n"))
def sh(*a):
    print("$ arl_study.py", *a, flush=True); r = subprocess.run([sys.executable,"-u","arl_study.py",*a],capture_output=True,text=True); print(r.stdout[-5000:]); print(r.stderr[-1500:]); 
    if r.returncode: raise SystemExit(f"step failed: {a}")
sh("selftest"); sh("build-tasks"); sh("learn")
lim = ["--limit","20"] if MODE=="pilot" else []
sh("run","--model","deepseek",*lim)
sh("analyze")
shutil.make_archive(f"arl_{MODE}_results","zip",os.environ["ARL_OUT"])
print(f"\nDONE -> arl_{MODE}_results.zip (download from the Files pane). Paste the analyze output above to Claude.")
