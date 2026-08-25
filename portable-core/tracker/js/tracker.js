/**
 * tracker.js — shared SRAM autotracking state
 * Shared between itemtracker.html (popup) and map.html (popup)
 * Uses BroadcastChannel so both windows get SRAM updates without double-polling.
 */

'use strict';

// ── Global item state (read by map logic) ────────────────────────────────────
window.trackerItems = {
  bow: 0, boomerang: 0, hookshot: 0, bomb: 0,
  mushroom: 0, powder: 0, firerod: 0, icerod: 0,
  bombos: 0, ether: 0, quake: 0,
  lamp: 0, hammer: 0, shovel: 0, flute: 0,
  net: 0, book: 0, bottle: 0,
  somaria: 0, byrna: 0, cape: 0, mirror: 0, halfmagic: 0,
  boots: 0, gloves: 0, flippers: 0, moonpearl: 0,
  sword: 0, shield: 0, tunic: 0, agahnim: 0,
  crystals: 0,   // count 0-7
  // medallion assignments (0=none,1=bombos,2=ether,3=quake)
  mmMedallion: 0, trMedallion: 0,
};

// ── Crystal / prize tracking (7 crystals + 3 pendants) ──────────────────────
window.trackerPrizes = {
  ep: 0, dp: 0, toh: 0,          // 0=unknown,1=green pendant,2=red/blue pendant,3=crystal
  pod: 0, sp: 0, sw: 0, tt: 0,
  ip: 0, mm: 0, tr: 0,
};

// ── BroadcastChannel so map popup receives item updates ──────────────────────
var _bc = null;
try { _bc = new BroadcastChannel('alttp-tracker'); } catch(e) {}

function broadcastItems() {
  if (_bc) _bc.postMessage({ type: 'items', data: window.trackerItems });
}

function _broadcastStatus(text, cls) {
  if (_bc) _bc.postMessage({ type: 'status', text: text, cls: cls });
}

// Listen in map window
if (typeof window._isMapWindow !== 'undefined') {
  try {
    var _bcRecv = new BroadcastChannel('alttp-tracker');
    _bcRecv.onmessage = function(e) {
      if (e.data && e.data.type === 'items') {
        window.trackerItems = e.data.data;
        if (typeof window.refreshMapLogic === 'function') window.refreshMapLogic();
      }
    };
  } catch(e) {}
}

// ── WebSocket helpers (used by itemtracker.html) ─────────────────────────────
window.wsState = {
  ws: null, device: null, attached: false,
  readTimer: null, reconnectTimer: null,
  prevInventory: null, prevRooms: null,
};

function wsConnect(host, port, onStatus) {
  var wss = window.wsState;
  if (wss.ws) { wss.ws.onclose = null; wss.ws.close(); }
  clearInterval(wss.readTimer); clearInterval(wss.reconnectTimer);
  wss.attached = false; wss.device = null;

  onStatus('Connecting…', '#f39c12');
  _broadcastStatus('Connecting…', 'connecting');
  try { wss.ws = new WebSocket('ws://' + host + ':' + port); }
  catch(e) { onStatus('Error: ' + e.message, '#e74c3c'); return; }
  wss.ws.binaryType = 'arraybuffer';

  wss.ws.onopen = function() {
    wss.ws.send(JSON.stringify({ Opcode: 'DeviceList', Space: 'SNES' }));
  };

  wss.ws.onmessage = function(evt) {
    if (evt.data instanceof ArrayBuffer) {
      _handleBinary(new Uint8Array(evt.data));
      return;
    }
    var r; try { r = JSON.parse(evt.data); } catch(e) { return; }
    if (!r.Results) return;
    if (!wss.attached) {
      if (!r.Results.length) {
        onStatus('No device', '#e67e22');
        _broadcastStatus('No device', 'disconnected');
        return;
      }
      wss.device = r.Results[0];
      wss.ws.send(JSON.stringify({ Opcode: 'Attach', Space: 'SNES', Operands: [wss.device] }));
      wss.ws.send(JSON.stringify({ Opcode: 'Name', Space: 'SNES', Operands: ['ALTTP Tracker'] }));
      wss.attached = true;
      onStatus('Connected · ' + wss.device, '#2ecc71');
      _broadcastStatus('Connected · ' + wss.device, 'connected');
      _startPolling();
    }
  };

  wss.ws.onerror = function() {
    onStatus('Connection error', '#e74c3c');
    _broadcastStatus('Connection error', 'error');
  };
  wss.ws.onclose = function() {
    clearInterval(wss.readTimer);
    wss.attached = false; wss.device = null;
    onStatus('Disconnected', '#777');
    _broadcastStatus('Disconnected', 'disconnected');
    wss.reconnectTimer = setTimeout(function() { wsConnect(host, port, onStatus); }, 5000);
  };
}

function wsDisconnect() {
  var wss = window.wsState;
  clearInterval(wss.readTimer); clearInterval(wss.reconnectTimer);
  if (wss.ws) { wss.ws.onclose = null; wss.ws.close(); wss.ws = null; }
  wss.attached = false;
}

function _startPolling() {
  var wss = window.wsState;
  clearInterval(wss.readTimer);
  wss.readTimer = setInterval(function() {
    if (!wss.ws || wss.ws.readyState !== WebSocket.OPEN || !wss.attached) return;
    // Inventory: 0xF5F340, 0x1AE bytes
    wss.ws.send(JSON.stringify({ Opcode: 'GetAddress', Space: 'SNES', Operands: ['F5F340', '1ae'] }));
    // Room/event data: 0xF5F000, 0x420 bytes (covers all check flags)
    wss.ws.send(JSON.stringify({ Opcode: 'GetAddress', Space: 'SNES', Operands: ['F5F000', '420'] }));
  }, 1000);
}

function _handleBinary(data) {
  if (data.length === 0x1ae) { _processInventory(data); }
  else if (data.length === 0x420) { _processRooms(data); }
}

// ── Inventory processing ─────────────────────────────────────────────────────
function _processInventory(data) {
  var prev = window.wsState.prevInventory;
  var ch = function(o) { return !prev || data[o] !== prev[o]; };
  var nb = function(o, m) { return ch(o) && (data[o] & m) !== 0 && (!prev || (prev[o] & m) === 0); };
  var it = window.trackerItems;

  if (ch(0x00)) {
    var bv = data[0x00];
    it.bow = bv === 0 ? 0 : bv === 1 ? 1 : bv === 2 ? 2 : 3;
  }
  if (ch(0x4C)) {
    var b = data[0x4C];
    var bb = b & 0xC0;
    it.boomerang = bb === 0x80 ? 1 : bb === 0x40 ? 2 : bb === 0xC0 ? 3 : 0;
    var mb = b & 0x28;
    it.mushroom = mb === 0x28 ? 1 : mb === 0x08 ? 2 : 0;
    if (b & 0x10) it.powder = 1;
    var fs = b & 0x03;
    it.flute = (fs === 1 || fs === 3) ? 2 : fs === 2 ? 1 : 0;
    if (b & 0x04) it.shovel = 1;
  }
  if (nb(0x02, 0x01)) it.hookshot = 1;
  if (ch(0x03))  it.bomb     = data[0x03] > 0 ? 1 : 0;
  if (nb(0x05, 0x01)) it.firerod  = 1;
  if (nb(0x06, 0x01)) it.icerod   = 1;
  if (nb(0x07, 0x01)) it.bombos   = 1;
  if (nb(0x08, 0x01)) it.ether    = 1;
  if (nb(0x09, 0x01)) it.quake    = 1;
  if (nb(0x0A, 0x01)) it.lamp     = 1;
  if (nb(0x0B, 0x01)) it.hammer   = 1;
  if (nb(0x0D, 0x01)) it.net      = 1;
  if (nb(0x0E, 0x01)) it.book     = 1;
  var bottles = 0;
  for (var i = 0x1C; i <= 0x1F; i++) if (data[i] > 0) bottles++;
  it.bottle = bottles;
  if (nb(0x10, 0x01)) it.somaria  = 1;
  if (nb(0x11, 0x01)) it.byrna    = 1;
  if (nb(0x12, 0x01)) it.cape     = 1;
  if (nb(0x13, 0x02)) it.mirror   = 1;
  if (ch(0x14))  it.gloves   = data[0x14];
  if (nb(0x15, 0x01)) it.boots    = 1;
  if (nb(0x16, 0x01)) it.flippers = 1;
  if (nb(0x17, 0x01)) it.moonpearl= 1;
  if (ch(0x19))  it.sword    = data[0x19] === 0xFF ? 0 : data[0x19];
  if (ch(0x1A))  it.shield   = data[0x1A];
  if (ch(0x1B))  it.tunic    = data[0x1B];
  if (ch(0x3B))  it.halfmagic= data[0x3B] > 0 ? 1 : 0;
  if (ch(0x85))  it.agahnim  = data[0x85] >= 3 ? 1 : 0;

  // Crystals from prize flags at 0x37A (offset from 0x340 = 0x3A)
  if (ch(0x3A)) {
    var crystalByte = data[0x3A];
    it.crystals = _countBits(crystalByte);
  }

  window.wsState.prevInventory = data.slice();
  broadcastItems();
  if (typeof window.onItemsUpdated === 'function') window.onItemsUpdated();
}

function _countBits(n) {
  var c = 0; while (n) { c += n & 1; n >>= 1; } return c;
}

// ── Room/event data for map checks ───────────────────────────────────────────
function _processRooms(data) {
  window.wsState.prevRooms = data.slice();
  // Notify map window if open
  if (_bc) _bc.postMessage({ type: 'rooms', data: Array.from(data) });
  if (typeof window.onRoomsUpdated === 'function') window.onRoomsUpdated(data);
}
