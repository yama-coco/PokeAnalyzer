import { app, BrowserWindow, shell } from "electron";
import { spawn, ChildProcess } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcess | null = null;

function getBackendPath(): string {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend");
  }
  return path.join(__dirname, "../../backend");
}

function getUvPath(): string {
  if (app.isPackaged) {
    const binaryName = process.platform === "win32" ? "uv.exe" : "uv";
    return path.join(process.resourcesPath, "uv", binaryName);
  }
  return "uv";
}

function startBackend(): void {
  const backendPath = getBackendPath();
  const uvPath = getUvPath();
  const uvDataDir = path.join(app.getPath("userData"), "uv");

  backendProcess = spawn(
    uvPath,
    ["run", "uvicorn", "app.main:app", "--port", "8000"],
    {
      cwd: backendPath,
      stdio: "pipe",
      env: {
        ...process.env,
        UV_CACHE_DIR: path.join(uvDataDir, "cache"),
        UV_PYTHON_INSTALL_DIR: path.join(uvDataDir, "python"),
      },
    },
  );
  backendProcess.stdout?.on("data", (data) => console.log(`[backend] ${data}`));
  backendProcess.stderr?.on("data", (data) =>
    console.error(`[backend] ${data}`),
  );
  backendProcess.on("error", (err) => {
    console.error(`[backend] Failed to start: ${err.message}`);
  });
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "PAL-C - PokeAnalysis Live for Champions",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  if (process.env.NODE_ENV === "development") {
    mainWindow.loadURL("http://localhost:5173");
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  startBackend();
  setTimeout(createWindow, 2000);

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  backendProcess?.kill();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});
