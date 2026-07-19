const { app, BrowserWindow, dialog, shell, Menu } = require('electron')
const { spawn, execFileSync } = require('child_process')
const path = require('path')
const net = require('net')
const fs = require('fs')
const { autoUpdater } = require('electron-updater')

const DJANGO_DEFAULT_PORT = 8765
const DJANGO_STARTUP_RETRIES = 120
const DJANGO_RETRY_INTERVAL_MS = 500

app.setName('StitchFlow')

let djangoProcess = null
let mainWindow = null
let djangoPort = DJANGO_DEFAULT_PORT
let logFilePath = null
let lastBackendError = 'Le serveur Django n\'a pas répondu dans les délais attendus.'

// ── Logging ──────────────────────────────────────────────────────────────────

function ensureLogger() {
  if (logFilePath) return logFilePath
  const logDir = path.join(app.getPath('userData'), 'logs')
  fs.mkdirSync(logDir, { recursive: true })
  logFilePath = path.join(logDir, 'main.log')
  return logFilePath
}

function log(message, meta = null) {
  const line = [
    new Date().toISOString(),
    message,
    meta ? JSON.stringify(meta, null, 2) : '',
  ].filter(Boolean).join(' ')

  try {
    fs.appendFileSync(ensureLogger(), `${line}\n`)
  } catch {}

  if (!app.isPackaged || process.env.DEBUG_DJANGO) {
    console.log(line)
  }
}

function logError(message, err = null) {
  const meta = err ? {
    message: err.message,
    code: err.code,
    signal: err.signal,
    stdout: err.stdout ? String(err.stdout).slice(-4000) : undefined,
    stderr: err.stderr ? String(err.stderr).slice(-4000) : undefined,
  } : null
  lastBackendError = err?.message || message
  log(message, meta)
}

// ── Utilitaires ──────────────────────────────────────────────────────────────

function getResourcesPath() {
  return app.isPackaged
    ? process.resourcesPath
    : path.join(__dirname, '..')
}

function getAppRootPath() {
  return app.isPackaged
    ? app.getAppPath()
    : path.join(__dirname, '..')
}

function getSrcPath() {
  return path.join(getAppRootPath(), 'src')
}

function getVendorPath() {
  return app.isPackaged
    ? path.join(process.resourcesPath, 'vendor')
    : path.join(getAppRootPath(), 'vendor')
}

function getPythonExecutable() {
  const appRootPath = getAppRootPath()
  const devVenvPython = path.join(appRootPath, '.venv', 'bin', 'python3')
  const devVenvPythonWin = path.join(appRootPath, '.venv', 'Scripts', 'python.exe')

  if (process.platform === 'win32' && fs.existsSync(devVenvPythonWin)) return devVenvPythonWin
  if (fs.existsSync(devVenvPython)) return devVenvPython
  return process.platform === 'win32' ? 'python' : 'python3'
}

function getBackendExecutable() {
  if (!app.isPackaged) return null
  const exeName = process.platform === 'win32' ? 'stitchflow-backend.exe' : 'stitchflow-backend'
  const candidate = path.join(process.resourcesPath, 'backend', exeName)
  return fs.existsSync(candidate) ? candidate : null
}

function getBackendCommand(args) {
  const backend = getBackendExecutable()
  if (backend) {
    return {
      command: backend,
      args,
      cwd: path.dirname(backend),
      mode: 'pyinstaller',
    }
  }

  const srcPath = getSrcPath()
  return {
    command: getPythonExecutable(),
    args: [path.join(srcPath, 'manage.py'), ...args],
    cwd: srcPath,
    mode: 'python-dev',
  }
}

function getBackendEnv(port = null) {
  const srcPath = getSrcPath()
  const env = {
    ...process.env,
    DJANGO_SETTINGS_MODULE: 'stitchflow.settings_desktop',
    PYTHONPATH: srcPath,
    STITCH_USERDATA: app.getPath('userData'),
    STITCH_VENDOR_PATH: getVendorPath(),
    PYTHONUNBUFFERED: '1',
  }
  if (port) env.STITCH_PORT = String(port)
  return env
}

function usefulEnv(env) {
  return {
    DJANGO_SETTINGS_MODULE: env.DJANGO_SETTINGS_MODULE,
    PYTHONPATH: env.PYTHONPATH,
    STITCH_USERDATA: env.STITCH_USERDATA,
    STITCH_VENDOR_PATH: env.STITCH_VENDOR_PATH,
    STITCH_PORT: env.STITCH_PORT,
    PATH: env.PATH,
  }
}

async function findFreePort(startPort) {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.listen(startPort, '127.0.0.1', () => {
      const port = server.address().port
      server.close(() => resolve(port))
    })
    server.on('error', () => resolve(findFreePort(startPort + 1)))
  })
}

async function waitForDjango(port, retries = DJANGO_STARTUP_RETRIES) {
  for (let i = 0; i < retries; i++) {
    try {
      await new Promise((resolve, reject) => {
        const socket = new net.Socket()
        socket.setTimeout(300)
        socket.connect(port, '127.0.0.1', () => { socket.destroy(); resolve() })
        socket.on('error', reject)
        socket.on('timeout', reject)
      })
      log('Django port responded', { port, attempt: i + 1 })
      return true
    } catch {
      await new Promise(r => setTimeout(r, DJANGO_RETRY_INTERVAL_MS))
    }
  }
  lastBackendError = `Timeout: Django n'a pas répondu sur 127.0.0.1:${port}.`
  log('Django startup timeout', { port, retries, logFilePath })
  return false
}

// ── Démarrage Django ──────────────────────────────────────────────────────────

function startDjango(port) {
  const env = getBackendEnv(port)
  const backend = getBackendExecutable()
  const command = backend
    ? {
        command: backend,
        args: ['--port', String(port)],
        cwd: path.dirname(backend),
        mode: 'pyinstaller',
      }
    : getBackendCommand(['runserver', `127.0.0.1:${port}`, '--noreload'])

  log('Starting Django backend', {
    mode: command.mode,
    command: command.command,
    args: command.args,
    cwd: command.cwd,
    appRootPath: getAppRootPath(),
    resourcesPath: getResourcesPath(),
    userDataPath: app.getPath('userData'),
    logFilePath,
    env: usefulEnv(env),
  })

  djangoProcess = spawn(command.command, command.args, {
    cwd: command.cwd,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  djangoProcess.stdout.on('data', (d) => {
    const text = String(d).trimEnd()
    if (text) log('[Django stdout]', { text })
  })
  djangoProcess.stderr.on('data', (d) => {
    const text = String(d).trimEnd()
    if (text) {
      lastBackendError = text.slice(-1000)
      log('[Django stderr]', { text })
    }
  })
  djangoProcess.on('error', (err) => {
    logError('Django spawn failed', err)
  })
  djangoProcess.on('exit', (code, signal) => {
    log('Django backend exited', { code, signal })
    if (code !== 0) {
      lastBackendError = `Le serveur backend a quitté avec le code ${code ?? 'inconnu'}${signal ? ` (${signal})` : ''}.`
    }
  })
}

// ── Migration Django au premier lancement ─────────────────────────────────────

function runMigrations() {
  const env = getBackendEnv()
  const backend = getBackendExecutable()
  const command = backend
    ? {
        command: backend,
        args: ['--migrate'],
        cwd: path.dirname(backend),
        mode: 'pyinstaller',
      }
    : getBackendCommand(['migrate', '--run-syncdb', '--noinput'])

  try {
    log('Running migrations', {
      mode: command.mode,
      command: command.command,
      args: command.args,
      cwd: command.cwd,
      env: usefulEnv(env),
    })
    const output = execFileSync(command.command, command.args, {
      cwd: command.cwd,
      env,
      encoding: 'utf8',
      timeout: 60000,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    log('Migrations completed', { output: output.slice(-4000) })
  } catch (e) {
    logError('Migrations failed; continuing to backend startup', e)
  }
}

// ── Fenêtre principale ────────────────────────────────────────────────────────

function createWindow(port) {
  const appRootPath = getAppRootPath()
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'StitchFlow',
    backgroundColor: '#F8F3EB',
    icon: path.join(appRootPath, 'assets', 'brand', 'icon-256.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  mainWindow.loadFile(path.join(__dirname, 'splash.html'))

  mainWindow.on('closed', () => { mainWindow = null })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    try {
      const parsed = new URL(url)
      if (!url.startsWith('http://127.0.0.1') && ['https:', 'http:'].includes(parsed.protocol)) {
        shell.openExternal(url)
      }
    } catch {}
    return { action: 'deny' }
  })

  buildMenu(port)
}

function loadStartupError() {
  if (!mainWindow) return
  const errorUrl = new URL(`file://${path.join(__dirname, 'error.html')}`)
  errorUrl.searchParams.set('log', logFilePath || '')
  errorUrl.searchParams.set('reason', lastBackendError || '')
  mainWindow.loadURL(errorUrl.toString())
}

function buildMenu(port) {
  const isMac = process.platform === 'darwin'
  const template = [
    ...(isMac ? [{ role: 'appMenu' }] : []),
    {
      label: 'Fichier',
      submenu: [isMac ? { role: 'close' } : { role: 'quit' }],
    },
    {
      label: 'Affichage',
      submenu: [
        { role: 'reload' },
        ...(!app.isPackaged ? [{ role: 'toggleDevTools' }] : []),
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'Aide',
      submenu: [
        {
          label: 'Guide d\'installation Ink/Stitch',
          click: () => shell.openExternal('https://inkstitch.org/docs/install/'),
        },
        {
          label: 'Ouvrir le dossier des logs',
          click: () => shell.showItemInFolder(logFilePath || ensureLogger()),
        },
        {
          label: 'GitHub',
          click: () => shell.openExternal('https://github.com/Sollvoo/stitchflow'),
        },
      ],
    },
  ]
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

// ── Vérification des dépendances ─────────────────────────────────────────────

function checkDependencies() {
  const env = getBackendEnv()
  const backend = getBackendExecutable()
  const command = backend
    ? {
        command: backend,
        args: ['--check-deps'],
        cwd: path.dirname(backend),
        mode: 'pyinstaller',
      }
    : {
        command: getPythonExecutable(),
        args: [path.join(getAppRootPath(), 'scripts', 'check_deps.py')],
        cwd: getAppRootPath(),
        mode: 'python-dev',
      }

  try {
    log('Checking desktop dependencies', {
      mode: command.mode,
      command: command.command,
      args: command.args,
      cwd: command.cwd,
    })
    const result = execFileSync(command.command, command.args, {
      cwd: command.cwd,
      env,
      timeout: 15000,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    const deps = JSON.parse(result)
    log('Dependency check completed', deps)
    return deps
  } catch (e) {
    if (e.stdout) {
      try {
        const deps = JSON.parse(e.stdout)
        log('Dependency check completed with warnings', deps)
        return deps
      } catch {}
    }
    logError('Dependency check failed', e)
    return null
  }
}

function showInkstitchMissingDialog() {
  dialog.showMessageBoxSync({
    type: 'warning',
    title: 'Ink/Stitch non trouvé',
    message: 'Ink/Stitch n\'est pas installé',
    detail: [
      'StitchFlow nécessite l\'extension Ink/Stitch pour convertir vos fichiers en broderie.',
      '',
      'Pour l\'installer :',
      '1. Téléchargez Inkscape depuis inkscape.org',
      '2. Installez l\'extension Ink/Stitch depuis inkstitch.org/docs/install/',
      '',
      `Log de démarrage : ${logFilePath || ensureLogger()}`,
    ].join('\n'),
    buttons: ['Ouvrir le guide d\'installation', 'Continuer sans Ink/Stitch'],
    defaultId: 0,
  })
  shell.openExternal('https://inkstitch.org/docs/install/')
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

function setupAutoUpdater() {
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = true

  autoUpdater.on('update-available', (info) => {
    dialog.showMessageBox({
      type: 'info',
      title: 'Mise à jour disponible',
      message: `StitchFlow ${info.version} est disponible.`,
      detail: 'Voulez-vous télécharger la mise à jour ? Elle sera installée au prochain redémarrage.',
      buttons: ['Télécharger', 'Plus tard'],
      defaultId: 0,
    }).then(({ response }) => {
      if (response === 0) autoUpdater.downloadUpdate()
    })
  })

  autoUpdater.on('update-downloaded', () => {
    dialog.showMessageBox({
      type: 'info',
      title: 'Mise à jour prête',
      message: 'La mise à jour a été téléchargée.',
      detail: 'StitchFlow va redémarrer pour appliquer la mise à jour.',
      buttons: ['Redémarrer maintenant', 'Plus tard'],
      defaultId: 0,
    }).then(({ response }) => {
      if (response === 0) autoUpdater.quitAndInstall()
    })
  })

  autoUpdater.on('error', (err) => {
    logError('Auto-updater failed', err)
  })

  autoUpdater.checkForUpdates()
}

app.whenReady().then(async () => {
  ensureLogger()
  log('StitchFlow Electron startup', {
    isPackaged: app.isPackaged,
    platform: process.platform,
    arch: process.arch,
    appPath: app.getAppPath(),
    resourcesPath: getResourcesPath(),
    userDataPath: app.getPath('userData'),
    logFilePath,
    backendExecutable: getBackendExecutable(),
  })

  if (!app.isPackaged && process.platform === 'darwin') {
    const iconPath = path.join(__dirname, '..', 'assets', 'brand', 'icon-256.png')
    if (fs.existsSync(iconPath)) app.dock.setIcon(iconPath)
  }

  djangoPort = await findFreePort(DJANGO_DEFAULT_PORT)
  log('Selected Django port', { djangoPort })

  const deps = checkDependencies()
  if (deps && !deps.inkstitch?.found) {
    showInkstitchMissingDialog()
  }

  runMigrations()
  startDjango(djangoPort)
  createWindow(djangoPort)

  const ready = await waitForDjango(djangoPort)
  if (ready && mainWindow) {
    mainWindow.loadURL(`http://127.0.0.1:${djangoPort}/`)
  } else if (mainWindow) {
    loadStartupError()
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow(djangoPort)
  })

  if (app.isPackaged) setupAutoUpdater()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  log('StitchFlow Electron quitting')
  if (djangoProcess) {
    djangoProcess.kill('SIGTERM')
    djangoProcess = null
  }
})
