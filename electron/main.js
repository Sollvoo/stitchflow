const { app, BrowserWindow, dialog, shell, Menu, session } = require('electron')
const { spawn, execFileSync } = require('child_process')
const http = require('http')
const path = require('path')
const net = require('net')
const fs = require('fs')
const { autoUpdater } = require('electron-updater')

const DJANGO_DEFAULT_PORT = 8765
const DJANGO_BIND_HOST = '127.0.0.1'
const DJANGO_BROWSER_HOST = 'stitchflow.localhost'
const DJANGO_STARTUP_RETRIES = 120
const DJANGO_RETRY_INTERVAL_MS = 500
const INSTALL_GUIDE_URL = 'https://sollvoo.github.io/stitchflow/#prerequis'

app.commandLine.appendSwitch('host-resolver-rules', `MAP ${DJANGO_BROWSER_HOST} ${DJANGO_BIND_HOST}`)
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
  const vendorPath = getVendorPath()
  const popplerMacosBin = path.join(vendorPath, 'poppler-macos', 'bin')
  const popplerMacosLib = path.join(vendorPath, 'poppler-macos', 'lib')
  const env = {
    ...process.env,
    DJANGO_SETTINGS_MODULE: 'stitchflow.settings_desktop',
    PYTHONPATH: srcPath,
    STITCH_USERDATA: app.getPath('userData'),
    STITCH_VENDOR_PATH: vendorPath,
    PYTHONUNBUFFERED: '1',
  }
  if (process.platform === 'darwin' && fs.existsSync(popplerMacosBin)) {
    env.PATH = `${popplerMacosBin}:${env.PATH || ''}`
    if (fs.existsSync(popplerMacosLib)) {
      env.DYLD_FALLBACK_LIBRARY_PATH = [
        popplerMacosLib,
        env.DYLD_FALLBACK_LIBRARY_PATH,
      ].filter(Boolean).join(':')
    }
  }
  if (port) env.STITCH_PORT = String(port)
  return env
}

function getDjangoBrowserUrl(port) {
  return `http://${DJANGO_BROWSER_HOST}:${port}/`
}

function usefulEnv(env) {
  return {
    DJANGO_SETTINGS_MODULE: env.DJANGO_SETTINGS_MODULE,
    PYTHONPATH: env.PYTHONPATH,
    STITCH_USERDATA: env.STITCH_USERDATA,
    STITCH_VENDOR_PATH: env.STITCH_VENDOR_PATH,
    STITCH_PORT: env.STITCH_PORT,
    DYLD_FALLBACK_LIBRARY_PATH: env.DYLD_FALLBACK_LIBRARY_PATH,
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

async function requestLocalDjango(port, pathname) {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: '127.0.0.1',
      port,
      path: pathname,
      method: 'GET',
      timeout: 2000,
    }, (res) => {
      let body = ''
      res.setEncoding('utf8')
      res.on('data', chunk => { body += chunk })
      res.on('end', () => resolve({
        statusCode: res.statusCode,
        headers: res.headers,
        body: body.slice(0, 2000),
      }))
    })
    req.on('timeout', () => {
      req.destroy(new Error(`HTTP timeout on ${pathname}`))
    })
    req.on('error', reject)
    req.end()
  })
}

async function waitForDjangoHttp(port, retries = DJANGO_STARTUP_RETRIES) {
  for (let i = 0; i < retries; i++) {
    try {
      const health = await requestLocalDjango(port, '/healthz/')
      const home = await requestLocalDjango(port, '/')
      log('Django HTTP probe', {
        port,
        attempt: i + 1,
        healthStatus: health.statusCode,
        homeStatus: home.statusCode,
        homeLocation: home.headers.location,
        homePreview: home.body.slice(0, 300),
      })

      if (health.statusCode === 200 && home.statusCode === 200) {
        return true
      }

      lastBackendError = `Django a répondu, mais la page principale retourne HTTP ${home.statusCode}${home.headers.location ? ` vers ${home.headers.location}` : ''}.`
    } catch (err) {
      lastBackendError = err.message
    }
    await new Promise(r => setTimeout(r, DJANGO_RETRY_INTERVAL_MS))
  }

  log('Django HTTP readiness timeout', { port, retries, lastBackendError })
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

  mainWindow.webContents.on('did-start-loading', () => {
    log('Window did-start-loading', { url: mainWindow.webContents.getURL() })
  })
  mainWindow.webContents.on('did-finish-load', () => {
    log('Window did-finish-load', { url: mainWindow.webContents.getURL() })
  })
  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
    lastBackendError = `${errorDescription} (${errorCode})`
    log('Window did-fail-load', { errorCode, errorDescription, validatedURL, isMainFrame })
  })
  mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    log('Window console-message', { level, message, line, sourceId })
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    try {
      const parsed = new URL(url)
      const isLocalDjango =
        ['127.0.0.1', 'localhost', DJANGO_BROWSER_HOST].includes(parsed.hostname) &&
        parsed.port === String(port)
      if (!isLocalDjango && ['https:', 'http:'].includes(parsed.protocol)) {
        shell.openExternal(url)
      }
    } catch {}
    return { action: 'deny' }
  })

  buildMenu(port)
}

function setupLocalNavigationGuard(port) {
  session.defaultSession.webRequest.onBeforeRequest({
    urls: [
      `https://127.0.0.1:${port}/*`,
      `https://localhost:${port}/*`,
      `https://${DJANGO_BROWSER_HOST}:${port}/*`,
    ],
  }, (details, callback) => {
    const redirected = details.url
      .replace(/^https:\/\/127\.0\.0\.1:/, `http://${DJANGO_BROWSER_HOST}:`)
      .replace(/^https:\/\/localhost:/, `http://${DJANGO_BROWSER_HOST}:`)
      .replace(new RegExp(`^https://${DJANGO_BROWSER_HOST.replace('.', '\\.')}:`), `http://${DJANGO_BROWSER_HOST}:`)
    log('Rewriting local HTTPS navigation to HTTP', { from: details.url, to: redirected })
    callback({ redirectURL: redirected })
  })
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
          label: 'Guide d\'installation',
          click: () => shell.openExternal(INSTALL_GUIDE_URL),
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
  const selected = dialog.showMessageBoxSync({
    type: 'warning',
    title: 'Ink/Stitch non trouvé',
    message: 'Inkscape ou Ink/Stitch n\'est pas installé',
    detail: [
      'StitchFlow nécessite Inkscape et l\'extension Ink/Stitch pour convertir vos fichiers en broderie.',
      '',
      'Pour l\'installer :',
      '1. Installez Inkscape, ouvrez-le une première fois, puis fermez-le.',
      '2. Installez Ink/Stitch.',
      '3. Relancez StitchFlow et lancez votre conversion.',
      '',
      `Log de démarrage : ${logFilePath || ensureLogger()}`,
    ].join('\n'),
    buttons: ['Ouvrir le guide d\'installation', 'Continuer sans Ink/Stitch'],
    defaultId: 0,
  })
  if (selected === 0) {
    shell.openExternal(INSTALL_GUIDE_URL)
  }
}

function showPdfDepsMissingDialog(deps) {
  const missing = []
  if (deps && deps.poppler && !deps.poppler.found) missing.push(deps.poppler.message || 'Poppler introuvable')
  if (deps && deps.pdf2image && !deps.pdf2image.found) missing.push(deps.pdf2image.message || 'pdf2image introuvable')
  if (!missing.length) return

  dialog.showMessageBoxSync({
    type: 'warning',
    title: 'PDF partiellement indisponible',
    message: 'Les conversions PDF nécessitent Poppler',
    detail: [
      ...missing,
      '',
      'SVG, PNG, JPEG et WebP restent utilisables.',
      'Pour activer les PDF, installez Poppler ou utilisez une version qui embarque les binaires PDF.',
      '',
      `Log de démarrage : ${logFilePath || ensureLogger()}`,
    ].join('\n'),
    buttons: ['OK'],
    defaultId: 0,
  })
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
  if (deps && (deps.poppler?.found === false || deps.pdf2image?.found === false)) {
    showPdfDepsMissingDialog(deps)
  }

  runMigrations()
  startDjango(djangoPort)
  setupLocalNavigationGuard(djangoPort)
  createWindow(djangoPort)

  const ready = await waitForDjango(djangoPort)
  const httpReady = ready ? await waitForDjangoHttp(djangoPort) : false
  if (ready && httpReady && mainWindow) {
    mainWindow.loadURL(getDjangoBrowserUrl(djangoPort))
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
