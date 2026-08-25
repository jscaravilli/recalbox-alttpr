const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  launch:       (opts) => ipcRenderer.send('launch', opts),
  loadSettings: ()     => ipcRenderer.invoke('load-settings'),
  getPaths:     ()     => ipcRenderer.invoke('get-paths'),
  setBroadcastBg:   (bg) => ipcRenderer.invoke('set-broadcast-bg', bg),
  setTimerBg:       (bg) => ipcRenderer.invoke('set-timer-bg', bg),
  setItemTrackerBg: (bg) => ipcRenderer.invoke('set-itemtracker-bg', bg),
  registerNewgameHotkey:   (accel) => ipcRenderer.invoke('register-newgame-hotkey', accel),
  unregisterNewgameHotkey: ()      => ipcRenderer.invoke('unregister-newgame-hotkey'),
  onNewgame: (cb) => ipcRenderer.on('newgame', cb),
  checkForUpdates: ()  => ipcRenderer.invoke('check-for-updates'),
  installUpdate:   ()  => ipcRenderer.invoke('install-update'),
  openExternal:    (url) => ipcRenderer.invoke('open-external', url),
  openCheckList:     ()  => ipcRenderer.send('open-checklist'),
  saveEntState: (json) => ipcRenderer.invoke('save-ent-state', json),
  loadEntState: async (cb) => {
    const result = await ipcRenderer.invoke('load-ent-state');
    if (result && result.ok) cb(result.json);
  },
  openBcastSettings: ()  => ipcRenderer.invoke('open-bcast-settings'),
  onUpdateStatus:  (cb) => ipcRenderer.on('update-status', (_e, data) => cb(data)),
  isElectron:   true,
});
