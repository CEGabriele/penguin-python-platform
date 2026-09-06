try {
  importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.2/full/pyodide.js");
} catch (e) {
  self.postMessage({
    type: "error",
    error: "importScripts failed: " + e.message,
  });
}

let pyodide = null;
let frameTimer = null;
let pygameLoaded = false;
let lastProjectFiles = {};
let pyodideReady = false

const _origPostMessage = self.postMessage.bind(self);
self.safePost = (msg) => {
  try {
    _origPostMessage({
      type: msg.type || "stdout",
      data: msg.data ? String(msg.data) : "",
      prompt: msg.prompt ? String(msg.prompt) : "",
      method: msg.method,
      args: msg.args,
      error: msg.error ? String(msg.error) : undefined,
    });
  } catch (err) {
    _origPostMessage({ type: "stdout", data: `[safePost error: ${err}]` });
  }
};

// ---------------- PYTHON BOOTSTRAP ----------------
const PY_BOOTSTRAP = `
import sys, js, builtins, asyncio, inspect

async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value

def _safe_str(obj):
    try: return str(obj)
    except Exception as e: return f"[unprintable: {e}]"

def _send_stdout(msg: str):
    try:
        js.safePost(js.Object.fromEntries([
            ["type", "stdout"], ["data", msg]
        ]))
    except Exception: pass

class ConsoleIO:
    def write(self, s): _send_stdout(str(s))
    def flush(self): pass

def _print_bridge(*args, **kwargs):
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\\n")
    msg = sep.join(_safe_str(a) for a in args) + end
    _send_stdout(msg)

builtins.print = _print_bridge
sys.stdout = sys.stderr = ConsoleIO()

_input_future = None

async def input(prompt=""):
    global _input_future
    js.safePost(js.Object.fromEntries([
        ["type", "input_request"],
        ["prompt", _safe_str(prompt)]
    ]))
    loop = asyncio.get_event_loop()
    _input_future = loop.create_future()
    return await _input_future

def _input_response(s):
    global _input_future
    if _input_future and not _input_future.done():
        _input_future.set_result(_safe_str(s))
        _input_future = None

def _input_abort():
    global _input_future
    if _input_future and not _input_future.done():
        _input_future.set_exception(asyncio.CancelledError("Input aborted"))
        _input_future = None
builtins.input = input 
`;

// ---------------- AUTO ASYNC WRAPPER ----------------
function autoWrapAsync(code) {
  code = code.replace(/\r\n/g, "\n");
  let lines = code.split("\n").map(line => {
    if (/^\s*def\s+/.test(line)) return line;
    return line.replace(/\binput\s*\(/g, "await input(");
  });

  const defRx = /^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(.*\)\s*:\s*$/;
  const funcs = [];
  const indent = (l) => (l.match(/^\s*/)||[""])[0].length;
  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].match(defRx);
    if (!match) continue;
    const name = match[1];
    const baseIndent = indent(lines[i]);
    let j = i + 1;
    while (j < lines.length) {
      const l = lines[j];
      if (l.trim() && indent(l) <= baseIndent) break;
      j++;
    }
    funcs.push({ name, start: i, end: j });
  }

  const asyncFuncs = new Set();
  for (const f of funcs) {
    const body = lines.slice(f.start + 1, f.end).join("\n");
    if (/\bawait\b/.test(body)) asyncFuncs.add(f.name);
  }

  let changed = true;
  while (changed) {
    changed = false;
    for (const f of funcs) {
      if (asyncFuncs.has(f.name)) continue;
      const body = lines.slice(f.start + 1, f.end).join("\n");
      for (const callee of asyncFuncs) {
        const callRx = new RegExp(`\\b${callee}\\s*\\(`);
        if (callRx.test(body)) { asyncFuncs.add(f.name); changed = true; break; }
      }
    }
  }

  for (const f of funcs)
    if (asyncFuncs.has(f.name))
      lines[f.start] = lines[f.start].replace(/^(\s*)def(\s+)/, "$1async def$2");

  if (asyncFuncs.size > 0) {
    const asyncNames = Array.from(asyncFuncs);
    const callRx = new RegExp(`\\b(${asyncNames.join("|")})\\s*\\(`, "g");
    lines = lines.map(line => {
      if (/^\s*(async\s+)?def\s+/.test(line)) return line;
      if (/\bawait\s+/.test(line)) return line;
      return line.replace(callRx, (match, name) => `await ${name}(`);
    });
  }

  // Handles indirect async calls like:
  lines = lines.map(line => {
    if (/^\s*(async\s+)?def\s+/.test(line)) return line;
    if (/\bawait\s+/.test(line)) return line;
    if (line.trim().startsWith("#")) return line;

    return line.replace(
      /^(\s*)action\s*\(\s*\)\s*$/,
      "$1await _maybe_await(action())"
    );
  });
    return `import asyncio\n${lines.join("\n")}`;;
  }

// ---------------- LOAD PYODIDE ----------------
async function ensurePyodide() {
  if (!pyodide) {

  pyodide = await loadPyodide({
    indexURL: "https://cdn.jsdelivr.net/pyodide/v0.27.2/full/"
  });
  await pyodide.runPythonAsync(PY_BOOTSTRAP);    
  pyodideReady = true;
  safePost({ type: "ready" });
  }
}

// ---------------- MESSAGE HANDLER ----------------
self.onmessage = async (event) => {
  const { type, code, value, usesPygame, usesTurtle, files, entry } = event.data || {};
  try {
    if (type === "input_response") {
      await ensurePyodide();
    
      const inputResponse = pyodide.globals.get("_input_response");
      inputResponse(String(value));
    
      return;
    }

    if (type === 'input_abort') {
      await ensurePyodide();

      const inputAbort = pyodide.globals.get("_input_abort");
      inputAbort();
    }
    
    if (type === "run_project") {
      await ensurePyodide();

      if (usesPygame && !pygameLoaded) {
        await pyodide.loadPackage("pygame-ce");
        pygameLoaded = true;
      }
      
      const projectFiles = files || {};
      const entryFile = entry || "main.py";
      
      try {
        for (const [path, content] of Object.entries(projectFiles)) {
          if (lastProjectFiles[path] !== content) {
            pyodide.FS.writeFile(path, content || "");
          }
        }
      
        for (const oldPath of Object.keys(lastProjectFiles)) {
          if (!(oldPath in projectFiles)) {
            try { pyodide.FS.unlink(oldPath); } catch {}
          }
        }
      
        lastProjectFiles = { ...projectFiles };      
        // determine module name
        const moduleName = entryFile.replace(".py", "");
    
        // run the entry module
        const entryCode = projectFiles[entryFile] || "";
        const wrappedCode = autoWrapAsync(entryCode);

        await pyodide.runPythonAsync(wrappedCode);
        
    
      } catch (e) {
        safePost({ type: "error", error: "[Python error] " + e.toString() });
      }
    
      safePost({ type: "done" });
      return;
    }
  } catch (err) {
    safePost({ type: "error", error: err?.toString?.() || String(err) });
  }
};