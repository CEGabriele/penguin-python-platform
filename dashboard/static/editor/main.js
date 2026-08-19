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
let currentFontSize = 14;
let wordWrapEnabled = true;
let autosaveTimer;
let projectId = null;
let currentFilePath = "main.py";
let cachedProjectFiles = null;
let cachedProjectId = null;
let statusSpan = document.getElementById("saveStatus");
let workerReady = false;
let workerReadyPromiseResolve = null;

// Worker heartbeat tracking
const WORKER_SESSION_ID = 'worker_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
let heartbeatInterval = null;

function sendWorkerHeartbeat(action = 'start') {
  const url = `/dashboard/api/worker/heartbeat/?worker_id=${encodeURIComponent(WORKER_SESSION_ID)}&action=${action}`;
  navigator.sendBeacon(url) || fetch(url, { method: 'GET', keepalive: true }).catch(() => {});
}

function startWorkerHeartbeat() {
  if (heartbeatInterval) clearInterval(heartbeatInterval);
  sendWorkerHeartbeat('start');
  heartbeatInterval = setInterval(() => sendWorkerHeartbeat('start'), 10000);
}

function stopWorkerHeartbeat() {
  if (heartbeatInterval) clearInterval(heartbeatInterval);
  sendWorkerHeartbeat('stop');
}

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



function extractScreenSize(code) {
  const setupMatch = code.match(/\w+\.setup\s*\(\s*(?:width\s*=\s*)?(\d+)\s*,\s*(?:height\s*=\s*)?(\d+)/);
  const setmodeMatch = code.match(/pygame\.display\.set_mode\s*\(\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*\)/);

  if (setupMatch) {
    return { width: parseInt(setupMatch[1]), height: parseInt(setupMatch[2]) };
  }
  if (setmodeMatch) {
    return { width: parseInt(setmodeMatch[1]), height: parseInt(setmodeMatch[2]) };
  }
  return null;
}

function getGraphicsSize() {
  const widthInput = document.getElementById('graphicsWidth');
  const heightInput = document.getElementById('graphicsHeight');
  return {
    width: widthInput ? parseInt(widthInput.value) || 640 : 640,
    height: heightInput ? parseInt(heightInput.value) || 480 : 480,
  };
}

function setGraphicsSize(width, height) {
  const widthInput = document.getElementById('graphicsWidth');
  const heightInput = document.getElementById('graphicsHeight');
  if (widthInput) widthInput.value = width;
  if (heightInput) heightInput.value = height;
  window.applyGraphicsSize();
}

window.applyGraphicsSize = function() {
  const size = getGraphicsSize();
  const pygameCanvas = document.getElementById('graphics-canvas');
  const turtleCanvas = document.getElementById('turtle-canvas');

  if (pygameCanvas) {
    pygameCanvas.width = size.width;
    pygameCanvas.height = size.height;
    pygameCanvas.style.maxWidth = '100%';
    pygameCanvas.style.height = 'auto';
  }

  if (turtleCanvas) {
    // For turtle, clear and update the container
    turtleCanvas.innerHTML = "";
    turtleCanvas.style.width = size.width + 'px';
    turtleCanvas.style.height = size.height + 'px';
  }

  const container = document.getElementById('graphics-container');
  if (container) {
    container.style.maxWidth = (size.width + 20) + 'px';
  }
};

function showGraphicsSettings() {
  const settings = document.getElementById('graphics-settings');
  if (settings) {
    settings.style.display = 'block';
  }
}

function ensureTurtleCanvas() {
  const container = document.getElementById('graphics-container');
  let div = document.getElementById('turtle-canvas');
  if (!div) {
    div = document.createElement('div');
    div.id = 'turtle-canvas';
    div.style.display = 'none';
    container?.appendChild(div);
  }
  return div;
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
        stopWorkerHeartbeat();
        break;
      case 'error':
        console_write(`<span style="color:red;">${message.error}</span>\n`);
        codeRunning = false;
        stopWorkerHeartbeat();
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
  startWorkerHeartbeat();

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

// replacing Skulpt's ontimer function with one that can handle multiple timers at a timer
const turtleTimerQueue = {
  timers: [],
  schedule(fn, delayMs) {
    const id = setTimeout(() => {
      this.timers = this.timers.filter(t => t.id !== id);
      try {
        Sk.misceval.asyncToPromise(() => Sk.misceval.callsimOrSuspendArray(fn, []))
            .catch(err => {
              console_write(`<span style="color:red;">${err.toString ? err.toString() : err}</span>\n`);
            });
      } catch (err) {
        console_write(`<span style="color:red;">${err.toString ? err.toString() : err}</span>\n`);
      }
    }, delayMs);
    this.timers.push({ id, fn });
    return id;
  },
  clearAll() {
    this.timers.forEach(t => clearTimeout(t.id));
    this.timers = [];
  }
};

function makeOntimerPatch() {
  return new Sk.builtin.func(function (self, fn, t) {
    let delayMs = 0;
    if (t !== undefined && t !== null && t !== Sk.builtin.none.none$) {
      delayMs = Sk.builtin.asnum$(t);
    }
    turtleTimerQueue.schedule(fn, delayMs);
    return Sk.builtin.none.none$;
  });
}

Sk.onAfterImport = function (moduleName) {
  if (moduleName !== "turtle") return;
  const turtleMod = Sk.sysmodules.quick$lookup(new Sk.builtin.str("turtle"));
  if (!turtleMod) return;

  if (turtleMod.$d.ontimer) {
    turtleMod.$d.ontimer = makeOntimerPatch();
  }
  const ScreenClass = turtleMod.$d.Screen;
  if (ScreenClass && ScreenClass.prototype && ScreenClass.prototype.ontimer) {
    ScreenClass.prototype.ontimer = makeOntimerPatch();
  }
};

async function runWithSkulptTurtle(code) {
  // clear timer queue before running
  turtleTimerQueue.clearAll();
  const container = document.getElementById("graphics-container");
  const pygameCanvas = document.getElementById("graphics-canvas");
  const turtleCanvas = document.getElementById("turtle-canvas");

  const screenSize = extractScreenSize(code);
  if (screenSize) {
    setGraphicsSize(screenSize.width, screenSize.height);
  }
  const size = getGraphicsSize();

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
  Sk.TurtleGraphics.width = size.width;
  Sk.TurtleGraphics.height = size.height;

  try {
    await Sk.misceval.asyncToPromise(() =>
      Sk.importMainWithBody("<stdin>", false, code, true)
    );
  } catch (err) {
    console_write(`<span style="color:red;">${err.toString()}</span>\n`);
  } finally {
    codeRunning = false;
    stopWorkerHeartbeat();
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
  stopWorkerHeartbeat();

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
      keepalive: true,
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

// Autosave immediately when leaving page or switching tabs
window.addEventListener("beforeunload", () => {
  if (window.IS_READONLY) return;
  if (!editor || !editor.getModel()) return;
  const code = editor.getValue();
  if (!projectId || code === lastSavedCode) return;
  clearTimeout(autosaveTimer);

  // Fetch with keepalive ensures the request completes even during unload
  fetch(window.location.href, {
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
    keepalive: true,
  }).catch(err => {
    console.error("Autosave on unload failed:", err);
  });
});

window.addEventListener("visibilitychange", () => {
  if (document.hidden && !window.IS_READONLY) {
    clearTimeout(autosaveTimer);
    autosave();
  }
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

// Font size controls
window.increaseFontSize = function() {
  if (editor && currentFontSize < 32) {
    currentFontSize += 2;
    editor.updateOptions({ fontSize: currentFontSize });
    document.getElementById('fontSizeDisplay').textContent = currentFontSize;
    localStorage.setItem('editorFontSize', currentFontSize);
  }
};

window.decreaseFontSize = function() {
  if (editor && currentFontSize > 10) {
    currentFontSize -= 2;
    editor.updateOptions({ fontSize: currentFontSize });
    document.getElementById('fontSizeDisplay').textContent = currentFontSize;
    localStorage.setItem('editorFontSize', currentFontSize);
  }
};

window.toggleWordWrap = function() {
  if (!editor) return;
  wordWrapEnabled = !wordWrapEnabled;
  editor.updateOptions({ wordWrap: wordWrapEnabled ? 'on' : 'off' });
  const btn = document.getElementById('wordWrapBtn');
  if (btn) {
    btn.style.opacity = wordWrapEnabled ? '1' : '0.5';
  }
  localStorage.setItem('editorWordWrap', wordWrapEnabled);
};

// Project menu functions
function getCsrfToken() {
  let name = 'csrftoken';
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

window.renameProject = function(projectId, currentName) {
  const newName = prompt('Enter new project name:', currentName);
  if (!newName || !newName.trim()) return;

  fetch(`/dashboard/editor/project/${projectId}/rename/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken()
    },
    body: JSON.stringify({ name: newName.trim() })
  })
  .then(r => r.json())
  .then(data => {
    if (data.ok) {
      location.reload();
    } else {
      alert('Error: ' + (data.error || 'Unknown error'));
    }
  })
  .catch(e => alert('Error: ' + e));
};

window.deleteProject = function(projectId, projectName) {
  if (!confirm(`Are you sure you want to delete "${projectName}"? This cannot be undone.`)) {
    return;
  }

  fetch(`/dashboard/editor/project/${projectId}/delete/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': getCsrfToken()
    }
  })
  .then(r => r.json())
  .then(data => {
    if (data.ok) {
      window.location.href = '/dashboard/editor/';
    } else {
      alert('Error: ' + (data.error || 'Unknown error'));
    }
  })
  .catch(e => alert('Error: ' + e));
};

// Toggle project menu dropdown
document.addEventListener('click', function(e) {
  if (e.target.classList.contains('project-menu-btn')) {
    const dropdown = e.target.nextElementSibling;
    document.querySelectorAll('.project-menu-dropdown').forEach(d => {
      if (d !== dropdown) d.style.display = 'none';
    });
    dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
  } else if (!e.target.closest('.project-menu-dropdown')) {
    document.querySelectorAll('.project-menu-dropdown').forEach(d => {
      d.style.display = 'none';
    });
  }
}, true);

// Load saved editor preferences
document.addEventListener('DOMContentLoaded', function() {
  const savedFontSize = localStorage.getItem('editorFontSize');
  const savedWordWrap = localStorage.getItem('editorWordWrap');

  if (savedFontSize) {
    currentFontSize = parseInt(savedFontSize);
  }
  if (savedWordWrap === 'true') {
    wordWrapEnabled = true;
  }

  // Apply settings when editor is ready
  const checkEditor = setInterval(function() {
    if (editor) {
      clearInterval(checkEditor);
      editor.updateOptions({
        fontSize: currentFontSize,
        wordWrap: wordWrapEnabled ? 'on' : 'off'
      });
      document.getElementById('fontSizeDisplay').textContent = currentFontSize;
      const btn = document.getElementById('wordWrapBtn');
      if (btn && wordWrapEnabled) {
        btn.style.opacity = '1';
      }
    }
  }, 100);
});