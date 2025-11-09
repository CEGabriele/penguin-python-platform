// import js turtle
import turtleModule from './turtle.js';

let default_code = `# write your Python code here

print("Hello World!")

`;


let pyodide = null;
let editor = null;
let worker = null;
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
  editor.onDidChangeModelContent(onEditorChange);
  setInterval(autosave, 60000); // periodic autosave every minute
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
    inputInProgress = true;

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
        inputInProgress = false;
        resolve(val);
      }
    };
    inputBox.addEventListener("keydown", onEnter);

    // handle aborts
    if (!abortController) abortController = new AbortController();
    abortController.signal.addEventListener("abort", () => {
      inputBox.removeEventListener("keydown", onEnter);
      inputInProgress = false;
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

function initWorker(){
  if (worker) worker.terminate();
  worker = new Worker('/static/editor/worker.js');
  
  worker.onmessage = (e) => {
    const message = e.data;
    switch (message.type) {
      case 'ready':
        break;
      case 'stdout':
        console_write(message.data);
        break;
      case 'input_request': {
        const promptText = message.prompt || "";
        (async () => {
          try {
            const inputValue = await window.console_input(promptText);
            worker.postMessage({ type: 'input_response', value: inputValue });
          } catch {
            worker.postMessage({ type: 'input_abort'});
          }
        })();
        break;
      }
      case 'turtle_call': {
        try {
          const {method, args} = message;
          if (typeof turtleModule[method] === 'function') {
            turtleModule[method](...args);
          } 
        } catch (e) {
          console.warn('turtle_call error:', e);
        }
        break
      }
      case 'done':
        codeRunning = false;
        break;
      case 'error':
        console_write(`<span style="color:red;">${message.error}</span>\n`);
        codeRunning = false;
        break;
    }
  };
}

initWorker();


// runs when run button is pressed
async function runCode() {
  // make sure everything is ready
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
  if (abortController) {
    try { abortController.abort(); } catch {}
    abortController = null;
  }
  worker.postMessage({
    type: 'run',
    code: rawCode,
    usesPygame,
    usesTurtle
  });
}
window.runCode = runCode;

function clearTurtleCanvasIfVisible() {
  try {
    if (lastRunUsedTurtle) {
      const turtleCanvas = document.getElementById('turtle-canvas');
      if (turtleCanvas) {
        const w = turtleCanvas.width, h = turtleCanvas.height;
        const ctx = turtleCanvas.getContext('2d');
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, w, h);
      }
    }
  } catch (e) {
    console.warn('turtle clear failed', e);
  }
}

function hideGraphics() {
  const containerEl = document.getElementById('graphics-container');
  const pygameCanvas = document.getElementById('graphics-canvas');
  const turtleCanvas = document.getElementById('turtle-canvas');
  if (pygameCanvas) pygameCanvas.style.display = 'none';
  if (turtleCanvas) turtleCanvas.style.display = 'none';
  if (containerEl) containerEl.style.display = 'none';
}

// runs when stop button is pressed
async function stopCode() {
  if (abortController) {
    try { abortController.abort(); } catch {}
    abortController = null;
  }
  inputInProgress = false;
  codeRunning = false;

  if (worker) {
    worker.terminate();
    initWorker();
  }
  clearTurtleCanvasIfVisible();
  hideGraphics();

  if (editor) setTimeout(() => editor.focus(), 60);

  lastRunUsedPygame = false;
  lastRunUsedTurtle = false;
}

window.stopCode = stopCode;

window.EditorAPI = {
  getValue: () => editor?.getValue?.() ?? '',
  setValue: (v) => editor?.setValue?.(v ?? ''),
};

const CLASS_SELECT = document.getElementById("class");
const NAME_INPUT = document.getElementById("name");
const STATUS_SPAN = document.getElementById("saveStatus");
let lastSavedCode = "";
let autosaveTimer;

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let cookie of cookies) {
      cookie = cookie.trim();
      if (cookie.startsWith(name + "=")) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

async function autosave() {
  if (!editor) return;
  const code = editor.getValue();
  const class_id = CLASS_SELECT?.value;
  const name = NAME_INPUT?.value || "autosave";

  if (code === lastSavedCode || !class_id) return;
  lastSavedCode = code;

  try {
    const response = await fetch(window.location.pathname, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify({
        code: code,
        class_id: class_id,
        name: name,
      }),
    });
    if (response.ok) {
      STATUS_SPAN.textContent = "Autosaved";
    } else {
      STATUS_SPAN.textContent = "Save failed";
    }
  } catch (err) {
    STATUS_SPAN.textContent = "Network error";
  }
}

function onEditorChange() {
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(autosave, 2000);
}


 