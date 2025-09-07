// import js turtle
import turtleModule from './turtle.js';

let default_code = `# write your Python code here

print("Hello World!")

`;


let pyodide = null;
window.__miniEditors = new Map();
let codeRunning = false;
let inputInProgress = false;
let abortController = null;
let lastRunUsedPygame = false;
let lastRunUsedTurtle = false;
window.current_qid = null;

// configure Monaco
require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.34.1/min/vs' } });
require(['vs/editor/editor.main'], function () {
  document.querySelectorAll('.mini-editor').forEach(block => {
    const qid = String(block.dataset.qid);
    const host = document.getElementById(`editor-q${qid}`);
    const editor = monaco.editor.create(host, {
       value: default_code,
       language: 'python',
       theme: 'vs-dark',
       automaticLayout: true,
       scrollBeyondLastLine: false,
    });


   const editor_container = host;
   const graphics_container = document.getElementById(`graphics-container-q${qid}`);

   function updateHeight(){
      const height = editor.getContentHeight();
      editor_container.style.height = height + 'px';
      graphics_container.style.top = height + 'px';
      editor.layout()
   }

   updateHeight();
   editor.onDidContentSizeChange(updateHeight);

   window.__miniEditors.set(qid, editor);
  });
});

// writes to the console
window._mini_console_write = function (qid, s) {
  const consoleDiv = document.getElementById(`console-q${qid}`);


  if (consoleDiv) {
    consoleDiv.innerHTML += String(s ?? '').replace(/\n/g, '<br>');
    consoleDiv.scrollTop = consoleDiv.scrollHeight;
  }
};

// do some fancy stuff to allow for live inputs
window._mini_console_input = async function(qid, prompt) {
   if (inputInProgress) throw new Error('Reentrant input call');
   inputInProgress = true;
   const consoleDiv = document.getElementById(`console-q${qid}`);

   return await new Promise((resolve, reject) => {
      if (!abortController) abortController = new AbortController();
      abortController.signal.addEventListener('abort', () => {
         inputInProgress = false;
         reject(new Error('Input aborted.'));
      });

      const inputLine = document.createElement('div');
      inputLine.innerHTML = `<span>${prompt}</span><input id="userInput" />`;
      const inputBox = inputLine.querySelector('input');
      consoleDiv.appendChild(inputLine);
      inputBox.focus();

      const handler = (e) => {
         if (e.key === 'Enter') {
            const value = inputBox.value;
            inputLine.innerHTML = `<span>${prompt}${value}</span>`;
            inputBox.removeEventListener('keydown', handler);
            inputInProgress = false;
            resolve(value);
         }
      };
      inputBox.addEventListener('keydown', handler);
   });
};

// makes sure await/async is used
function autoWrapAsync(code) {
   if (code.includes("async def __main__")) return code;

   let transformed = code.replace(/\binput\s*\(/g, "await input(");

   let lines = transformed.split("\n");

   lines = lines.map(line => "    " + line);

   const loopRegex = /^\s*(for|while)\b.*:\s*$/;
   const newLines = [];

   for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      newLines.push(line);

      if (loopRegex.test(line)) {
         const indent = line.match(/^\s*/)[0] + "    ";
         newLines.push(`${indent}await asyncio.sleep(0)`);
      }
   }

   return `import asyncio\nasync def __main__():\n${newLines.join("\n")}\n\nawait __main__()`;
}




// make sure turtle has a canvas again
function ensureTurtleCanvas(qid) {
  const container = document.getElementById(`graphics-container-q${qid}`);
  let canvas = document.getElementById(`turtle-canvas-q${qid}`);
  if (!canvas) {
     canvas = document.createElement('canvas');
     canvas.id = `turtle-canvas-q${qid}`;
     canvas.width = 640;
     canvas.height = 480;
     canvas.style.border = '1px solid #444';
     canvas.style.display = 'none';
     container?.appendChild(canvas);
  }
  return canvas;
}

// runs when run button is pressed
async function runMini(qid) {
   // make sure everything is ready
   if (!pyodide) return alert('Pyodide not loaded.');
   if (codeRunning) return alert('Code is already running.');

   window.current_qid= qid;
   pyodide.globals.set("CURRENT_QID", qid);
   codeRunning = true;
   inputInProgress = false;
   // clear console
   const consoleBox = document.getElementById(`console-q${qid}`);
   if (consoleBox) consoleBox.innerHTML = '';

   const rawCode = window.__miniEditors.get(qid).getValue();
   const usesPygame = /\bimport\s+pygame\b/.test(rawCode);
   const usesTurtle = /\bimport\s+turtle\b|\bfrom\s+turtle\s+import\b/.test(rawCode);
   lastRunUsedPygame = usesPygame;
   lastRunUsedTurtle = usesTurtle;

   const container = document.getElementById(`graphics-container-q${qid}`);
   const pygameCanvas = document.getElementById(`graphics-canvas-q${qid}`);
   const turtleCanvas = ensureTurtleCanvas(qid);

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

   // wrapping allows input to convert to async
   const code = autoWrapAsync(rawCode);
   abortController = new AbortController();

   try {
      await pyodide.runPythonAsync(code);
   } catch (err) {
    window._mini_console_write(CURRENT_QID, `<span style="color:red;">${err.toString()}</span>\n`);
   } finally {
      codeRunning = false;
   }
}
window.runMini = runMini;

// runs when stop button is pressed
async function stopMini(qid) {
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

   const turtleCanvas = document.getElementById(`turtle-canvas-q${qid}`);
   if (turtleCanvas) {
      const ctx = turtleCanvas.getContext('2d');
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, turtleCanvas.width, turtleCanvas.height);
   }

   const containerEl = document.getElementById(`graphics-container-q${qid}`);
   const pygameCanvas = document.getElementById(`graphics-canvas-q${qid}`);
   if (pygameCanvas) pygameCanvas.style.display = 'none';
   if (turtleCanvas) turtleCanvas.style.display = 'none';
   if (containerEl) containerEl.style.display = 'none';

   if (pyodide?._module) {
      try { pyodide._module.canvas = null; } catch {}
   }

   // not entirely sure what this does
   if (pyodide?._module) {
      try { pyodide._module.canvas = null; } catch { }
   }

   window.__miniEditors.get(qid)?.focus();

   lastRunUsedPygame = false;
   lastRunUsedTurtle = false;
}

window.stopMini = stopMini;

window.EditorAPI = {
  getValue: (qid) => window.__miniEditors.get(String(qid))?.getValue() ?? '',
  setValue: (qid, v) => window.__miniEditors.get(String(qid))?.setValue(v ?? ''),
};

// loading pyodide
async function loadPyodideAndPackages() {
  pyodide = await loadPyodide();

  // register fake "turtle" module
  pyodide.registerJsModule('turtle', turtleModule);

  // expose functions to Python
  self._mini_console_write = window._mini_console_write;
  self._mini_console_input = window._mini_console_input;
  self.current_qid = window.current_qid;

  // console bridge setup
  await pyodide.runPythonAsync(`
import sys, asyncio, js

CURRENT_QID = None
class ConsoleIO:
    def write(self, s):
        try:
            # Pass current_qid so we know which console to target
            js._mini_console_write(CURRENT_QID, s)
        except Exception as e:
            js.console.log("Bridge error:", str(e))
    def flush(self): 
        pass

sys.stdout = sys.stderr = ConsoleIO()

async def input(prompt=''):
    return await js._mini_console_input(CURRENT_QID, prompt)

print("Mini editor bridge connected ✓")
  `);

  console.log("Pyodide is ready.");
}
loadPyodideAndPackages();