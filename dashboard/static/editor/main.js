// import js turtle

//import turtleModule from './turtle.js';

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
let lastSavedCode = "";
let autosaveTimer;
let projectId = null;
let currentFilePath = "main.py";
let cachedProjectFiles = null;
let cachedProjectId = null;
let statusSpan = document.getElementById("saveStatus");
let workerReady = false;
let workerReadyPromiseResolve = null;

function waitForWorkerReady() {
  if (workerReady) return Promise.resolve();
  return new Promise((resolve, reject) => {
    workerReadyPromiseResolve = resolve;

    setTimeout(() => {
      if (!workerReady) {
        reject(new Error("Python worker did not become ready"));
      }
    }, 15000);
  });
}

// configure Monaco
require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.34.1/min/vs' } });
require(['vs/editor/editor.main'], function () {
  const hidden = document.getElementById("id_code");
  
  const code =
    hidden && hidden.value !== ""
      ? hidden.value
      : default_code;
  
  editor = monaco.editor.create(document.getElementById('editor'), {
    value: code,
    language: 'python',
    theme: 'vs-dark',
    automaticLayout: true,
    scrollBeyondLastLine: false,
  });
  lastSavedCode = editor.getValue();

  projectId = document.getElementById("project_id")?.value || null;
  if (!projectId || projectId === "None") {
    projectId = null;
  }
  currentFilePath = document.getElementById("current_file_path")?.value || "main.py";

  if (window.IS_READONLY) {
    editor.updateOptions({ readOnly: true });
  }


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
    if (inputInProgress) {
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


function attachWorkerHandlers(w) {
  w.onmessage = (e) => {

    if (typeof e.data === "string") {
      console_write(e.data + "\n");
      return;
    }

    const message = e.data;

    switch (message.type) {
      case "ready":
        workerReady = true;
        window.sharedPyWorkerReady = true;
        console_write("Python ready.\n");

        if (workerReadyPromiseResolve) {
          workerReadyPromiseResolve();
          workerReadyPromiseResolve = null;
        }

        break;
      case 'stdout':
        console_write(message.data);
        break;
      case 'input_request': {
        const promptText = message.prompt || "";
        (async () => {
          try {
            const inputValue = await window.console_input(promptText);
            w.postMessage({ type: 'input_response', value: inputValue });
          } catch {
            if (codeRunning){
              w.postMessage({ type: 'input_abort' });
            }
          }
        })();
        break;
      }
      case 'turtle_call': {
        try {
          const { method, args } = message;
          if (typeof turtleModule[method] === 'function') {
            turtleModule[method](...args);
          }
        } catch (e) {
          console.warn('turtle_call error:', e);
        }
        break;
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

function initWorker() {
  workerReady = false;
  window.sharedPyWorkerReady = false;

  if (worker) {
    try { worker.terminate(); } catch {}
    worker = null;
  }

  worker = new Worker(window.WORKER_URL, { type: "classic" });
  window.sharedPyWorker = worker;

  attachWorkerHandlers(worker);

}


initWorker();

async function loadProjectFilesIfNeeded() {
  if (!projectId || projectId === "None") {
    cachedProjectFiles = {};
    cachedProjectId = null;
    return {};
  }

  if (cachedProjectId === projectId && cachedProjectFiles) {
    return { ...cachedProjectFiles };
  }

  const response = await fetch(`/dashboard/editor/project/${projectId}/files/`);
  const data = await response.json();

  if (data.ok && data.files) {
    cachedProjectFiles = data.files;
    cachedProjectId = projectId;
    return { ...cachedProjectFiles };
  }

  return {};
}



// runs when run button is pressed
async function runCode() {
  if (!editor) return;
  // make sure everything is ready
  if (codeRunning) return alert('Code is already running.');
  // clear console
  document.getElementById('console').innerHTML = '';
  if (!workerReady) {
    console_write("Starting Python...\n");
  }
  

  codeRunning = true;
  inputInProgress = false;

  // get code and check what is used
  const rawCode = editor.getValue();

  const usesSkulptTurtle = shouldUseSkulptTurtle(rawCode);
  if (usesSkulptTurtle) {
    codeRunning = true;
    inputInProgress = false;
    document.getElementById('console').innerHTML = '';
    await runWithSkulptTurtle(rawCode);
    return;
  }

  const usesPygame = /\bimport\s+pygame\b/.test(rawCode);
  lastRunUsedPygame = usesPygame;


  const container = document.getElementById('graphics-container');
  const pygameCanvas = document.getElementById('graphics-canvas');
  const turtleCanvas = ensureTurtleCanvas(); // create if missing

  // show appropriate canvases/container
  if (usesPygame) {
    container.style.display = 'block';
    container.style.height = '';
    container.style.padding = '5px';
  } else {
    container.style.display = 'none';
  }
  if (pygameCanvas) pygameCanvas.style.display = usesPygame ? 'inline-block' : 'none';


  // turtle setup if using
  if (abortController) {
    try { abortController.abort(); } catch {}
    abortController = null;
  }

  let files = {
    [currentFilePath]: rawCode
  };
  
  if (projectId && projectId !== "None") {
    try {
      files = await loadProjectFilesIfNeeded();
      files[currentFilePath] = rawCode;
    } catch (err) {
      console.warn("Failed loading project files:", err);
    }
  }
  
  
  worker.postMessage({
    type: "run_project",
    files: files,
    entry: currentFilePath,
    usesPygame
  });
}
window.runCode = runCode;

function shouldUseSkulptTurtle(code) {
  return /^\s*(import\s+turtle|from\s+turtle\s+import)/m.test(code);
}

function outf(text) {
  console_write(text);
}

function builtinRead(file) {
  if (
    Sk.builtinFiles === undefined ||
    Sk.builtinFiles["files"][file] === undefined
  ) {
    throw `File not found: '${file}'`;
  }

  return Sk.builtinFiles["files"][file];
}

async function runWithSkulptTurtle(code) {
  const container = document.getElementById("graphics-container");
  const pygameCanvas = document.getElementById("graphics-canvas");
  const turtleCanvas = document.getElementById("turtle-canvas");

  container.style.display = "block";
  if (pygameCanvas) pygameCanvas.style.display = "none";

  turtleCanvas.style.display = "block";
  turtleCanvas.innerHTML = "";

  Sk.configure({
    output: outf,
    read: builtinRead,
    __future__: Sk.python3,

    inputfun: (promptText) => {
      return window.console_input(promptText || "");
    },

    inputfunTakesPrompt: true,
  });

  Sk.TurtleGraphics = Sk.TurtleGraphics || {};
  Sk.TurtleGraphics.target = "turtle-canvas";
  Sk.TurtleGraphics.width = 640;
  Sk.TurtleGraphics.height = 480;

  try {
    await Sk.misceval.asyncToPromise(() =>
      Sk.importMainWithBody("<stdin>", false, code, true)
    );
  } catch (err) {
    console_write(`<span style="color:red;">${err.toString()}</span>\n`);
  } finally {
    codeRunning = false;
  }
}

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

  if (worker){
    try { worker.terminate(); } catch {}
    worker = null;
  }

  console_write(`
    <div style="
      color:#ffb347;
      padding:6px 10px;
      margin-top:6px;
      border-left:4px solid #ffb347;
      background:#2a2a2a;
    ">
      ⏹ Program stopped
    </div>
  `);

  clearTurtleCanvasIfVisible();
  hideGraphics();

  initWorker();

  lastRunUsedPygame = false;
  lastRunUsedTurtle = false;

  if (editor) setTimeout(() => editor.focus(), 60);
}

window.stopCode = stopCode;

window.EditorAPI = {
  getValue: () => editor?.getValue?.() ?? '',
  setValue: (v) => editor?.setValue?.(v ?? ''),
  setReadOnly: (state) => editor?.updateOptions({ readOnly: state }),
};

window.EditorProject = {
  getProjectId: () => projectId,
  setProjectId: (id) => {
    projectId = id || null;
    cachedProjectId = null;
    cachedProjectFiles = null;
  },
  getCurrentFile: () => currentFilePath,
  setCurrentFile: (path) => {
    currentFilePath = path || "main.py";
  },
  resetLastSavedCode: (code) => {
    lastSavedCode = code ?? "";
  },
  clearAutosaveTimer: () => {
    clearTimeout(autosaveTimer);
  }
};


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
  if (window.IS_READONLY) return;
  if (!editor || !editor.getModel()) return;

  const code = editor.getValue();
  if (!projectId) return;

  if (code === lastSavedCode) return;

  try {
    const response = await fetch(window.location.href, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify({
        project_id: projectId,
        path: currentFilePath,
        code: code,
      }),
    });
    if (response.ok) {
      const data = await response.json();
    
      statusSpan.textContent = "Autosaved";
      lastSavedCode = code;
    } else {
      statusSpan.textContent = "Save failed";
    }
  } catch (err) {
    statusSpan.textContent = "Network error";
    console.error("Autosave error:", err);
  }


}

function onEditorChange() {
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(autosave, 600);
}

window.addEventListener("resize", () => {
  editor.layout();
});

function setupDragDivider(){
  const main = document.getElementById("main");
  const divider = document.getElementById("drag-divider");
  const editorEl = document.getElementById("editor");
  const rightPanel = document.getElementById("right-panel");

  if (!main || !divider || !editorEl || !rightPanel) return;

  let isDragging = false;

  divider.addEventListener("mousedown", (e) => {
    isDragging = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    e.preventDefault();
  });

  window.addEventListener("mousemove", (e) => {
    if (!isDragging) return;

    const mainRect = main.getBoundingClientRect();
    let newRightWidth = mainRect.right - e.clientX;

    // set limits
    const minRight = 320;
    const minEditor = 300;
    const maxRight = mainRect.width - minEditor - divider.offsetWidth;

    const width = Math.max(minRight, Math.min(newRightWidth, maxRight));

    rightPanel.style.width = `${width}px`;
    rightPanel.style.flex = `0 0 ${width}px`;
    if (editor && editor.layout) editor.layout();
  });

  window.addEventListener("mouseup", () => {
    if (isDragging) {
      isDragging = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
    else return;
  });
}
document.addEventListener("DOMContentLoaded", setupDragDivider);