const { app, BrowserWindow, dialog, shell, Menu } = require('electron')
const { spawn, execFileSync } = require('child_process')
const path = require('path')
const net = require('net')
const fs = require('fs')
const { autoUpdater } = require('electron-updater')

const DJANGO_DEFAULT_PORT = 8765
const DJANGO_STARTUP_RETRIES = 60
const DJANGO_RETRY_INTERVAL_MS = 500

let djangoProcess = null
let mainWindow = null
let djangoPort = DJANGO_DEFAULT_PORT

// ── Utilitaires ──────────────────────────────────────────────────────────────

function getResourcesPath() {
  return app.isPackaged
    ? path.join(process.resourcesPath)
    : path.join(__dirname, '..')
}

function getAppRootPath() {
  return app.isPackaged
    ? app.getAppPath()
    : path.join(__dirname, '..')
}

function getPythonExecutable() {
  const resourcesPath = getResourcesPath()
  const appRootPath = getAppRootPath()
  const venvPython = path.join(resourcesPath, '.venv', 'bin', 'python3')
  const venvPythonWin = path.join(resourcesPath, '.venv', 'Scripts', 'python.exe')
  const devVenvPython = path.join(appRootPath, '.venv', 'bin', 'python3')
  const devVenvPythonWin = path.join(appRootPath, '.venv', 'Scripts', 'python.exe')
  const macCandidates = [
    '/opt/homebrew/bin/python3',
    '/usr/local/bin/python3',
    '/usr/bin/python3',
  ]

  if (process.platform === 'win32' && fs.existsSync(venvPythonWin)) return venvPythonWin
  if (process.platform === 'win32' && fs.existsSync(devVenvPythonWin)) return devVenvPythonWin
  if (fs.existsSync(venvPython)) return venvPython
  if (fs.existsSync(devVenvPython)) return devVenvPython
  if (process.platform === 'darwin') {
    const found = macCandidates.find((candidate) => fs.existsSync(candidate))
    if (found) return found
  }
  return 'python3'
}

function getVendorPath() {
  const resourcesPath = getResourcesPath()
  const appRootPath = getAppRootPath()
  return app.isPackaged
    ? path.join(process.resourcesPath, 'vendor')
    : path.join(appRootPath, 'vendor')
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
      return true
    } catch {
      await new Promise(r => setTimeout(r, DJANGO_RETRY_INTERVAL_MS))
    }
  }
  return false
}

// ── Démarrage Django ──────────────────────────────────────────────────────────

function startDjango(port) {
  const appRootPath = getAppRootPath()
  const srcPath = path.join(appRootPath, 'src')
  const userDataPath = app.getPath('userData')
  const python = getPythonExecutable()
  const vendorPath = getVendorPath()

  const env = {
    ...process.env,
    DJANGO_SETTINGS_MODULE: 'stitchflow.settings_desktop',
    PYTHONPATH: srcPath,
    STITCH_USERDATA: userDataPath,
    STITCH_VENDOR_PATH: vendorPath,
    STITCH_PORT: String(port),
    PYTHONUNBUFFERED: '1',
  }

  const managePy = path.join(srcPath, 'manage.py')
  djangoProcess = spawn(python, [managePy, 'runserver', `127.0.0.1:${port}`, '--noreload'], {
    cwd: srcPath,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  djangoProcess.stdout.on('data', (d) => {
    if (process.env.DEBUG_DJANGO) process.stdout.write('[Django] ' + d)
  })
  djangoProcess.stderr.on('data', (d) => {
    if (process.env.DEBUG_DJANGO) process.stderr.write('[Django] ' + d)
  })
  djangoProcess.on('exit', (code) => {
    if (code !== 0 && mainWindow) {
      mainWindow.webContents.executeJavaScript(
        `document.body.innerHTML = '<div style="font-family:sans-serif;padding:40px;color:#c00"><h2>StitchFlow a rencontré une erreur</h2><p>Le serveur backend a quitté avec le code ${code}.</p><p>Relancez l\'application.</p></div>'`
      )
    }
  })
}

// ── Migration Django au premier lancement ─────────────────────────────────────

function runMigrations() {
  const appRootPath = getAppRootPath()
  const srcPath = path.join(appRootPath, 'src')
  const userDataPath = app.getPath('userData')
  const python = getPythonExecutable()
  const vendorPath = getVendorPath()

  const env = {
    ...process.env,
    DJANGO_SETTINGS_MODULE: 'stitchflow.settings_desktop',
    PYTHONPATH: srcPath,
    STITCH_USERDATA: userDataPath,
    STITCH_VENDOR_PATH: vendorPath,
  }

  try {
    const managePy = path.join(srcPath, 'manage.py')
    execFileSync(python, [managePy, 'migrate', '--run-syncdb'], {
      cwd: srcPath,
      env,
      stdio: 'ignore',
      timeout: 30000,
    })
  } catch (e) {
    // Non-bloquant : on continue si les migrations échouent (DB déjà à jour)
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

  // Splash screen pendant le chargement
  mainWindow.loadFile(path.join(__dirname, 'splash.html'))

  mainWindow.on('closed', () => { mainWindow = null })

  // Ouvrir les liens externes dans le navigateur par défaut (https:// et http:// uniquement)
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
          label: 'GitHub',
          click: () => shell.openExternal('https://github.com/Sollvoo/stitchflow-desktop'),
        },
      ],
    },
  ]
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

// ── Vérification des dépendances ─────────────────────────────────────────────

function checkDependencies() {
  const appRootPath = getAppRootPath()
  const python = getPythonExecutable()
  const checkScript = path.join(appRootPath, 'scripts', 'check_deps.py')

  try {
    const result = execFileSync(python, [checkScript], {
      timeout: 10000,
      encoding: 'utf8',
    })
    return JSON.parse(result)
  } catch (e) {
    // check_deps.py peut retourner exit code 1 même avec output JSON valide
    if (e.stdout) {
      try { return JSON.parse(e.stdout) } catch {}
    }
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
      'Vous pourrez utiliser StitchFlow après l\'installation.',
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
    if (process.env.DEBUG_DJANGO) console.error('[updater]', err.message)
  })

  autoUpdater.checkForUpdates()
}

app.whenReady().then(async () => {
  // Icône dock en mode dev (packagé : l'icône vient du bundle .app)
  if (!app.isPackaged && process.platform === 'darwin') {
    const iconPath = path.join(__dirname, '..', 'assets', 'brand', 'icon-256.png')
    if (fs.existsSync(iconPath)) app.dock.setIcon(iconPath)
  }

  djangoPort = await findFreePort(DJANGO_DEFAULT_PORT)

  // Vérifier les dépendances
  const deps = checkDependencies()
  if (deps && !deps.inkstitch?.found) {
    showInkstitchMissingDialog()
  }

  // Migrations au premier lancement
  runMigrations()

  // Lancer Django
  startDjango(djangoPort)

  // Créer la fenêtre avec splash screen
  createWindow(djangoPort)

  // Attendre que Django réponde
  const ready = await waitForDjango(djangoPort)
  if (ready && mainWindow) {
    mainWindow.loadURL(`http://127.0.0.1:${djangoPort}/`)
  } else if (mainWindow) {
    mainWindow.loadFile(path.join(__dirname, 'error.html'))
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow(djangoPort)
  })

  // Vérifier les mises à jour uniquement dans l'app packagée
  if (app.isPackaged) setupAutoUpdater()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  if (djangoProcess) {
    djangoProcess.kill('SIGTERM')
    djangoProcess = null
  }
})
