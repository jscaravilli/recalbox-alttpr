const { app, BrowserWindow, ipcMain, globalShortcut, dialog } = require('electron');
const https = require('https');
const path = require('path');
const url  = require('url');
const fs   = require('fs');
const Store = require('electron-store');

const store = new Store();

let launcherWin   = null;
let itemWin       = null;
let mapWin        = null;
let timerWin      = null;
let broadcastWin      = null;
let checklistWin      = null;
let bcastSettingsWin  = null;
let broadcastBg   = 'black';
let timerBg       = 'black';
let itemTrackerBg = 'black';

function findAppRoot() {
  const candidates = [
    __dirname,
    path.join(process.resourcesPath, 'app'),
    path.join(process.resourcesPath),
  ];
  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, 'items'))) {
      console.log('App root found:', dir);
      return dir;
    }
  }
  console.warn('Could not find items/ folder. Falling back to __dirname:', __dirname);
  return __dirname;
}

let APP_ROOT = null;

function getRoot() {
  if (!APP_ROOT) APP_ROOT = findAppRoot();
  return APP_ROOT;
}

function toFileUrl(rel) {
  return url.pathToFileURL(path.join(getRoot(), rel)).href;
}

// ── Launcher ──────────────────────────────────────────────────────────────────
function createLauncher() {
  launcherWin = new BrowserWindow({
    width: 580, height: 920,
    minWidth: 580, minHeight: 700,
    resizable: false,
    useContentSize: true,
    title: 'Hutch-ALTTPR Tracker',
    backgroundColor: '#0d0d0d',
    webPreferences: {
      preload: path.join(getRoot(), 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,
    }
  });
  launcherWin.setMenuBarVisibility(false);
  launcherWin.loadURL(toFileUrl('index.html'));
  launcherWin.on('closed', () => {
    launcherWin = null;
    if (itemWin && !itemWin.isDestroyed()) itemWin.close();
    if (mapWin  && !mapWin.isDestroyed())  mapWin.close();
  });
}

// ── Item Tracker ──────────────────────────────────────────────────────────────
function createItemTrackerWindow(scale, wsHost, wsPort, bg, dungeonItems, bossShuffle, bounds) {
  const s = parseFloat(scale) || 1.0;
  const isTransparent = bg === 'transparent';
  const bgColors = { black: '#000000', white: '#ffffff', grey: '#2a2a2a', transparent: '#00000000' };
  const opts = {
    width:  (bounds && bounds.width)  || Math.ceil(480 * s),
    height: (bounds && bounds.height) || Math.ceil(620 * s),
    resizable: true,
    useContentSize: true,
    title: 'Item Tracker',
    backgroundColor: isTransparent ? undefined : (bgColors[bg] || '#000000'),
    transparent: isTransparent,
    titleBarStyle: isTransparent ? (process.platform === 'darwin' ? 'hiddenInset' : 'hidden') : 'default',
    titleBarOverlay: isTransparent && process.platform !== 'darwin' ? {
      color: '#00000000',
      symbolColor: '#ffffff',
      height: 30
    } : false,
    hasShadow: true,
    webPreferences: {
      preload: path.join(getRoot(), 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,
    }
  };
  if (bounds && bounds.x !== undefined && bounds.y !== undefined) {
    opts.x = bounds.x;
    opts.y = bounds.y;
  }
  itemWin = new BrowserWindow(opts);
  itemWin.setMenuBarVisibility(false);
  const q = `?scale=${s}&wshost=${wsHost||'localhost'}&wsport=${wsPort||23074}&bg=${bg||'black'}&dungeonitems=${dungeonItems||'standard'}&bossshuffle=${bossShuffle||'yes'}`;
  itemWin.loadURL(toFileUrl('itemtracker.html') + q);
  itemWin.on('closed', () => { itemWin = null; });
  itemTrackerBg = bg || 'black';
}

function openItemTracker(scale, wsHost, wsPort, bg, dungeonItems, bossShuffle) {
  if (itemWin && !itemWin.isDestroyed()) { itemWin.focus(); return; }
  createItemTrackerWindow(scale, wsHost, wsPort, bg, dungeonItems, bossShuffle);
}

// ── Map ───────────────────────────────────────────────────────────────────────
function openMap(zoom, layout, enemizer, gtCrystals, wsHost, wsPort, gamemode, dungeonItems, swordless, bossShuffle, entranceShuffle, entranceMode) {
  if (mapWin && !mapWin.isDestroyed()) { mapWin.focus(); return; }
  const pct = parseInt(zoom) || 100;
  const size = Math.round(512 * pct / 100);
  const isVert = layout === 'vertical';
  mapWin = new BrowserWindow({
    width:  isVert ? size + 60 : size * 2 + 80,
    height: isVert ? size * 2 + 360 : size + 360,
    resizable: true,
    useContentSize: true,
    title: 'Map',
    backgroundColor: '#0d0d0d',
    webPreferences: {
      preload: path.join(getRoot(), 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,
      // The map is often left visible while the user focuses on the game —
      // disable Chromium's background throttling so auto-tracker updates
      // keep painting at full speed even when this window isn't focused.
      backgroundThrottling: false,
    }
  });
  mapWin.setMenuBarVisibility(false);
  const q = `?zoom=${pct}&layout=${layout||'horizontal'}&enemizer=${enemizer||'yes'}&gtcrystals=${gtCrystals||7}&wshost=${wsHost||'localhost'}&wsport=${wsPort||23074}&gamemode=${gamemode||'standard'}&dungeonitems=${dungeonItems||'standard'}&swordless=${swordless||'no'}&bossshuffle=${bossShuffle||'yes'}&entranceshuffle=${entranceShuffle||'no'}&entrancemode=${entranceMode||'none'}`;
  mapWin.loadURL(toFileUrl('map.html') + q);
  mapWin.on('closed', () => { mapWin = null; });
}

// ── Timer window ──────────────────────────────────────────────────────────────
function createTimerWindow(wsHost, wsPort, color, bg, bounds) {
  const isTransparent = bg === 'transparent';
  const bgColors = { black: '#000000', white: '#ffffff', grey: '#2a2a2a', transparent: '#00000000' };
  const opts = {
    width:  (bounds && bounds.width)  || 300,
    height: (bounds && bounds.height) || 220,
    resizable: true,
    useContentSize: true,
    title: 'Timer',
    backgroundColor: isTransparent ? undefined : (bgColors[bg] || '#000000'),
    transparent: isTransparent,
    titleBarStyle: isTransparent ? (process.platform === 'darwin' ? 'hiddenInset' : 'hidden') : 'default',
    titleBarOverlay: isTransparent && process.platform !== 'darwin' ? {
      color: '#00000000',
      symbolColor: '#ffffff',
      height: 30
    } : false,
    hasShadow: true,
    webPreferences: {
      preload:          path.join(getRoot(), 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
      webSecurity:      false,
      // Critical: the timer's centisecond setInterval is clamped by Chromium
      // to ~1s when backgrounded. Without this the timer drifts massively
      // slow whenever the user focuses the game / OBS / another window.
      backgroundThrottling: false,
    }
  };
  if (bounds && bounds.x !== undefined && bounds.y !== undefined) {
    opts.x = bounds.x;
    opts.y = bounds.y;
  }
  timerWin = new BrowserWindow(opts);
  timerWin.setMenuBarVisibility(false);
  const q = `?wshost=${wsHost||'localhost'}&wsport=${wsPort||23074}&color=${color||'blue'}&bg=${bg||'black'}`;
  timerWin.loadURL(toFileUrl('timer.html') + q);
  timerWin.on('closed', () => { timerWin = null; });
  timerBg = bg || 'black';
}

function openTimer(wsHost, wsPort, color, bg) {
  if (timerWin && !timerWin.isDestroyed()) { timerWin.focus(); return; }
  createTimerWindow(wsHost, wsPort, color, bg);
}

// ── Broadcast window ──────────────────────────────────────────────────────────
function createBroadcastWindow(bg, bounds) {
  const root = getRoot();
  const isTransparent = bg === 'transparent';
  const bgColors = { black: '#000000', white: '#ffffff', grey: '#2a2a2a', transparent: '#00000000' };
  const opts = {
    width:  (bounds && bounds.width)  || 500,
    height: (bounds && bounds.height) || (process.platform === 'win32' ? 220 : 250),
    resizable: true,
    useContentSize: true,
    title: 'ALTTP Broadcast View',
    backgroundColor: isTransparent ? undefined : (bgColors[bg] || '#000000'),
    transparent: isTransparent,
    titleBarStyle: isTransparent ? (process.platform === 'darwin' ? 'hiddenInset' : 'hidden') : 'default',
    titleBarOverlay: isTransparent && process.platform !== 'darwin' ? {
      color: '#00000000',
      symbolColor: '#ffffff',
      height: 30
    } : false,
    hasShadow: true,
    webPreferences: {
      preload: path.join(root, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,
      // Keep timers, BroadcastChannel callbacks, and paints running at full
      // speed even when the window is hidden behind OBS / the game window.
      // Without this, Chromium throttles backgrounded windows aggressively
      // and the broadcast view will stop updating until brought to focus.
      backgroundThrottling: false,
    },
  };
  if (bounds && bounds.x !== undefined && bounds.y !== undefined) {
    opts.x = bounds.x;
    opts.y = bounds.y;
  }
  broadcastWin = new BrowserWindow(opts);
  broadcastWin.setMenuBarVisibility(false);
  // Premium broadcast: check userData path first (survives upgrades), then app folder, then default
  const premiumUserData = path.join(app.getPath('userData'), 'premium', 'broadcast.html');
  const premiumApp      = path.join(root, 'premium', 'broadcast.html');
  const broadcastFile   = fs.existsSync(premiumUserData) ? premiumUserData
                        : fs.existsSync(premiumApp)      ? premiumApp
                        : path.join(root, 'broadcast.html');
  const appRootUrl = url.pathToFileURL(root).href;
  broadcastWin.loadFile(broadcastFile, { query: { bg, approot: appRootUrl } });
  broadcastWin.on('closed', () => { broadcastWin = null; });
  broadcastBg = bg;
}

function openBroadcast(bg) {
  if (broadcastWin && !broadcastWin.isDestroyed()) { broadcastWin.focus(); return; }
  createBroadcastWindow(bg);
}

// ── Check List window ─────────────────────────────────────────────────────────
function openCheckList() {
  if (checklistWin && !checklistWin.isDestroyed()) { checklistWin.focus(); return; }
  checklistWin = new BrowserWindow({
    width: 350,
    height: 900,
    resizable: true,
    useContentSize: true,
    title: 'Check List',
    backgroundColor: '#111111',
    alwaysOnTop: true,
    webPreferences: {
      preload: path.join(getRoot(), 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,
      backgroundThrottling: false,
    }
  });
  checklistWin.setMenuBarVisibility(false);
  checklistWin.loadURL(toFileUrl('checklist.html'));
  checklistWin.on('closed', () => { checklistWin = null; });
}

// ── IPC ───────────────────────────────────────────────────────────────────────
ipcMain.on('launch', (event, opts) => {
  store.set('settings', opts);
  if (opts.which === 'items' || opts.which === 'both') openItemTracker(opts.scale, opts.wsHost, opts.wsPort, opts.trackerBg, opts.dungeonItems, opts.bossshuffle);
  if (opts.which === 'map'   || opts.which === 'both') openMap(opts.zoom, opts.layout, opts.enemizer, opts.gtCrystals, opts.wsHost, opts.wsPort, opts.gamemode, opts.dungeonItems, opts.swordless, opts.bossshuffle, (opts.entranceShuffle && opts.entranceShuffle !== 'none') ? 'yes' : 'no', opts.entranceShuffle || 'none');
  if (opts.which === 'timer') openTimer(opts.wsHost, opts.wsPort, opts.timerColor, opts.timerBg);
  if (opts.which === 'broadcast') openBroadcast(opts.trackerBg || 'black');
  if (opts.which === 'checklist') openCheckList();
});

ipcMain.on('open-checklist', () => openCheckList());

ipcMain.handle('load-settings', () => store.get('settings', {}));


ipcMain.handle('get-paths', () => {
  const root = getRoot();
  return {
    root,
    itemsUrl:    url.pathToFileURL(path.join(root, 'items')).href,
    mapUrl:      url.pathToFileURL(path.join(root, 'map')).href,
    itemsExists: fs.existsSync(path.join(root, 'items')),
  };
});

ipcMain.handle('set-broadcast-bg', (event, bg) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (!win) return;
  // Only the broadcast window participates in this handler.
  if (broadcastWin !== win) return;

  const wasTransparent  = broadcastBg === 'transparent';
  const willBeTransparent = bg === 'transparent';

  // Electron does not allow toggling the `transparent` flag after a window is
  // created. To switch in or out of transparent mode we need to recreate the
  // window, preserving its current bounds so the user does not lose position.
  if (wasTransparent !== willBeTransparent) {
    const bounds = win.getBounds();
    setImmediate(() => {
      if (broadcastWin === win) broadcastWin = null;
      if (!win.isDestroyed()) win.close();
      createBroadcastWindow(bg, bounds);
    });
    return;
  }

  // Same transparency mode — just swap the solid background color.
  const bgColors = { black: '#000000', white: '#ffffff', grey: '#2a2a2a', image: '#000000' };
  if (bgColors[bg]) win.setBackgroundColor(bgColors[bg]);
  broadcastBg = bg;
});

ipcMain.handle('set-timer-bg', (event, bg) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (!win || timerWin !== win) return;

  const wasTransparent  = timerBg === 'transparent';
  const willBeTransparent = bg === 'transparent';

  // Toggling transparency requires a window recreate (Electron limitation).
  if (wasTransparent !== willBeTransparent) {
    const bounds = win.getBounds();
    // Pull current ws/color from the window URL so the recreate matches.
    const currentUrl = new URL(win.webContents.getURL());
    const wsHost = currentUrl.searchParams.get('wshost') || 'localhost';
    const wsPort = currentUrl.searchParams.get('wsport') || '23074';
    const color  = currentUrl.searchParams.get('color')  || 'blue';
    setImmediate(() => {
      if (timerWin === win) timerWin = null;
      if (!win.isDestroyed()) win.close();
      createTimerWindow(wsHost, wsPort, color, bg, bounds);
    });
    return;
  }

  // Same transparency mode — just swap the solid background color.
  const bgColors = { black: '#000000', white: '#ffffff', grey: '#2a2a2a', custom: '#000000' };
  if (bgColors[bg]) win.setBackgroundColor(bgColors[bg]);
  timerBg = bg;
});

ipcMain.handle('set-itemtracker-bg', (event, bg) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (!win || itemWin !== win) return;

  const wasTransparent    = itemTrackerBg === 'transparent';
  const willBeTransparent = bg === 'transparent';

  // Toggling transparency requires a window recreate (Electron limitation).
  if (wasTransparent !== willBeTransparent) {
    const bounds = win.getBounds();
    // Pull scale / ws / dungeonItems from the window URL so the recreate matches.
    const currentUrl   = new URL(win.webContents.getURL());
    const scale        = currentUrl.searchParams.get('scale')        || '1';
    const wsHost       = currentUrl.searchParams.get('wshost')       || 'localhost';
    const wsPort       = currentUrl.searchParams.get('wsport')       || '23074';
    const dungeonItems = currentUrl.searchParams.get('dungeonitems') || 'standard';
    const bossShuffle  = currentUrl.searchParams.get('bossshuffle')  || 'yes';
    setImmediate(() => {
      if (itemWin === win) itemWin = null;
      if (!win.isDestroyed()) win.close();
      createItemTrackerWindow(scale, wsHost, wsPort, bg, dungeonItems, bossShuffle, bounds);
    });
    return;
  }

  // Same transparency mode — just swap the solid background color.
  // 'image' keeps a black native window colour; the renderer paints the image.
  const bgColors = { black: '#000000', white: '#ffffff', grey: '#2a2a2a', image: '#000000' };
  if (bgColors[bg]) win.setBackgroundColor(bgColors[bg]);
  itemTrackerBg = bg;
});

// ── Update checker (notification-only, no auto-download) ─────────────────────
const CURRENT_VERSION = app.getVersion();
const RELEASES_URL    = 'https://github.com/hutchch/ALTTPR-Tracker/releases';
const API_URL         = 'https://api.github.com/repos/hutchch/ALTTPR-Tracker/releases/latest';

function sendUpdateStatus(status, info) {
  if (launcherWin && !launcherWin.isDestroyed()) {
    launcherWin.webContents.send('update-status', { status, info: info || null });
  }
}

function compareVersions(a, b) {
  const pa = a.replace(/^v/, '').split('.').map(Number);
  const pb = b.replace(/^v/, '').split('.').map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const na = pa[i] || 0, nb = pb[i] || 0;
    if (na > nb) return 1;
    if (na < nb) return -1;
  }
  return 0;
}

function fetchLatestRelease(callback) {
  const opts = {
    hostname: 'api.github.com',
    path:     '/repos/hutchch/ALTTPR-Tracker/releases/latest',
    headers:  { 'User-Agent': 'ALTTPR-Tracker-Updater' },
    timeout:  8000,
  };
  const req = https.get(opts, (res) => {
    if (res.statusCode !== 200) { callback(null); return; }
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
      try {
        const json = JSON.parse(data);
        callback(json.tag_name || null);  // e.g. "v1.1.14"
      } catch(e) { callback(null); }
    });
  });
  req.on('error',   () => callback(null));
  req.on('timeout', () => { req.destroy(); callback(null); });
}

function checkForUpdates() {
  sendUpdateStatus('checking');
  fetchLatestRelease((tagName) => {
    if (!tagName) {
      // No response — network down, API unavailable, etc. Stay quiet.
      sendUpdateStatus('up-to-date');
      return;
    }
    if (compareVersions(tagName, CURRENT_VERSION) > 0) {
      sendUpdateStatus('available', { version: tagName.replace(/^v/, ''), url: RELEASES_URL });
    } else {
      sendUpdateStatus('up-to-date');
    }
  });
}

function openBcastSettingsWindow() {
  if (bcastSettingsWin && !bcastSettingsWin.isDestroyed()) { bcastSettingsWin.focus(); return; }
  const root = getRoot();
  bcastSettingsWin = new BrowserWindow({
    width: 480, height: 620, resizable: true, useContentSize: true,
    title: 'Broadcast Item Sounds', backgroundColor: '#0d0d0d',
    webPreferences: {
      preload: path.join(root, 'preload.js'),
      contextIsolation: true, nodeIntegration: false, webSecurity: false,
    },
  });
  bcastSettingsWin.setMenuBarVisibility(false);
  bcastSettingsWin.loadFile(path.join(root, 'bcast-settings.html'));
  bcastSettingsWin.on('closed', () => { bcastSettingsWin = null; });
}
ipcMain.handle('open-bcast-settings', () => openBcastSettingsWindow());

ipcMain.handle('check-for-updates', () => checkForUpdates());
ipcMain.handle('install-update', () => {
  const { shell } = require('electron');
  shell.openExternal(RELEASES_URL);
});

ipcMain.handle('open-external', (event, url) => {
  const { shell } = require('electron');
  // Only allow http/https URLs to be opened this way.
  if (typeof url === 'string' && /^https?:\/\//i.test(url)) {
    shell.openExternal(url);
  }
});

// ── New Game global hotkey ────────────────────────────────────────────────────
let newgameHotkey = null; // currently registered accelerator string, or null

function fireNewgame() {
  // Send only to itemtracker — resetItemTracker() will BroadcastChannel
  // the newgame event to map and broadcast windows itself.
  if (itemWin && !itemWin.isDestroyed()) {
    itemWin.webContents.send('newgame');
  }
}

ipcMain.handle('register-newgame-hotkey', (event, accelerator) => {
  // Unregister any existing hotkey first
  if (newgameHotkey) {
    globalShortcut.unregister(newgameHotkey);
    newgameHotkey = null;
  }
  try {
    const ok = globalShortcut.register(accelerator, fireNewgame);
    if (ok) { newgameHotkey = accelerator; return { ok: true }; }
    return { ok: false, error: 'Accelerator already in use or invalid' };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

ipcMain.handle('unregister-newgame-hotkey', () => {
  if (newgameHotkey) {
    globalShortcut.unregister(newgameHotkey);
    newgameHotkey = null;
  }
  return { ok: true };
});

// ── Entrance state save / load ────────────────────────────────────────────────
ipcMain.handle('save-ent-state', async (event, json) => {
  const { filePath, canceled } = await dialog.showSaveDialog({
    title: 'Save Entrance State',
    defaultPath: 'alttp-entrance-state.json',
    filters: [{ name: 'JSON', extensions: ['json'] }],
  });
  if (canceled || !filePath) return { ok: false };
  fs.writeFileSync(filePath, json, 'utf8');
  return { ok: true };
});

ipcMain.handle('load-ent-state', async () => {
  const { filePaths, canceled } = await dialog.showOpenDialog({
    title: 'Load Entrance State',
    filters: [{ name: 'JSON', extensions: ['json'] }],
    properties: ['openFile'],
  });
  if (canceled || !filePaths.length) return { ok: false };
  const json = fs.readFileSync(filePaths[0], 'utf8');
  return { ok: true, json };
});

// Clean up on quit
app.on('will-quit', () => { globalShortcut.unregisterAll(); });

// ── Lifecycle ─────────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  console.log('__dirname        :', __dirname);
  console.log('resourcesPath    :', process.resourcesPath);
  console.log('appRoot          :', getRoot());
  createLauncher();
  // Check for updates a few seconds after launch so the window is ready
  setTimeout(() => checkForUpdates(), 3000);
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createLauncher();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
