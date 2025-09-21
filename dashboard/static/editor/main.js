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

// do some fancy stuff to allow for live inputs
window.console_input = async function (prompt) {
   if (inputInProgress) throw new Error('Reentrant input call');
   inputInProgress = true;
   const consoleDiv = document.getElementById('console');

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

// loading pyodide
async function loadPyodideAndPackages() {
   pyodide = await loadPyodide();
   await pyodide.loadPackage('micropip');

   // register fake "turtle" module
   pyodide.registerJsModule('turtle', turtleModule);

   // console setup
   await pyodide.runPythonAsync(`
import sys, asyncio, js
class ConsoleIO:
    def write(self, s):
        try:
            js.console_write(s)
        except Exception:
            js.console.log(s)
    def flush(self): pass
sys.stdout = sys.stderr = ConsoleIO()
async def input(prompt=''):
    return await js.console_input(prompt)
  `);

   console_write('Pyodide is ready.\n');
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

   // wrapping allows input to convert to async
   const code = autoWrapAsync(rawCode);
   abortController = new AbortController();

   try {
      await pyodide.runPythonAsync(code);
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