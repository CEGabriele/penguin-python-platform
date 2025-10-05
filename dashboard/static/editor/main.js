// import js turtle
import turtleModule from './turtle.js';

let default_code = `# write your Python code here

print("Hello World!")

`;


let pyodide = null;
let editor = null;
let codeRunning = false;
let inputInProgress = false;
let abortController = null;
let lastRunUsedPygame = false;
let lastRunUsedTurtle = false;

// configure Monaco
require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.34.1/min/vs' } });
require(['vs/editor/editor.main'], function () {
   let code = default_code
   const minLines = 30;
   const lineCount = code.split("\n").length;

   if (lineCount < minLines) {
      code += "\n".repeat(minLines - lineCount);
   }
   

   editor = monaco.editor.create(document.getElementById('editor'), {
      value: code,
      language: 'python',
      theme: 'vs-dark',
      automaticLayout: true,
      scrollBeyondLastLine: false,
   });

   const editor_container = document.getElementById('editor');
   const graphics_container = document.getElementById('graphics-container');

   function updateHeight(){
      const height = editor.getContentHeight();
      editor_container.style.height = height + 'px';
      graphics_container.style.top = height + 'px';
   }

   updateHeight();
   editor.onDidContentSizeChange(updateHeight);
});

// writes to the console
window.console_write = function (s) {
   const consoleDiv = document.getElementById('console');
   consoleDiv.innerHTML += String(s ?? '').replace(/\n/g, '<br>');
   consoleDiv.scrollTop = consoleDiv.scrollHeight;
};

window.console_input = function (promptText = "") {
   return new Promise((resolve, reject) => {
     // prevent overlapping inputs
     if (window.inputInProgress) {
       reject(new Error("Input already in progress"));
       return;
     }
     window.inputInProgress = true;
 
     const consoleEl = document.getElementById("console");
 
     const line = document.createElement("div");
     const promptSpan = document.createElement("span");
     promptSpan.textContent = promptText || "";
     const inputBox = document.createElement("input");
     inputBox.type = "text";
     inputBox.className = "console-input-box";
 
     line.appendChild(promptSpan);
     line.appendChild(inputBox);
     consoleEl.appendChild(line);
     inputBox.focus();
     consoleEl.scrollTop = consoleEl.scrollHeight;
 
     const onEnter = (e) => {
       if (e.key === "Enter") {
         const val = inputBox.value;
         line.innerHTML = `<span>${promptText}${val}</span>`;
         inputBox.removeEventListener("keydown", onEnter);
         window.inputInProgress = false;
         resolve(val);
       }
     };
     inputBox.addEventListener("keydown", onEnter);
 
     // handle aborts
     if (!window.abortController) window.abortController = new AbortController();
     window.abortController.signal.addEventListener("abort", () => {
       inputBox.removeEventListener("keydown", onEnter);
       window.inputInProgress = false;
       reject(new Error("Input aborted"));
     });
   });
 };

 function ensureTurtleCanvas() {
   const container = document.getElementById('graphics-container');
   let canvas = document.getElementById('turtle-canvas');
   if (!canvas) {
     canvas = document.createElement('canvas');
     canvas.id = 'turtle-canvas';
     canvas.width = 640;
     canvas.height = 480;
     canvas.style.border = '1px solid #444';
     canvas.style.display = 'none';
     container?.appendChild(canvas);
   }
 
   return canvas;
 }

async function loadPyodideAndPackages() {
pyodide = await loadPyodide();
window.pyodide = pyodide; // for debugging if needed
await pyodide.loadPackage("micropip");

// register fake turtle module if needed
pyodide.registerJsModule("turtle", turtleModule);

// ✅ define console I/O and fully compatible input()
await pyodide.runPythonAsync(`
import sys, asyncio, js, builtins

class ConsoleIO:
    def write(self, s):
        try:
            js.console_write(s)
        except Exception:
            pass
    def flush(self): pass

sys.stdout = sys.stderr = ConsoleIO()

# async-only input; print prompt exactly once via JS
async def input(prompt=""):
    if prompt:
        js.console_write(prompt)
    return await js.console_input("")

builtins.input = input
`);
console_write("Pyodide is ready ");
}
loadPyodideAndPackages();

// runs when run button is pressed
async function runCode() {
   // make sure everything is ready
   if (!pyodide) return alert('Pyodide not loaded.');
   if (codeRunning) return alert('Code is already running.');

   codeRunning = true;
   inputInProgress = false;
   // clear console
   document.getElementById('console').innerHTML = '';

   // get code and check what is used
   const rawCode = editor.getValue();
   const usesPygame = /\bimport\s+pygame\b/.test(rawCode);
   const usesTurtle = /\bimport\s+turtle\b|\bfrom\s+turtle\s+import\b/.test(rawCode);
   lastRunUsedPygame = usesPygame;
   lastRunUsedTurtle = usesTurtle;


   const container = document.getElementById('graphics-container');
   const pygameCanvas = document.getElementById('graphics-canvas');
   const turtleCanvas = ensureTurtleCanvas(); // create if missing

   // show appropriate canvases/container
   if (usesPygame || usesTurtle) {
      container.style.display = 'block';
      container.style.height = '';
      container.style.padding = '5px';
   } else {
      container.style.display = 'none';
   }
   if (pygameCanvas) pygameCanvas.style.display = usesPygame ? 'inline-block' : 'none';
   if (turtleCanvas) turtleCanvas.style.display = usesTurtle ? 'inline-block' : 'none';

   // load pygame before running
   if (usesPygame) {
      await pyodide.loadPackage('pygame-ce');

      // SDL things
      window.Module = pyodide._module;
      Module.canvas = pygameCanvas;
      pygameCanvas.style.background = '#111';

      // keep editor focused for now so pygame doesn't grab it
      pygameCanvas.setAttribute('tabindex', '-1');
      pygameCanvas.addEventListener('focus', (e) => {
         e.preventDefault();
         editor?.focus();
      });
   }

   // turtle setup if using
   if (usesTurtle) {
      turtleModule.setup({
         canvas: turtleCanvas,
         width: 640,
         height: 480,
         bgcolor: 'white',
      });
   }

   abortController = new AbortController();

   try {
      const wrapped = autoWrapAsync(rawCode);
      await pyodide.runPythonAsync(wrapped);
   } catch (err) {
      console_write(`<span style="color:red;">${err.toString()}</span>\n`);
   } finally {
      codeRunning = false;
   }
}
window.runCode = runCode;

// runs when stop button is pressed
async function stopCode() {
   // if pygame was running, safely quit
   if (lastRunUsedPygame) {
      try {
         await pyodide.runPythonAsync(`
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
      } catch (e) {
         console.warn('posting QUIT failed (safe to ignore):', e);
      }
      // give time to process quitting
      await new Promise((r) => setTimeout(r, 120));
   }

   // abort all awaits (input)
   if (abortController) {
      abortController.abort();
      abortController = null;
   }
   codeRunning = false;
   inputInProgress = false;

   // make sure everything is cleaned up
   try {
      await pyodide.runPythonAsync(`
import importlib
spec = importlib.util.find_spec("pygame")
if spec is not None:
    import pygame
    if pygame.get_init():
        pygame.quit()
`);
   } catch (e) {
      console.warn('pygame cleanup skipped:', e);
   }

   // clean turtle canvas if it was used
   try {
      if (lastRunUsedTurtle) {
         const turtleCanvas = document.getElementById('turtle-canvas');
         if (turtleCanvas) {
            // fast clear method
            const w = turtleCanvas.width, h = turtleCanvas.height;
            const ctx = turtleCanvas.getContext('2d');
            ctx.setTransform(1, 0, 0, 1, 0, 0);
            ctx.clearRect(0, 0, w, h);
         }
      }
   } catch (e) {
      console.warn('turtle clear failed', e);
   }


   // hide canvases and collapse graphics container
   const containerEl = document.getElementById('graphics-container');
   const pygameCanvas = document.getElementById('graphics-canvas');
   const turtleCanvas = document.getElementById('turtle-canvas');
   if (pygameCanvas) pygameCanvas.style.display = 'none';
   if (turtleCanvas) turtleCanvas.style.display = 'none';
   if (containerEl) {
      containerEl.style.display = 'none';
   }

   // not entirely sure what this does
   if (pyodide?._module) {
      try { pyodide._module.canvas = null; } catch { }
   }

   // refocus monaco editor
   if (editor) setTimeout(() => editor.focus(), 50);

   // reset last used
   lastRunUsedPygame = false;
   lastRunUsedTurtle = false;
}

window.stopCode = stopCode;

window.EditorAPI = {
   getValue: () => editor?.getValue?.() ?? '',
   setValue: (v) => editor?.setValue?.(v ?? ''),
};

function autoWrapAsync(code) {
   code = code.replace(/\r\n/g, "\n");
 
   // Step 1 — replace input() with await input()
   // (but skip "def " lines to avoid inserting await inside definitions)
   let lines = code.split("\n").map(line => {
     if (/^\s*def\s+/.test(line)) return line;
     return line.replace(/\binput\s*\(/g, "await input(");
   });
 
   // Step 2 — identify functions that contain 'await'
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
 
   // Step 3 — mark which functions need async
   const asyncFuncs = new Set();
   for (const f of funcs) {
     const body = lines.slice(f.start + 1, f.end).join("\n");
     if (/\bawait\b/.test(body)) asyncFuncs.add(f.name);
   }
 
   // Step 4 — propagate async to callers
   let changed = true;
   while (changed) {
     changed = false;
     for (const f of funcs) {
       if (asyncFuncs.has(f.name)) continue;
       const body = lines.slice(f.start + 1, f.end).join("\n");
       for (const callee of asyncFuncs) {
         const callRx = new RegExp(`\\b${callee}\\s*\\(`);
         if (callRx.test(body)) {
           asyncFuncs.add(f.name);
           changed = true;
           break;
         }
       }
     }
   }
 
   // Step 5 — rewrite def → async def (only once)
   for (const f of funcs) {
     if (asyncFuncs.has(f.name)) {
       lines[f.start] = lines[f.start].replace(/^(\s*)def(\s+)/, "$1async def$2");
     }
   }
 
   // Step 6 — add await to call sites (but skip definition lines)
   if (asyncFuncs.size > 0) {
     const asyncNames = Array.from(asyncFuncs);
     const callRx = new RegExp(`\\b(${asyncNames.join("|")})\\s*\\(`, "g");
     lines = lines.map(line => {
       if (/^\s*(async\s+)?def\s+/.test(line)) return line; // skip defs
       if (/\bawait\s+/.test(line)) return line; // skip already awaited
       return line.replace(callRx, (match, name) => `await ${name}(`);
     });
   }
 
   // Step 7 — add small async sleep inside loops for UI smoothness
   const loopRx = /^\s*(for|while)\b.*:\s*$/;
   const expanded = [];
   for (let i = 0; i < lines.length; i++) {
     expanded.push(lines[i]);
     if (loopRx.test(lines[i])) {
       const base = (lines[i].match(/^\s*/)||[""])[0] + "    ";
       expanded.push(`${base}await asyncio.sleep(0)`);
     }
   }
 
   // Step 8 — wrap everything in async main
   const indented = expanded.map(l => "    " + l).join("\n");
   return `import asyncio\nasync def __user_main__():\n${indented}\n\nawait __user_main__()`;
}
 