// --- OPTIONAL: turtle emulation module (same one you use in main editor) ---
import turtleModule from './turtle.js';

let PYODIDE_SINGLETON = null;

async function ensurePyodide() {
  if (!PYODIDE_SINGLETON) {
    PYODIDE_SINGLETON = await loadPyodide();
    try { await PYODIDE_SINGLETON.loadPackage('micropip'); } catch {}
    
    await PYODIDE_SINGLETON.runPythonAsync(`
import sys, js, asyncio
class _MiniIO:
    def write(self, s):
        try: js._mini_console_write(s)
        except Exception: pass
    def flush(self): pass
sys.stdout = sys.stderr = _MiniIO()
    `);
  }
  return PYODIDE_SINGLETON;
}

// This will be set before each run to route output to the correct console
window._mini_console_write = (s) => {};


function autoWrapAsync(code) {
  if (code.includes("async def __main__")) return code;

  let transformed = code.replace(/\binput\s*\(/g, "await input(");
  let lines = transformed.split("\n").map(line => "    " + line); // (fixed your stray 'a' typo)

  const loopRegex = /^\s*(for|while)\b.*:\s*$/;
  const newLines = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    newLines.push(line);
    if (loopRegex.test(line)) {
      const indent = (line.match(/^\s*/)?.[0] || "") + "    ";
      newLines.push(`${indent}await asyncio.sleep(0)`);
    }
  }
  return `import asyncio\nasync def __main__():\n${newLines.join("\n")}\n\nawait __main__()`;
}

function consoleWrite(qid, s) {
  const div = document.getElementById(`console-q${qid}`);
  if (!div) return;
  div.innerHTML += String(s ?? '').replace(/\n/g, '<br>');
  div.scrollTop = div.scrollHeight;
}

function ensureTurtleCanvas(qid) {
  const container = document.getElementById(`graphics-container-q${qid}`);
  if (!container) return null;
  let canvas = document.getElementById(`turtle-canvas-q${qid}`);
  if (!canvas) {
    canvas = document.createElement('canvas');
    canvas.id = `turtle-canvas-q${qid}`;
    canvas.width = 640;
    canvas.height = 480;
    canvas.style.border = '1px solid #444';
    canvas.style.display = 'none';
    container.appendChild(canvas);
  }
  return canvas;
}


async function runMini(qid) {
  const editor = window.__miniEditors?.get(String(qid));
  if (!editor) return;

  const status = document.getElementById(`status-q${qid}`);
  const consoleBox = document.getElementById(`console-q${qid}`);
  const gfxContainer = document.getElementById(`graphics-container-q${qid}`);
  const pygameCanvas = document.getElementById(`graphics-canvas-q${qid}`);
  const turtleCanvas = ensureTurtleCanvas(qid);

  if (consoleBox) consoleBox.innerHTML = '';
  if (status) status.textContent = 'Running…';

  const py = await ensurePyodide();

  // Determine imports
  const rawCode = editor.getValue();
  const usesPygame = /\bimport\s+pygame\b/.test(rawCode);
  const usesTurtle = /\bimport\s+turtle\b|\bfrom\s+turtle\s+import\b/.test(rawCode);

  // Show/Hide graphics area
  if (gfxContainer) {
    const show = usesPygame || usesTurtle;
    gfxContainer.style.display = show ? 'block' : 'none';
    if (pygameCanvas) pygameCanvas.style.display = usesPygame ? 'inline-block' : 'none';
    if (turtleCanvas) turtleCanvas.style.display = usesTurtle ? 'inline-block' : 'none';
  }

  // pygame setup (per mini)
  if (usesPygame && pygameCanvas) {
    try { await py.loadPackage('pygame-ce'); } catch {}
    window.Module = py._module;            // let SDL target this canvas
    Module.canvas = pygameCanvas;
    pygameCanvas.style.background = '#111';
    // prevent stealing focus
    pygameCanvas.setAttribute('tabindex', '-1');
    pygameCanvas.addEventListener('focus', (e) => e.preventDefault());
  }

  // turtle setup (per mini)
  if (usesTurtle && turtleCanvas) {
    py.registerJsModule('turtle', turtleModule);
    turtleModule.setup({
      canvas: turtleCanvas,
      width: 640, height: 480, bgcolor: 'white',
    });
  }

  window._mini_console_write = (s) => consoleWrite(qid, s);
  try {
    await py.runPythonAsync(autoWrapAsync(rawCode));
    if (status) status.textContent = 'Done ✓';
  } catch (err) {
    consoleWrite(qid, `<span style="color:#f55;">${err}</span>\n`);
    if (status) status.textContent = 'Error';
  } finally {
    window._mini_console_write = () => {};
  }
}

async function stopMini(qid) {
  // Try to quit pygame if that mini used it most recently (best-effort)
  if (PYODIDE_SINGLETON) {
    try {
      await PYODIDE_SINGLETON.runPythonAsync(`
import importlib
spec = importlib.util.find_spec("pygame")
if spec is not None:
    import pygame
    if pygame.get_init():
        try:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        except Exception:
            pass
`);
      await new Promise(r => setTimeout(r, 120));
      await PYODIDE_SINGLETON.runPythonAsync(`
import importlib
spec = importlib.util.find_spec("pygame")
if spec is not None:
    import pygame
    if pygame.get_init():
        pygame.quit()
`);
    } catch {}
  }

  // Clear turtle canvas (fast)
  const tc = document.getElementById(`turtle-canvas-q${qid}`);
  if (tc) {
    const ctx = tc.getContext('2d');
    ctx.setTransform(1,0,0,1,0,0);
    ctx.clearRect(0,0,tc.width, tc.height);
  }

  // Hide gfx
  const gc = document.getElementById(`graphics-container-q${qid}`);
  const pg = document.getElementById(`graphics-canvas-q${qid}`);
  if (pg) pg.style.display = 'none';
  if (tc) tc.style.display = 'none';
  if (gc) gc.style.display = 'none';

  const status = document.getElementById(`status-q${qid}`);
  if (status) status.textContent = 'Stopped';
  window._mini_console_write = () => {};
}

// --------------- Monaco init for all mini editors on page ---------------
function initMiniEditors() {
  const blocks = document.querySelectorAll('.mini-editor');
  if (!blocks.length) return;

  // AMD loader (the page must include loader.js in <head>)
  require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.34.1/min/vs' }});
  require(['vs/editor/editor.main'], function () {
    window.__miniEditors = new Map();

    blocks.forEach(block => {
      const qid = String(block.dataset.qid);
      const host = document.getElementById(`editor-q${qid}`);

      const editor = monaco.editor.create(host, {
        value: '',              // (optional) inject starter code if you have it
        language: 'python',
        theme: 'vs-dark',
        automaticLayout: true,
        scrollBeyondLastLine: false,
      });

      // autosize to content
      const fit = () => { host.style.height = editor.getContentHeight() + 'px'; editor.layout(); };
      fit(); editor.onDidContentSizeChange(fit);

      window.__miniEditors.set(qid, editor);
    });

    // Before form submit, copy each editor into its hidden textarea
    const form = document.getElementById('hw-form');
    if (form) {
      form.addEventListener('submit', () => {
        window.__miniEditors.forEach((ed, qid) => {
          const field = document.getElementById(`code-q${qid}`);
          if (field) field.value = ed.getValue();
        });
      });
    }

    // Wire Run/Stop buttons
    document.querySelectorAll('.run-btn').forEach(btn => {
      btn.addEventListener('click', () => runMini(btn.dataset.qid));
    });
    document.querySelectorAll('.stop-btn').forEach(btn => {
      btn.addEventListener('click', () => stopMini(btn.dataset.qid));
    });
  });
}

// --------------- Bootstrap ---------------
document.addEventListener('DOMContentLoaded', initMiniEditors);