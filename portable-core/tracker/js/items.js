// BASE_URL for item images.
// In Electron we ask the main process for the real absolute file:// path.
// In browser we use the normal relative path.
let BASE_URL = 'items';
// BOSS_URL points at the sibling boss/ folder (boss0.png … boss10.png).
let BOSS_URL = 'boss';

function applyBaseUrl(newBase) {
  BASE_URL = newBase;
  // boss/ lives next to items/ — derive its path from the same base.
  BOSS_URL = newBase.replace(/items\/?$/, 'boss');
  // Rebuild all image src paths in the items object
  Object.keys(items).forEach(function(key) {
    var item = items[key];
    if (!item.states) return;
    item.states.forEach(function(state) {
      if (state.img) {
        // Replace any existing base (items/ or file://.../) with the new one
        state.img = state.img.replace(/^.*\/items\//, newBase + '/');
        // Handle case where img is just 'items/filename.png'
        if (!state.img.startsWith(newBase)) {
          state.img = state.img.replace(/^items\//, newBase + '/');
        }
      }
    });
  });
  // Re-render all currently displayed item images
  document.querySelectorAll('[data-item-key] img, .item-slot img').forEach(function(img) {
    var slot = img.closest('[data-item-key]') || img.closest('.item-slot');
    if (!slot) return;
    var key = slot.dataset.itemKey || slot.dataset.dungeonKey;
    if (key && items[key]) {
      var state = items[key].states[items[key].currentState];
      if (state && state.img) img.src = state.img;
    }
  });
  // Re-render boss circles with the corrected boss/ base path (no-op if the
  // dungeon slots haven't been built yet — createTracker will refresh later).
  if (typeof refreshAllBossCircles === 'function') refreshAllBossCircles();
}

(async function() {
  if (window.electronAPI && window.electronAPI.getPaths) {
    try {
      const paths = await window.electronAPI.getPaths();
      if (paths && paths.itemsUrl) {
        // Wait for DOM so items object and rendered images are available
        if (document.readyState === 'loading') {
          document.addEventListener('DOMContentLoaded', function() { applyBaseUrl(paths.itemsUrl); });
        } else {
          // Small delay to let createTracker() finish rendering
          setTimeout(function() { applyBaseUrl(paths.itemsUrl); }, 100);
        }
      }
    } catch(e) { /* fall back to relative path */ }
  }
})();

// WebSocket connection
let ws = null;
let wsHost = 'localhost';
let wsPort = 23074;
let reconnectInterval = null;
let deviceName = null;
let deviceAttached = false;
let _deviceRetryTimer = null;
let _gamemodeValid = false;
// Tracking mode: 'auto' polls live game memory over the bridge; 'manual' fully
// disconnects so the user can tap items by hand without the poll overwriting them.
let _trackingMode = (function() {
    try { return localStorage.getItem('alttp-tracking-mode') || 'auto'; }
    catch (e) { return 'auto'; }
})();
const GAMEMODE_SRAM = (0xF50010).toString(16).toUpperCase();
const GAMEPLAY_MODES = [0x07, 0x09, 0x0B];
const KNOWN_ALTTP_MODES = [
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06,
    0x08, 0x0A, 0x0C, 0x0D, 0x0E, 0x0F,
    0x10, 0x14, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B
];
let readTimer = null;
let previousSRAM = null;
let _bombClearTimer = null; // debounce: only clear bombs after sustained 0 reading

const items = {
    bow: {
        states: [
            { img: `${BASE_URL}/bow00.png`, name: 'No Bow' },
            { img: `${BASE_URL}/bow10.png`, name: 'Bow' },
            { img: `${BASE_URL}/bow11.png`, name: 'Bow & Arrows' },
            { img: `${BASE_URL}/bow12.png`, name: 'Silver Arrows' }
        ],
        currentState: 0
    },
    boomerang: {
        states: [
            { img: `${BASE_URL}/boomerang00.png`, name: 'No Boomerang' },
            { img: `${BASE_URL}/boomerang10.png`, name: 'Blue Boomerang' },
            { img: `${BASE_URL}/boomerang01.png`, name: 'Red Boomerang' },
            { img: `${BASE_URL}/boomerang11.png`, name: 'Both Boomerangs' }
        ],
        currentState: 0
    },
    hookshot: {
        states: [
            { img: `${BASE_URL}/hookshot0.png`, name: 'No Hookshot' },
            { img: `${BASE_URL}/hookshot1.png`, name: 'Hookshot' }
        ],
        currentState: 0
    },
    bomb: {
        states: [
            { img: `${BASE_URL}/bomb00.png`, name: 'No Bombs' },
            { img: `${BASE_URL}/bomb10.png`, name: 'Bombs' }
        ],
        currentState: 0
    },
    mushroom: {
        states: [
            { img: `${BASE_URL}/mushroom0.png`, name: 'No Mushroom' },
            { img: `${BASE_URL}/mushroom1.png`, name: 'Mushroom' },
            { img: `${BASE_URL}/mushroom2.png`, name: 'Turned In' }
        ],
        currentState: 0
    },
    powder: {
        states: [
            { img: `${BASE_URL}/powder00.png`, name: 'No Powder' },
            { img: `${BASE_URL}/powder10.png`, name: 'Magic Powder' }
        ],
        currentState: 0
    },
    firerod: {
        states: [
            { img: `${BASE_URL}/firerod0.png`, name: 'No Fire Rod' },
            { img: `${BASE_URL}/firerod1.png`, name: 'Fire Rod' }
        ],
        currentState: 0
    },
    icerod: {
        states: [
            { img: `${BASE_URL}/icerod0.png`, name: 'No Ice Rod' },
            { img: `${BASE_URL}/icerod1.png`, name: 'Ice Rod' }
        ],
        currentState: 0
    },
    bombos: {
        states: [
            { img: `${BASE_URL}/bombos00.png`, name: 'No Bombos' },
            { img: `${BASE_URL}/bombos10.png`, name: 'Bombos' }
        ],
        currentState: 0,
        medallionLabel: ''
    },
    ether: {
        states: [
            { img: `${BASE_URL}/ether00.png`, name: 'No Ether' },
            { img: `${BASE_URL}/ether10.png`, name: 'Ether' }
        ],
        currentState: 0,
        medallionLabel: ''
    },
    quake: {
        states: [
            { img: `${BASE_URL}/quake00.png`, name: 'No Quake' },
            { img: `${BASE_URL}/quake10.png`, name: 'Quake' }
        ],
        currentState: 0,
        medallionLabel: ''
    },
    agahnim: {
        states: [
            { img: `${BASE_URL}/aga10.png`, name: 'Agahnim Alive' },
            { img: `${BASE_URL}/aga11.png`, name: 'Agahnim Defeated' }
        ],
        currentState: 0
    },
    gomode: {
        states: [
            { img: null, name: 'Go Mode Off',      color: '#666'     },
            { img: null, name: 'Go Mode On',        color: '#2ecc71'  },
            { img: null, name: 'Go Mode Feeling',   color: '#eee600'  }
        ],
        currentState: 0,
        isGoMode: true
    },
    lamp: {
        states: [
            { img: `${BASE_URL}/lamp0.png`, name: 'No Lamp' },
            { img: `${BASE_URL}/lamp1.png`, name: 'Lamp' }
        ],
        currentState: 0
    },
    hammer: {
        states: [
            { img: `${BASE_URL}/hammer0.png`, name: 'No Hammer' },
            { img: `${BASE_URL}/hammer1.png`, name: 'Hammer' }
        ],
        currentState: 0
    },
    shovel: {
        states: [
            { img: `${BASE_URL}/shovel0.png`, name: 'No Shovel' },
            { img: `${BASE_URL}/shovel1.png`, name: 'Shovel' }
        ],
        currentState: 0
    },
    flute: {
        states: [
            { img: `${BASE_URL}/flute00.png`, name: 'No Flute' },
            { img: `${BASE_URL}/flute10.png`, name: 'Flute' },
            { img: `${BASE_URL}/flute11.png`, name: 'Flute & Bird' }
        ],
        currentState: 0
    },
    net: {
        states: [
            { img: `${BASE_URL}/net0.png`, name: 'No Net' },
            { img: `${BASE_URL}/net1.png`, name: 'Net' }
        ],
        currentState: 0
    },
    book: {
        states: [
            { img: `${BASE_URL}/book0.png`, name: 'No Book' },
            { img: `${BASE_URL}/book1.png`, name: 'Book of Mudora' }
        ],
        currentState: 0
    },
    bottle1: {
        states: [
            { img: `${BASE_URL}/bottle0.png`,      name: 'Empty Slot' },
            { img: `${BASE_URL}/bottle_empty.png`, name: 'Empty Bottle' },
            { img: `${BASE_URL}/bottle_red.png`,   name: 'Red Potion' },
            { img: `${BASE_URL}/bottle_green.png`, name: 'Green Potion' },
            { img: `${BASE_URL}/bottle_blue.png`,  name: 'Blue Potion' },
            { img: `${BASE_URL}/bottle_fairy.png`, name: 'Fairy' },
            { img: `${BASE_URL}/bottle_bee.png`,   name: 'Bee' },
            { img: `${BASE_URL}/bottle_goodbee.png`,      name: 'Good Bee' },
        ], currentState: 0
    },
    bottle2: {
        states: [
            { img: `${BASE_URL}/bottle0.png`,      name: 'Empty Slot' },
            { img: `${BASE_URL}/bottle_empty.png`, name: 'Empty Bottle' },
            { img: `${BASE_URL}/bottle_red.png`,   name: 'Red Potion' },
            { img: `${BASE_URL}/bottle_green.png`, name: 'Green Potion' },
            { img: `${BASE_URL}/bottle_blue.png`,  name: 'Blue Potion' },
            { img: `${BASE_URL}/bottle_fairy.png`, name: 'Fairy' },
            { img: `${BASE_URL}/bottle_bee.png`,   name: 'Bee' },
            { img: `${BASE_URL}/bottle_goodbee.png`,      name: 'Good Bee' },
        ], currentState: 0
    },
    bottle3: {
        states: [
            { img: `${BASE_URL}/bottle0.png`,      name: 'Empty Slot' },
            { img: `${BASE_URL}/bottle_empty.png`, name: 'Empty Bottle' },
            { img: `${BASE_URL}/bottle_red.png`,   name: 'Red Potion' },
            { img: `${BASE_URL}/bottle_green.png`, name: 'Green Potion' },
            { img: `${BASE_URL}/bottle_blue.png`,  name: 'Blue Potion' },
            { img: `${BASE_URL}/bottle_fairy.png`, name: 'Fairy' },
            { img: `${BASE_URL}/bottle_bee.png`,   name: 'Bee' },
            { img: `${BASE_URL}/bottle_goodbee.png`,      name: 'Good Bee' },
        ], currentState: 0
    },
    bottle4: {
        states: [
            { img: `${BASE_URL}/bottle0.png`,      name: 'Empty Slot' },
            { img: `${BASE_URL}/bottle_empty.png`, name: 'Empty Bottle' },
            { img: `${BASE_URL}/bottle_red.png`,   name: 'Red Potion' },
            { img: `${BASE_URL}/bottle_green.png`, name: 'Green Potion' },
            { img: `${BASE_URL}/bottle_blue.png`,  name: 'Blue Potion' },
            { img: `${BASE_URL}/bottle_fairy.png`, name: 'Fairy' },
            { img: `${BASE_URL}/bottle_bee.png`,   name: 'Bee' },
            { img: `${BASE_URL}/bottle_goodbee.png`,      name: 'Good Bee' },
        ], currentState: 0
    },
    somaria: {
        states: [
            { img: `${BASE_URL}/caneofsomaria0.png`, name: 'No Somaria' },
            { img: `${BASE_URL}/caneofsomaria1.png`, name: 'Cane of Somaria' }
        ],
        currentState: 0
    },
    byrna: {
        states: [
            { img: `${BASE_URL}/caneofbyrna0.png`, name: 'No Byrna' },
            { img: `${BASE_URL}/caneofbyrna1.png`, name: 'Cane of Byrna' }
        ],
        currentState: 0
    },
    cape: {
        states: [
            { img: `${BASE_URL}/cape0.png`, name: 'No Cape' },
            { img: `${BASE_URL}/cape1.png`, name: 'Magic Cape' }
        ],
        currentState: 0
    },
    mirror: {
        states: [
            { img: `${BASE_URL}/mirror0.png`, name: 'No Mirror' },
            { img: `${BASE_URL}/mirror1.png`, name: 'Magic Mirror' }
        ],
        currentState: 0
    },
    halfmagic: {
        states: [
            { img: `${BASE_URL}/halfmagic0.png`, name: 'No Half Magic' },
            { img: `${BASE_URL}/halfmagic1.png`, name: 'Half Magic' }
        ],
        currentState: 0
    },
    boots: {
        states: [
            { img: `${BASE_URL}/boots0.png`, name: 'No Boots' },
            { img: `${BASE_URL}/boots1.png`, name: 'Pegasus Boots' }
        ],
        currentState: 0
    },
    gloves: {
        states: [
            { img: `${BASE_URL}/gloves0.png`, name: 'No Gloves' },
            { img: `${BASE_URL}/gloves1.png`, name: 'Power Glove' },
            { img: `${BASE_URL}/gloves2.png`, name: 'Titan\'s Mitt' }
        ],
        currentState: 0
    },
    flippers: {
        states: [
            { img: `${BASE_URL}/flippers0.png`, name: 'No Flippers' },
            { img: `${BASE_URL}/flippers1.png`, name: 'Flippers' }
        ],
        currentState: 0
    },
    moonpearl: {
        states: [
            { img: `${BASE_URL}/moonpearl0.png`, name: 'No Moon Pearl' },
            { img: `${BASE_URL}/moonpearl1.png`, name: 'Moon Pearl' }
        ],
        currentState: 0
    },
    sword: {
        states: [
            { img: `${BASE_URL}/sword0.png`, name: 'No Sword' },
            { img: `${BASE_URL}/sword1.png`, name: 'Fighter\'s Sword' },
            { img: `${BASE_URL}/sword2.png`, name: 'Master Sword' },
            { img: `${BASE_URL}/sword3.png`, name: 'Tempered Sword' },
            { img: `${BASE_URL}/sword4.png`, name: 'Golden Sword' }
        ],
        currentState: 0
    },
    shield: {
        states: [
            { img: `${BASE_URL}/shield0.png`, name: 'No Shield' },
            { img: `${BASE_URL}/shield1.png`, name: 'Fighter\'s Shield' },
            { img: `${BASE_URL}/shield2.png`, name: 'Fire Shield' },
            { img: `${BASE_URL}/shield3.png`, name: 'Mirror Shield' }
        ],
        currentState: 0
    },
    tunic: {
        states: [
            { img: `${BASE_URL}/mail0.png`, name: 'Green Mail' },
            { img: `${BASE_URL}/mail1.png`, name: 'Blue Mail' },
            { img: `${BASE_URL}/mail2.png`, name: 'Red Mail' }
        ],
        currentState: 0
    }
};

const dungeons = {
    ep: { name: 'EP', bossAddr: 0x191, bigkeyAddr: 0x367, bigkeyMask: 0x20, compassAddr: 0x365, compassMask: 0x20, mapAddr: 0x369, mapMask: 0x20, smallKeyAddr: 0x4e2, maxChests: 6, maxSmallKeys: 0, maxItems: 3, smallKeyCount: 0, itemCount: 0, prizeState: 0, bigkeyState: 0, compassState: 0, mapState: 0,
        locations: [[0x172,0x10],[0x154,0x10],[0x150,0x10],[0x152,0x10],[0x170,0x10],[0x191,0x08]] },
    dp: { name: 'DP', bossAddr: 0x067, bigkeyAddr: 0x367, bigkeyMask: 0x10, compassAddr: 0x365, compassMask: 0x10, mapAddr: 0x369, mapMask: 0x10, smallKeyAddr: 0x4e3, maxChests: 6, maxSmallKeys: 1, maxItems: 2, smallKeyCount: 0, itemCount: 0, prizeState: 0, bigkeyState: 0, compassState: 0, mapState: 0,
        locations: [[0xe6,0x10],[0xe7,0x04],[0xe8,0x10],[0x10a,0x10],[0xea,0x10],[0x67,0x08]] },
    toh: { name: 'TOH', bossAddr: 0x00f, bigkeyAddr: 0x366, bigkeyMask: 0x20, compassAddr: 0x364, compassMask: 0x20, mapAddr: 0x368, mapMask: 0x20, smallKeyAddr: 0x4ea, maxChests: 6, maxSmallKeys: 1, maxItems: 2, smallKeyCount: 0, itemCount: 0, prizeState: 0, bigkeyState: 0, compassState: 0, mapState: 0,
        locations: [[0x10f,0x04],[0xee,0x10],[0x10e,0x10],[0x4e,0x10],[0x4e,0x20],[0xf,0x08]] },
    pod: { name: 'POD', bossAddr: 0x0b5, bigkeyAddr: 0x367, bigkeyMask: 0x02, compassAddr: 0x365, compassMask: 0x02, mapAddr: 0x369, mapMask: 0x02, smallKeyAddr: 0x4e6, maxChests: 14, maxSmallKeys: 6, maxItems: 5, smallKeyCount: 0, itemCount: 0, prizeState: 0, bigkeyState: 0, compassState: 0, mapState: 0,
        locations: [[0x12,0x10],[0x56,0x10],[0x54,0x10],[0x54,0x20],[0x74,0x10],[0x14,0x10],[0x34,0x10],[0x34,0x20],[0x34,0x40],[0x32,0x10],[0x32,0x20],[0xd4,0x10],[0xd4,0x20],[0xb5,0x08]] },
    sp: { name: 'SP', bossAddr: 0x00d, bigkeyAddr: 0x367, bigkeyMask: 0x04, compassAddr: 0x365, compassMask: 0x04, mapAddr: 0x369, mapMask: 0x04, smallKeyAddr: 0x4e5, maxChests: 10, maxSmallKeys: 1, maxItems: 6, smallKeyCount: 0, itemCount: 0, prizeState: 0, bigkeyState: 0, compassState: 0, mapState: 0,
        locations: [[0x50,0x10],[0x6e,0x10],[0x6c,0x10],[0x6a,0x10],[0x68,0x10],[0x8c,0x10],[0xec,0x10],[0xec,0x20],[0xcc,0x10],[0xd,0x08]] },
    sw: { name: 'SW', bossAddr: 0x053, bigkeyAddr: 0x366, bigkeyMask: 0x80, compassAddr: 0x364, compassMask: 0x80, mapAddr: 0x368, mapMask: 0x80, smallKeyAddr: 0x4e8, maxChests: 8, maxSmallKeys: 3, maxItems: 2, smallKeyCount: 0, itemCount: 0, prizeState: 0, bigkeyState: 0, compassState: 0, mapState: 0,
        locations: [[0xce,0x10],[0xd0,0x10],[0xae,0x10],[0xae,0x20],[0xb0,0x10],[0xb0,0x20],[0xb2,0x10],[0x53,0x08]] },
    tt: { name: 'TT', bossAddr: 0x159, bigkeyAddr: 0x366, bigkeyMask: 0x10, compassAddr: 0x364, compassMask: 0x10, mapAddr: 0x368, mapMask: 0x10, smallKeyAddr: 0x4eb, maxChests: 8, maxSmallKeys: 1, maxItems: 4, smallKeyCount: 0, itemCount: 0, prizeState: 0, bigkeyState: 0, compassState: 0, mapState: 0,
        locations: [[0x1b6,0x10],[0x1b6,0x20],[0x196,0x10],[0x1b8,0x10],[0xca,0x10],[0x8a,0x10],[0x88,0x10],[0x159,0x08]] },
    ip: { name: 'IP', bossAddr: 0x1bd, bigkeyAddr: 0x366, bigkeyMask: 0x40, compassAddr: 0x364, compassMask: 0x40, mapAddr: 0x368, mapMask: 0x40, smallKeyAddr: 0x4e9, maxChests: 8, maxSmallKeys: 2, maxItems: 3, smallKeyCount: 0, itemCount: 0, prizeState: 0, bigkeyState: 0, compassState: 0, mapState: 0,
        locations: [[0x5c,0x10],[0x7e,0x10],[0x3e,0x10],[0xbe,0x10],[0xfc,0x10],[0x15c,0x10],[0x13c,0x10],[0x1bd,0x08]] },
    mm: { name: 'MM', bossAddr: 0x121, bigkeyAddr: 0x367, bigkeyMask: 0x01, compassAddr: 0x365, compassMask: 0x01, mapAddr: 0x369, mapMask: 0x01, smallKeyAddr: 0x4e7, maxChests: 8, maxSmallKeys: 3, maxItems: 2, smallKeyCount: 0, itemCount: 0, prizeState: 0, bigkeyState: 0, compassState: 0, mapState: 0,
        locations: [[0x144,0x10],[0x166,0x10],[0x184,0x10],[0x182,0x10],[0x1a2,0x10],[0x186,0x10],[0x186,0x20],[0x121,0x08]] },
    tr: { name: 'TR', bossAddr: 0x149, bigkeyAddr: 0x366, bigkeyMask: 0x08, compassAddr: 0x364, compassMask: 0x08, mapAddr: 0x368, mapMask: 0x08, smallKeyAddr: 0x4ec, maxChests: 12, maxSmallKeys: 4, maxItems: 5, smallKeyCount: 0, itemCount: 0, prizeState: 0, bigkeyState: 0, compassState: 0, mapState: 0,
        locations: [[0x1ac,0x10],[0x16e,0x10],[0x16e,0x20],[0x16c,0x10],[0x28,0x10],[0x48,0x10],[0x8,0x10],[0x1aa,0x10],[0x1aa,0x20],[0x1aa,0x40],[0x1aa,0x80],[0x149,0x08]] },
    gt: { name: 'GT', bossAddr: null, bigkeyAddr: 0x366, bigkeyMask: 0x04, compassAddr: 0x364, compassMask: 0x04, mapAddr: 0x368, mapMask: 0x04, smallKeyAddr: 0x4ed, maxChests: 27, maxSmallKeys: 4, maxItems: 20, smallKeyCount: 0, itemCount: 0, prizeState: 0, bigkeyState: 0, compassState: 0, mapState: 0, bigkeyOnly: true,
        locations: [[0x119,0x04],[0xf6,0x10],[0xf6,0x20],[0xf6,0x40],[0xf6,0x80],[0x116,0x10],[0xfa,0x10],[0xf8,0x10],[0xf8,0x20],[0xf8,0x40],[0xf8,0x80],[0x118,0x10],[0x118,0x20],[0x118,0x40],[0x118,0x80],[0x38,0x10],[0x38,0x20],[0x38,0x40],[0x11a,0x10],[0x13a,0x10],[0x13a,0x20],[0x13a,0x40],[0x13a,0x80],[0x7a,0x10],[0x7a,0x20],[0x7a,0x40],[0x9a,0x10]] }
};

// Expose dungeons globally so itemtracker.html can read/update them
window.dungeons = dungeons;

// Apply dungeon item shuffle maxItems overrides based on mode
(function() {
    var p = new URLSearchParams(window.location.search);
    var mode = p.get('dungeonitems') || localStorage.getItem('alttp-dungeon-items') || 'standard';
    if (mode === 'keysanity') {
        // All dungeon items (map/compass/keys/bigkey) are shuffled — count all chests
        var KS = { ep:6, dp:6, toh:6, pod:14, sp:10, sw:8, tt:8, ip:8, mm:8, tr:12, gt:27 };
        Object.keys(KS).forEach(function(k) {
            if (dungeons[k]) dungeons[k].maxItems = KS[k];
        });
    } else if (mode === 'mapcompass') {
        // Maps and compasses are shuffled — standard + 2 per dungeon (GT +1, no map)
        var MC = { ep:5, dp:4, toh:4, pod:7, sp:8, sw:4, tt:6, ip:5, mm:4, tr:7, gt:22 };
        Object.keys(MC).forEach(function(k) {
            if (dungeons[k]) dungeons[k].maxItems = MC[k];
        });
    } else if (mode === 'mapcompasskeys') {
        // Maps, compasses, and small keys shuffled but big key stays — subtract 1 for big key
        var MCK = { ep:5, dp:5, toh:5, pod:13, sp:9, sw:7, tt:7, ip:7, mm:7, tr:11, gt:26 };
        Object.keys(MCK).forEach(function(k) {
            if (dungeons[k]) dungeons[k].maxItems = MCK[k];
        });
    }
})();

const layout = [
    ['bow', 'boomerang', 'hookshot', 'bomb', 'mushroom', 'powder', 'moonpearl', 'sword', 'ep'],
    ['firerod', 'icerod', 'bombos', 'ether', 'quake', 'boots', 'gloves', 'shield', 'dp'],
    ['lamp', 'hammer', 'shovel', 'flute', 'net', 'book', 'flippers', 'tunic', 'toh'],
    ['bottles', 'somaria', 'byrna', 'cape', 'mirror', 'halfmagic', 'agahnim', 'gomode', 'stats'],
    ['pod', 'sp', 'sw', 'tt', 'ip', 'mm', 'tr', 'gt']
];

function createTracker() {
    // Clear cache on load
    localStorage.removeItem('alttp-tracker-state');
    
    const container = document.querySelector('.tracker-container');
    
    layout.forEach((row, rowIndex) => {
        const rowDiv = document.createElement('div');
        rowDiv.className = 'tracker-row';
        // The row holding the (tall) stats box is top-aligned so its 48px
        // items hug the row above instead of floating in the middle.
        if (row.indexOf('stats') !== -1) rowDiv.classList.add('stats-row');
        // Rows 1-4 are "item rows" — give them all a uniform fixed height so
        // the spacing between every item row is consistent (row 5 is the
        // crystal-dungeon row and is left auto-height).
        if (rowIndex <= 3) rowDiv.classList.add('item-row');

        row.forEach(itemKey => {
            // Check if this is a dungeon
            if (dungeons[itemKey]) {
                const dungeonSlot = document.createElement('div');
                dungeonSlot.className = 'dungeon-slot';
                dungeonSlot.dataset.dungeonKey = itemKey;
                
                // Check if this is a pendant dungeon (EP, DP, ToH)
                const isPendantDungeon = ['ep', 'dp', 'toh'].includes(itemKey);
                if (isPendantDungeon) {
                    dungeonSlot.classList.add('pendant-dungeon');
                }

                // GT is a shorter box than the crystal dungeons. In Key Sanity /
                // MCK modes the stats box is taller (it carries the extra CT
                // counter) and overflows down far enough to overlap GT — drop GT
                // to the bottom of its row in those modes so it clears the overflow.
                if (itemKey === 'gt') {
                    const _gtMode = (new URLSearchParams(window.location.search).get('dungeonitems') || localStorage.getItem('alttp-dungeon-items') || 'standard');
                    if (['keysanity', 'mapcompasskeys'].includes(_gtMode)) {
                        dungeonSlot.classList.add('gt-bottom');
                    }
                }

                // Container for label and prize (left side for pendant dungeons)
                const dungeonContent = document.createElement('div');
                dungeonContent.className = 'dungeon-content';

                if (isPendantDungeon) {
                    // Pendant dungeons: label then prize stacked vertically
                    const label = document.createElement('div');
                    label.className = 'dungeon-label';
                    label.textContent = dungeons[itemKey].name;
                    dungeonContent.appendChild(label);

                    if (!dungeons[itemKey].bigkeyOnly) {
                        const prizeImg = document.createElement('img');
                        prizeImg.className = 'prize-img';
                        const _ksMode = (new URLSearchParams(window.location.search).get('dungeonitems') || localStorage.getItem('alttp-dungeon-items') || 'standard');
                        const _isShuffled = ['keysanity','mapcompass','mapcompasskeys','other'].includes(_ksMode);
                        prizeImg.src = `${BASE_URL}/${_isShuffled ? 'unknown0.png' : 'crystal0.png'}`;
                        prizeImg.alt = 'Prize';
                        prizeImg.addEventListener('contextmenu', function(e) {
                            e.preventDefault();
                            e.stopPropagation();
                            togglePrizeObtained(itemKey, dungeonSlot);
                        });
                        dungeonContent.appendChild(prizeImg);
                        dungeonSlot.addEventListener('click', () => cycleDungeonPrize(itemKey, dungeonSlot));
                    }
                    dungeonSlot.appendChild(dungeonContent);
                } else {
                    // DW dungeons: label left, prize right on top row
                    const topRow = document.createElement('div');
                    topRow.className = 'dungeon-top-row';
                    const label = document.createElement('div');
                    label.className = 'dungeon-label';
                    label.textContent = dungeons[itemKey].name;
                    topRow.appendChild(label);

                    if (!dungeons[itemKey].bigkeyOnly) {
                        const prizeImg = document.createElement('img');
                        prizeImg.className = 'prize-img';
                        const _ksMode = (new URLSearchParams(window.location.search).get('dungeonitems') || localStorage.getItem('alttp-dungeon-items') || 'standard');
                        const _isShuffled = ['keysanity','mapcompass','mapcompasskeys','other'].includes(_ksMode);
                        prizeImg.src = `${BASE_URL}/${_isShuffled ? 'unknown0.png' : 'crystal0.png'}`;
                        prizeImg.alt = 'Prize';
                        prizeImg.addEventListener('contextmenu', function(e) {
                            e.preventDefault();
                            e.stopPropagation();
                            togglePrizeObtained(itemKey, dungeonSlot);
                        });
                        topRow.appendChild(prizeImg);
                        dungeonSlot.addEventListener('click', () => cycleDungeonPrize(itemKey, dungeonSlot));
                    }
                    dungeonSlot.appendChild(topRow);
                    dungeonSlot.appendChild(dungeonContent); // empty but needed for consistent structure
                }
                
                // Container for dungeon items (bigkey, compass, map)
                const itemsContainer = document.createElement('div');
                itemsContainer.className = 'dungeon-items';
                
                const bigkeyImg = document.createElement('img');
                bigkeyImg.className = 'bigkey-img';
                bigkeyImg.src = `${BASE_URL}/bigkey0.png`;
                bigkeyImg.alt = 'Big Key';
                bigkeyImg.style.cursor = 'pointer';
                bigkeyImg.addEventListener('click', function(e) {
                    e.stopPropagation();
                    const d = dungeons[itemKey];
                    d.bigkeyState = d.bigkeyState ? 0 : 1;
                    bigkeyImg.src = `${BASE_URL}/bigkey${d.bigkeyState}.png`;
                    if (!window.trackerItems) window.trackerItems = {};
                    window.trackerItems[itemKey + 'BigKey'] = d.bigkeyState;
                    if (window.broadcastItemSnap) window.broadcastItemSnap();
                });
                itemsContainer.appendChild(bigkeyImg);

                const compassImg = document.createElement('img');
                compassImg.className = 'compass-img';
                compassImg.src = `${BASE_URL}/compass0.png`;
                compassImg.alt = 'Compass';
                compassImg.style.cursor = 'pointer';
                compassImg.addEventListener('click', function(e) {
                    e.stopPropagation();
                    const d = dungeons[itemKey];
                    d.compassState = d.compassState ? 0 : 1;
                    compassImg.src = `${BASE_URL}/compass${d.compassState}.png`;
                    updateDungeonCountDisplay(itemKey);
                    if (window.broadcastItemSnap) window.broadcastItemSnap();
                });
                itemsContainer.appendChild(compassImg);

                const mapImg = document.createElement('img');
                mapImg.className = 'map-img';
                mapImg.src = `${BASE_URL}/map0.png`;
                mapImg.alt = 'Map';
                mapImg.style.cursor = 'pointer';
                mapImg.addEventListener('click', function(e) {
                    e.stopPropagation();
                    const d = dungeons[itemKey];
                    d.mapState = d.mapState ? 0 : 1;
                    mapImg.src = `${BASE_URL}/map${d.mapState}.png`;
                    updateDungeonCountDisplay(itemKey);
                    if (typeof broadcastPrizes === 'function') setTimeout(broadcastPrizes, 50);
                    if (window.broadcastItemSnap) window.broadcastItemSnap();
                });
                itemsContainer.appendChild(mapImg);
                
                dungeonSlot.appendChild(itemsContainer);
                
                // Add small key and item count displays
                const _diModeSlot = (new URLSearchParams(window.location.search).get('dungeonitems') || localStorage.getItem('alttp-dungeon-items') || 'standard');
                const _isOtherMode = _diModeSlot === 'other';
                const countsContainer = document.createElement('div');
                countsContainer.className = isPendantDungeon ? 'dungeon-counts-pendant' : 'dungeon-counts';
                
                // Small key count with icon (only if maxSmallKeys > 0 and not Other mode)
                if (!_isOtherMode && dungeons[itemKey].maxSmallKeys > 0) {
                    const keyContainer = document.createElement('div');
                    keyContainer.className = 'count-item';
                    
                    const keyImg = document.createElement('img');
                    keyImg.className = 'count-icon';
                    keyImg.src = `${BASE_URL}/smallkey0.png`;
                    keyImg.alt = 'Small Key';
                    
                    const keyCount = document.createElement('span');
                    keyCount.className = 'key-count';
                    keyCount.textContent = `0/${dungeons[itemKey].maxSmallKeys}`;
                    keyCount.dataset.dungeonKey = itemKey;
                    
                    keyContainer.appendChild(keyImg);
                    keyContainer.appendChild(keyCount);
                    keyContainer.style.cursor = 'pointer';
                    keyContainer.addEventListener('click', function(e) {
                        e.stopPropagation();
                        if (deviceAttached) return;
                        const d = dungeons[itemKey];
                        if (d.smallKeyCount < d.maxSmallKeys) {
                            d.smallKeyCount++;
                            if (d.smallKeyCount > (d.smallKeyMax || 0)) d.smallKeyMax = d.smallKeyCount;
                            if (!window.trackerItems) window.trackerItems = {};
                            window.trackerItems[itemKey + 'SmallKeys'] = d.smallKeyCount;
                            updateDungeonCountDisplay(itemKey);
                            if (window.broadcastItemSnap) window.broadcastItemSnap();
                        }
                    });
                    keyContainer.addEventListener('contextmenu', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        if (deviceAttached) return;
                        const d = dungeons[itemKey];
                        if (d.smallKeyCount > 0) {
                            d.smallKeyCount--;
                            if (!window.trackerItems) window.trackerItems = {};
                            window.trackerItems[itemKey + 'SmallKeys'] = d.smallKeyCount;
                            updateDungeonCountDisplay(itemKey);
                            if (window.broadcastItemSnap) window.broadcastItemSnap();
                        }
                    });
                    countsContainer.appendChild(keyContainer);
                }
                
                // Non-dungeon item count with icon (hidden in Other mode)
                if (_isOtherMode) {
                    // Other mode: clickable chest toggles completion
                    const otherContainer = document.createElement('div');
                    otherContainer.className = 'count-item';
                    const otherChest = document.createElement('img');
                    otherChest.className = 'count-icon other-chest';
                    otherChest.src = `${BASE_URL}/chest0.png`;
                    otherChest.alt = 'Items';
                    otherChest.style.cursor = 'pointer';
                    otherChest.style.width = '16px';
                    otherChest.style.height = '16px';
                    otherChest.addEventListener('click', function(e) {
                        e.stopPropagation();
                        const d = dungeons[itemKey];
                        d.otherCleared = !d.otherCleared;
                        otherChest.src = `${BASE_URL}/${d.otherCleared ? 'chest00.png' : 'chest0.png'}`;
                        updateDungeonCountDisplay(itemKey);
                        if (typeof broadcastPrizes === 'function') setTimeout(broadcastPrizes, 50);
                    });
                    otherContainer.appendChild(otherChest);
                    countsContainer.appendChild(otherContainer);
                } else {
                const itemContainer = document.createElement('div');
                itemContainer.className = 'count-item';
                
                const chestImg = document.createElement('img');
                chestImg.className = 'count-icon';
                chestImg.src = `${BASE_URL}/chest0.png`;
                chestImg.alt = 'Items';
                
                const itemCount = document.createElement('span');
                itemCount.className = 'item-count';
                itemCount.textContent = `0/${dungeons[itemKey].maxItems}`;
                itemCount.dataset.dungeonKey = itemKey;
                
                itemContainer.appendChild(chestImg);
                itemContainer.appendChild(itemCount);
                itemContainer.style.cursor = 'pointer';
                itemContainer.addEventListener('click', function(e) {
                    e.stopPropagation();
                    if (deviceAttached) return;
                    const d = dungeons[itemKey];
                    if (d.itemCount < d.maxItems) {
                        d.itemCount++;
                        updateDungeonCountDisplay(itemKey);
                    }
                });
                itemContainer.addEventListener('contextmenu', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (deviceAttached) return;
                    const d = dungeons[itemKey];
                    if (d.itemCount > 0) {
                        d.itemCount--;
                        updateDungeonCountDisplay(itemKey);
                    }
                });
                countsContainer.appendChild(itemContainer);
                } // end !_isOtherMode item count
                
                dungeonSlot.appendChild(countsContainer);

                // Boss circle — left of the row for pendant dungeons, underneath for the rest
                createBossCircle(itemKey, dungeonSlot, isPendantDungeon);

                rowDiv.appendChild(dungeonSlot);
            } else if (itemKey === 'stats') {
                const statsSlot = document.createElement('div');
                statsSlot.className = 'stats-slot';
                const checkBox = document.createElement('div');
                checkBox.className = 'stat-box stat-check';
                checkBox.innerHTML = '<span class="stat-label">CHECKS</span><span class="stat-value" id="toh-check-count">0</span>';
                const deathBox = document.createElement('div');
                deathBox.className = 'stat-box stat-death';
                deathBox.innerHTML = '<span class="stat-label">DEATHS</span><span class="stat-value" id="toh-death-count">0</span>';
                const bonkBox = document.createElement('div');
                bonkBox.className = 'stat-box stat-bonk';
                bonkBox.innerHTML = '<span class="stat-label">BONKS</span><span class="stat-value" id="toh-bonk-count">0</span>';
                const heartBox = document.createElement('div');
                heartBox.className = 'stat-box stat-heartpiece';
                heartBox.innerHTML = '<span class="stat-label">HEARTS</span><span class="stat-value" id="toh-heartpiece-count">0/4</span>';
                const revivalBox = document.createElement('div');
                revivalBox.className = 'stat-box stat-revival';
                revivalBox.innerHTML = '<span class="stat-label">REVIVALS</span><span class="stat-value" id="toh-revival-count">0</span>';
                // CT small key counter — Key Sanity only, shown above checks
                const _ksCheck = ['keysanity','mapcompasskeys'].includes(new URLSearchParams(window.location.search).get('dungeonitems') || localStorage.getItem('alttp-dungeon-items') || 'standard');
                if (_ksCheck) {
                    const ctKeyBox = document.createElement('div');
                    ctKeyBox.className = 'stat-box stat-ctkey';
                    ctKeyBox.innerHTML = `<span class="stat-label">CT</span><img src="${BASE_URL}/smallkey0.png" class="stat-icon" alt="Key"><span class="stat-value" id="toh-ctkey-count">0/2</span>`;
                    ctKeyBox.style.cursor = 'pointer';
                    ctKeyBox.addEventListener('click', function(e) {
                        e.stopPropagation();
                        if (deviceAttached) return;
                        if (!window.trackerItems) window.trackerItems = {};
                        var cur = window.trackerItems.ctSmallKeys || 0;
                        if (cur < 2) {
                            window.trackerItems.ctSmallKeys = cur + 1;
                            var el = document.getElementById('toh-ctkey-count');
                            if (el) { el.textContent = window.trackerItems.ctSmallKeys + '/2'; el.style.color = window.trackerItems.ctSmallKeys >= 2 ? '#2ecc71' : ''; }
                            if (window.broadcastItemSnap) window.broadcastItemSnap();
                        }
                    });
                    ctKeyBox.addEventListener('contextmenu', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        if (deviceAttached) return;
                        if (!window.trackerItems) window.trackerItems = {};
                        var cur = window.trackerItems.ctSmallKeys || 0;
                        if (cur > 0) {
                            window.trackerItems.ctSmallKeys = cur - 1;
                            var el = document.getElementById('toh-ctkey-count');
                            if (el) { el.textContent = window.trackerItems.ctSmallKeys + '/2'; el.style.color = window.trackerItems.ctSmallKeys >= 2 ? '#2ecc71' : ''; }
                            if (window.broadcastItemSnap) window.broadcastItemSnap();
                        }
                    });
                    statsSlot.appendChild(ctKeyBox);
                }
                statsSlot.appendChild(checkBox);
                statsSlot.appendChild(deathBox);
                statsSlot.appendChild(bonkBox);
                statsSlot.appendChild(heartBox);
                statsSlot.appendChild(revivalBox);
                rowDiv.appendChild(statsSlot);
            } else if (itemKey === 'bottles') {
                // 2x2 grid of bottle slots, same footprint as a single item slot (48x48)
                const bottleGrid = document.createElement('div');
                bottleGrid.className = 'bottle-grid';
                bottleGrid.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;width:48px;height:48px;gap:1px;padding:1px;cursor:pointer;';

                ['bottle1','bottle2','bottle3','bottle4'].forEach(function(bKey) {
                    const cell = document.createElement('div');
                    cell.dataset.itemKey = bKey;
                    cell.style.cssText = 'width:100%;height:100%;display:flex;align-items:center;justify-content:center;overflow:hidden;';
                    const img = document.createElement('img');
                    img.src = items[bKey].states[0].img;
                    img.alt = items[bKey].states[0].name;
                    img.style.cssText = 'width:22px;height:22px;image-rendering:pixelated;';
                    cell.appendChild(img);
                    cell.addEventListener('click', function(e) {
                        e.stopPropagation();
                        cycleItem(bKey, cell);
                    });
                    cell.addEventListener('contextmenu', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        // Right-click cycles backward
                        const cur = items[bKey].currentState;
                        const total = items[bKey].states.length;
                        items[bKey].currentState = (cur - 1 + total) % total;
                        const img = cell.querySelector('img');
                        if (img) {
                            img.src = items[bKey].states[items[bKey].currentState].img;
                            img.alt = items[bKey].states[items[bKey].currentState].name;
                        }
                        if (window.broadcastItemSnap) window.broadcastItemSnap();
                    });
                    bottleGrid.appendChild(cell);
                });
                rowDiv.appendChild(bottleGrid);
            } else {
                const itemSlot = document.createElement('div');
                itemSlot.className = 'item-slot';
                itemSlot.dataset.itemKey = itemKey;
                itemSlot.dataset.itemName = items[itemKey].states[0].name;
                
                if (items[itemKey].isGoMode) {
                    itemSlot.classList.add('go-mode');
                    itemSlot.textContent = 'GO';
                    itemSlot.style.marginLeft = '5px';
                    const state0 = items[itemKey].states[0];
                    if (state0.color === '#666') {
                        itemSlot.style.color = state0.color;
                        itemSlot.style.background = 'transparent';
                    } else {
                        itemSlot.style.color = '#000';
                        itemSlot.style.background = state0.color;
                    }
                } else {
                    const img = document.createElement('img');
                    img.src = items[itemKey].states[0].img;
                    img.alt = items[itemKey].states[0].name;
                    itemSlot.appendChild(img);
                    
                    // Add medallion label container for bombos, ether, quake
                    if (['bombos', 'ether', 'quake'].includes(itemKey)) {
                        const label = document.createElement('div');
                        label.className = 'medallion-label';
                        itemSlot.appendChild(label);
                    }
                }
                
                itemSlot.addEventListener('click', () => cycleItem(itemKey, itemSlot));
                itemSlot.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    if (['bombos', 'ether', 'quake'].includes(itemKey)) {
                        cycleMedallionLabel(itemKey, itemSlot);
                    } else if (items[itemKey].isGoMode) {
                        toggleGoModeFeeling(itemKey, itemSlot);
                    }
                });
                
                rowDiv.appendChild(itemSlot);
            }
        });
        
        container.appendChild(rowDiv);
    });
}

function togglePrizeObtained(dungeonKey, slot) {
    const prizeImg = slot.querySelector('.prize-img');
    if (!prizeImg) return;
    const src = prizeImg.src;
    // Toggle between dim (0.png) and bright (1.png) versions of current prize
    if (src.includes('0.png')) {
        prizeImg.src = src.replace('0.png', '1.png');
    } else {
        prizeImg.src = src.replace('1.png', '0.png');
    }
    updateDungeonCountDisplay(dungeonKey);
    updateBossCircle(dungeonKey);   // grey/un-grey the boss image to match
    if (typeof window.onPrizeCycled === 'function') window.onPrizeCycled();
    if (window.broadcastItemSnap) window.broadcastItemSnap();
}

function cycleDungeonPrize(dungeonKey, slot) {
    const dungeon = dungeons[dungeonKey];
    const _diMode = (new URLSearchParams(window.location.search).get('dungeonitems') || localStorage.getItem('alttp-dungeon-items') || 'standard');
    const ksMode = ['keysanity','mapcompass','mapcompasskeys','other'].includes(_diMode);
    const prizeImages = ksMode
        ? ['unknown0.png', 'crystal0.png', 'redcrystal0.png', 'pendant0.png', 'greenpendant0.png']
        : ['crystal0.png', 'redcrystal0.png', 'pendant0.png', 'greenpendant0.png'];
    
    dungeon.prizeState = (dungeon.prizeState + 1) % prizeImages.length;
    
    const prizeImg = slot.querySelector('.prize-img');
    prizeImg.src = `${BASE_URL}/${prizeImages[dungeon.prizeState]}`;
    updateBossCircle(dungeonKey);   // cycling resets the prize to un-obtained — un-grey the boss

    // Hook for external listeners (e.g. map window sync)
    if (typeof window.onPrizeCycled === 'function') window.onPrizeCycled();
    if (window.broadcastItemSnap) window.broadcastItemSnap();
}

// ── Boss circle ──────────────────────────────────────────────────────────────
// Each dungeon slot carries a "boss circle": a circle showing one of boss0..10.
// boss0 is the default '?' (neutral). The user right-clicks to pick a boss.
// Certain bosses need specific items; the circle turns red until those items
// are collected, green once they are (or immediately, for bosses with no
// requirement).
var BOSS_REQUIREMENTS = {
    // Armos Knights: Bow OR Byrna OR Somaria OR Fire Rod OR Hammer OR Ice Rod OR Sword
    1:  function() { return hasBossItem('bow') || hasBossItem('byrna') || hasBossItem('somaria') || hasBossItem('firerod') || hasBossItem('hammer') || hasBossItem('icerod') || hasBossItem('sword'); },
    // Lanmolas: Bow OR Byrna OR Somaria OR Fire Rod OR Hammer OR Ice Rod OR Sword
    2:  function() { return hasBossItem('bow') || hasBossItem('byrna') || hasBossItem('somaria') || hasBossItem('firerod') || hasBossItem('hammer') || hasBossItem('icerod') || hasBossItem('sword'); },
    // Moldorm: Hammer OR Sword
    3:  function() { return hasBossItem('hammer') || hasBossItem('sword'); },
    // Helmasaur King: Hammer OR (Bombs AND (Sword OR Bow))
    4:  function() { return hasBossItem('hammer') || (hasBossItem('bomb') && (hasBossItem('sword') || hasBossItem('bow'))); },
    // Arrghus: Hookshot + (Bow OR Fire Rod OR Hammer OR Ice Rod OR Sword)
    5:  function() { return hasBossItem('hookshot') && (hasBossItem('bow') || hasBossItem('firerod') || hasBossItem('hammer') || hasBossItem('icerod') || hasBossItem('sword')); },
    // Mothula: Fire Rod OR Hammer OR Byrna OR Somaria OR Sword
    6:  function() { return hasBossItem('firerod') || hasBossItem('hammer') || hasBossItem('byrna') || hasBossItem('somaria') || hasBossItem('sword'); },
    // Blind: Byrna OR Somaria OR Hammer OR Sword
    7:  function() { return hasBossItem('byrna') || hasBossItem('somaria') || hasBossItem('hammer') || hasBossItem('sword'); },
    // Kholdstare: (Fire Rod OR Bombos) + (Hammer OR Sword)
    8:  function() { return (hasBossItem('firerod') || hasBossItem('bombos')) && (hasBossItem('hammer') || hasBossItem('sword')); },
    // Vitreous: Bow OR Hammer OR Sword
    9:  function() { return hasBossItem('bow') || hasBossItem('hammer') || hasBossItem('sword'); },
    // Trinexx: (Fire Rod AND Ice Rod) + (Hammer OR Sword)
    10: function() { return hasBossItem('firerod') && hasBossItem('icerod') && (hasBossItem('hammer') || hasBossItem('sword')); }
};

function hasBossItem(key) {
    return !!(items[key] && items[key].currentState > 0);
}

// Build the boss circle for one dungeon slot. Pendant dungeons (EP/DP/ToH) get
// it on the left of the row; all other dungeons get it underneath.
function createBossCircle(dungeonKey, dungeonSlot, isPendant) {
    // GT's boss is always Agahnim 2 / Ganon — no boss selector needed there.
    if (dungeonKey === 'gt') return;
    if (dungeons[dungeonKey].bossState === undefined) dungeons[dungeonKey].bossState = 0;

    const circle = document.createElement('div');
    circle.className = 'boss-circle';

    const img = document.createElement('img');
    img.className = 'boss-img';
    img.src = `${BOSS_URL}/boss0.png`;
    img.alt = 'Boss';
    circle.appendChild(img);

    // Both left-click and right-click open the boss-selection popup. The
    // stopPropagation keeps the click from bubbling up to the dungeon's prize
    // cycle handler.
    circle.addEventListener('click', function(e) {
        e.stopPropagation();
        openBossPopup(dungeonKey, e.clientX, e.clientY);
    });
    circle.addEventListener('contextmenu', function(e) {
        e.preventDefault();
        e.stopPropagation();
        openBossPopup(dungeonKey, e.clientX, e.clientY);
    });

    if (isPendant) {
        // Pendant dungeons are a horizontal row — drop the circle into the
        // counts column so it sits underneath the chest count.
        const counts = dungeonSlot.querySelector('.dungeon-counts-pendant');
        (counts || dungeonSlot).appendChild(circle);
    } else {
        // Other dungeons are a vertical column — append lands it underneath.
        dungeonSlot.appendChild(circle);
    }
    updateBossCircle(dungeonKey);
}

// Refresh one dungeon's boss circle image + red/green/neutral state.
function updateBossCircle(dungeonKey) {
    const d = dungeons[dungeonKey];
    if (!d) return;
    const slot = document.querySelector(`[data-dungeon-key="${dungeonKey}"]`);
    if (!slot) return;
    const circle = slot.querySelector('.boss-circle');
    if (!circle) return;
    const img = circle.querySelector('.boss-img');
    const bossNum = d.bossState || 0;
    if (img) img.src = `${BOSS_URL}/boss${bossNum}.png`;

    // Prize obtained = boss defeated (the prize image switches to its bright
    // "1.png" variant, set either manually or by the auto-tracker).
    const prizeImg = slot.querySelector('.prize-img');
    const prizeObtained = !!(prizeImg && prizeImg.src.includes('1.png'));

    circle.classList.remove('boss-need', 'boss-ok');
    // Once defeated the red/green requirement ring is moot — leave the border
    // at its default neutral grey by skipping the boss-ok / boss-need class.
    if (bossNum > 0 && !prizeObtained) {
        const req = BOSS_REQUIREMENTS[bossNum];
        const met = req ? req() : true;   // bosses with no requirement are always "ok"
        circle.classList.add(met ? 'boss-ok' : 'boss-need');
    }

    // Grey out the boss image once the prize has been obtained.
    circle.classList.toggle('boss-defeated', prizeObtained);
}

// Re-evaluate every dungeon's boss circle — called whenever item state changes.
function refreshAllBossCircles() {
    Object.keys(dungeons).forEach(updateBossCircle);
}

function setBoss(dungeonKey, bossNum) {
    if (!dungeonKey || !dungeons[dungeonKey]) return;
    dungeons[dungeonKey].bossState = bossNum;
    updateBossCircle(dungeonKey);
    // Dedicated 'boss' message — short, fast, authoritative. The map applies
    // it directly to DUNGEONS[key] so the stripe state survives any subsequent
    // 'items' / 'prizes' snap (which replaces trackerItems wholesale).
    try {
        if (window._itemsBc) {
            var _req = (typeof BOSS_REQUIREMENTS !== 'undefined') ? BOSS_REQUIREMENTS[bossNum] : null;
            var _ok  = (!bossNum || !_req) ? true : !!_req();
            window._itemsBc.postMessage({ type: 'boss', data: { key: dungeonKey, state: bossNum, ok: _ok } });
        }
    } catch(e) {}
    // Also push a full snap so anything else that hangs off item state refreshes.
    if (window.broadcastItemSnap) window.broadcastItemSnap();
}

// ── Boss selection popup ─────────────────────────────────────────────────────
let _bossPopup = null;
let _bossPopupActiveKey = null;

function ensureBossPopup() {
    if (_bossPopup) return _bossPopup;
    const popup = document.createElement('div');
    popup.id = 'boss-popup';
    const grid = document.createElement('div');
    grid.className = 'boss-popup-grid';
    for (let i = 1; i <= 10; i++) {
        (function(n) {
            const cell = document.createElement('div');
            cell.className = 'boss-popup-item';
            cell.title = 'Boss ' + n;
            const cellImg = document.createElement('img');
            cellImg.src = `${BOSS_URL}/boss${n}.png`;
            cell.appendChild(cellImg);
            cell.addEventListener('click', function() {
                setBoss(_bossPopupActiveKey, n);
                closeBossPopup();
            });
            grid.appendChild(cell);
        })(i);
    }
    const clearBtn = document.createElement('button');
    clearBtn.className = 'boss-popup-clear';
    clearBtn.type = 'button';
    clearBtn.textContent = 'Clear ( ? )';
    clearBtn.addEventListener('click', function() {
        setBoss(_bossPopupActiveKey, 0);
        closeBossPopup();
    });
    grid.appendChild(clearBtn);
    popup.appendChild(grid);
    // Append to <html>, not <body>: the item tracker applies CSS `zoom` to the
    // body when scaled, which shifts position:fixed children out of true
    // viewport coordinates. Living on documentElement keeps the popup aligned
    // with the cursor's clientX/clientY.
    document.documentElement.appendChild(popup);

    // Dismiss on outside-click or Escape
    document.addEventListener('mousedown', function(e) {
        if (!popup.classList.contains('open')) return;
        if (popup.contains(e.target)) return;
        closeBossPopup();
    });
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeBossPopup();
    });

    _bossPopup = popup;
    return popup;
}

function openBossPopup(dungeonKey, x, y) {
    const popup = ensureBossPopup();
    _bossPopupActiveKey = dungeonKey;
    popup.classList.add('open');
    // Measure now that it's displayed, then position relative to the cursor.
    const pw = popup.offsetWidth, ph = popup.offsetHeight;
    const vw = window.innerWidth, vh = window.innerHeight;
    // Horizontal: open to the right of the cursor; flip left if it would overflow.
    let px = x;
    if (px + pw + 8 > vw) px = x - pw;
    px = Math.max(8, Math.min(px, vw - pw - 8));
    // Vertical: open below the cursor; flip above if it would overflow the
    // bottom of the window (common for the bottom-row crystal dungeons).
    let py = y;
    if (py + ph + 8 > vh) py = y - ph;
    py = Math.max(8, Math.min(py, vh - ph - 8));
    popup.style.left = px + 'px';
    popup.style.top  = py + 'px';
}

function closeBossPopup() {
    if (_bossPopup) _bossPopup.classList.remove('open');
    _bossPopupActiveKey = null;
}

function updateDungeonCountDisplay(dungeonKey) {
    const dungeon = dungeons[dungeonKey];
    const slot = document.querySelector(`[data-dungeon-key="${dungeonKey}"]`);
    
    if (slot) {
        // Calculate status first — needed by key count color and completion logic
        const allItemsCollected = dungeon.itemCount >= dungeon.maxItems;
        const allKeysCollected  = dungeon.maxSmallKeys > 0
            ? dungeon.smallKeyCount >= dungeon.maxSmallKeys
            : false;

        // Update small key count
        if (dungeon.maxSmallKeys > 0) {
            const keyCountSpan = slot.querySelector('.key-count');
            if (keyCountSpan) {
                keyCountSpan.textContent = `${dungeon.smallKeyCount}/${dungeon.maxSmallKeys}`;
                const _ksForKey = ['keysanity','mapcompasskeys'].includes(new URLSearchParams(window.location.search).get('dungeonitems') || localStorage.getItem('alttp-dungeon-items') || 'standard');
                keyCountSpan.style.color = (_ksForKey && allKeysCollected) ? '#2ecc71' : '';
            }
        }
        
        // Update item count and chest icon
        const itemCountSpan = slot.querySelector('.item-count');
        if (itemCountSpan) {
            itemCountSpan.textContent = `${dungeon.itemCount}/${dungeon.maxItems}`;
            // Switch chest icon to chest00.png when all items collected
            const chestIcon = slot.querySelector('.count-icon[alt="Items"]');
            if (chestIcon) {
                chestIcon.src = `${BASE_URL}/${dungeon.itemCount >= dungeon.maxItems ? 'chest00.png' : 'chest0.png'}`;
            }
            if (window.broadcastItemSnap) window.broadcastItemSnap();
        }

        // Check completion status (1.png = obtained/bright)
        const prizeImg = slot.querySelector('.prize-img');
        const prizeCollected = prizeImg && prizeImg.src.includes('1.png');

        const ksMode2 = (new URLSearchParams(window.location.search).get('dungeonitems') || localStorage.getItem('alttp-dungeon-items') || 'standard') === 'keysanity';
        const _isOther = (new URLSearchParams(window.location.search).get('dungeonitems') || localStorage.getItem('alttp-dungeon-items') || 'standard') === 'other';

        // Remove all completion classes first
        slot.classList.remove('completed-items', 'completed-full', 'prize-obtained');

        if (_isOther) {
            // Other mode: green border when chest clicked AND prize collected
            if (dungeon.otherCleared && prizeCollected) {
                slot.classList.add('completed-full');
            } else if (dungeon.otherCleared) {
                slot.classList.add('completed-items');
            } else if (prizeCollected) {
                // Boss defeated but no chest clicked yet — green outline only.
                slot.classList.add('prize-obtained');
            }
        } else if (allItemsCollected && prizeCollected) {
            // Green — all items + prize collected (both modes)
            slot.classList.add('completed-full');
        } else if (allItemsCollected && !ksMode2) {
            // Standard: blue when all items collected
            slot.classList.add('completed-items');
        } else if (prizeCollected) {
            // Boss defeated but items remain — green outline only (no fill).
            slot.classList.add('prize-obtained');
        }
        // Notify map of completion state change
        if (typeof broadcastPrizes === 'function') setTimeout(broadcastPrizes, 50);
    }
}

function cycleItem(itemKey, slot) {
    const item = items[itemKey];
    item.currentState = (item.currentState + 1) % item.states.length;
    
    const newState = item.states[item.currentState];
    
    if (item.isGoMode) {
        if (newState.color === '#666') {
            slot.style.color = newState.color;
            slot.style.background = 'transparent';
        } else {
            slot.style.color = '#000';
            slot.style.background = newState.color;
        }
        slot.dataset.itemName = newState.name;
    } else {
        const img = slot.querySelector('img');
        img.src = newState.img;
        img.alt = newState.name;
        slot.dataset.itemName = newState.name;
    }

    // Broadcast updated item states to map
    broadcastItemSnap();

    // Item state changed — re-evaluate boss circle requirement colors
    refreshAllBossCircles();
    // …and the item-background fills (settings customization)
    if (window.refreshItemFills) window.refreshItemFills();
}

// Right-click on Go Mode: toggle directly between "Go Mode" (1) and
// "Go Mode Feeling" (2) without cycling through "Off". If currently Off,
// right-click jumps straight to "Go Mode Feeling".
function toggleGoModeFeeling(itemKey, slot) {
    const item = items[itemKey];
    item.currentState = (item.currentState === 2) ? 1 : 2;

    const newState = item.states[item.currentState];
    if (newState.color === '#666') {
        slot.style.color = newState.color;
        slot.style.background = 'transparent';
    } else {
        slot.style.color = '#000';
        slot.style.background = newState.color;
    }
    slot.dataset.itemName = newState.name;

    broadcastItemSnap();
    refreshAllBossCircles();
    if (window.refreshItemFills) window.refreshItemFills();
}

function broadcastItemSnap() {
    if (!window._itemsBc) return;
    var snap = {};
    var copyKeys = ['bow','boomerang','hookshot','bomb','mushroom','powder','firerod','icerod',
                    'bombos','ether','quake','lamp','hammer','shovel','flute','net','book',
                    'bottle1','bottle2','bottle3','bottle4',
                    'somaria','byrna','cape','mirror','boots','gloves','flippers',
                    'moonpearl','sword','shield','tunic','agahnim','halfmagic'];
    copyKeys.forEach(function(k) {
        if (items[k]) snap[k] = items[k].currentState;
    });
    // Derive bottle count for map logic (trackerItems.bottle)
    snap.bottle = ['bottle1','bottle2','bottle3','bottle4'].filter(k => items[k] && items[k].currentState > 0).length;
    // Compute crystal/pendant counts from DOM prize images (same as processInventoryData).
    // Reading from trackerItems here would always return 0 on the item-tracker side,
    // causing the map's greenPendant/redCrystal to be zeroed on every snap and making
    // Sahasrahla / Pyramid Fairy checks flash red after the prize is collected.
    (function() {
        var cc=0, rc=0, pc=0, gpc=0;
        Object.keys(typeof dungeons !== 'undefined' ? dungeons : {}).forEach(function(k) {
            var slot = document.querySelector('[data-dungeon-key="' + k + '"] .prize-img');
            if (!slot || !slot.src.includes('1.png')) return;
            var src = slot.src;
            if      (src.includes('greenpendant')) { pc++; gpc++; }
            else if (src.includes('pendant'))      { pc++; }
            else if (src.includes('redcrystal'))   { cc++; rc++; }
            else if (src.includes('crystal'))      { cc++; }
        });
        snap.crystals     = cc;
        snap.pendants     = pc;
        snap.greenPendant = gpc;
        snap.redCrystal   = rc;
    })();
    snap.mmMedallion  = (window.trackerItems && window.trackerItems.mmMedallion)  || 0;
    snap.trMedallion  = (window.trackerItems && window.trackerItems.trMedallion)  || 0;
    snap.ctSmallKeys  = (window.trackerItems && window.trackerItems.ctSmallKeys)  || 0;
    snap.spSmallKeys  = (window.trackerItems && window.trackerItems.spSmallKeys)  || 0;
    snap.dpSmallKeys  = (window.trackerItems && window.trackerItems.dpSmallKeys)  || 0;
    snap.tohSmallKeys  = (window.trackerItems && window.trackerItems.tohSmallKeys)  || 0;
    snap.podSmallKeys  = (window.trackerItems && window.trackerItems.podSmallKeys)  || 0;
    snap.ttSmallKeys  = (window.trackerItems && window.trackerItems.ttSmallKeys)  || 0;
    snap.ipSmallKeys  = (window.trackerItems && window.trackerItems.ipSmallKeys)  || 0;
    snap.mmSmallKeys  = (window.trackerItems && window.trackerItems.mmSmallKeys)  || 0;
    snap.trSmallKeys  = (window.trackerItems && window.trackerItems.trSmallKeys)  || 0;
    snap.swSmallKeys  = (window.trackerItems && window.trackerItems.swSmallKeys)  || 0;
    snap.gtSmallKeys  = (window.trackerItems && window.trackerItems.gtSmallKeys)  || 0;
    snap.epBigKey     = (window.trackerItems && window.trackerItems.epBigKey)     || 0;
    snap.dpBigKey     = (window.trackerItems && window.trackerItems.dpBigKey)     || 0;
    snap.tohBigKey     = (window.trackerItems && window.trackerItems.tohBigKey)     || 0;
    snap.podBigKey     = (window.trackerItems && window.trackerItems.podBigKey)     || 0;
    snap.ttBigKey     = (window.trackerItems && window.trackerItems.ttBigKey)     || 0;
    snap.ipBigKey     = (window.trackerItems && window.trackerItems.ipBigKey)     || 0;
    snap.mmBigKey     = (window.trackerItems && window.trackerItems.mmBigKey)     || 0;
    snap.trBigKey     = (window.trackerItems && window.trackerItems.trBigKey)     || 0;
    snap.spBigKey     = (window.trackerItems && window.trackerItems.spBigKey)     || 0;
    snap.swBigKey     = (window.trackerItems && window.trackerItems.swBigKey)     || 0;
    snap.gomode = items['gomode'] ? items['gomode'].currentState : 0;
    // Include dungeon prize and chest data
    var dngKeys = ['ep','dp','toh','pod','sp','sw','tt','ip','mm','tr','gt'];
    dngKeys.forEach(function(k) {
        var d = window.dungeons && window.dungeons[k];
        if (!d) return;
        snap[k+'Chests']        = d.itemCount       || 0;
        snap[k+'MaxChests']     = d.maxItems        || 0;
        snap[k+'BigKey']        = d.bigkeyState     || 0;
        snap[k+'Map']           = d.mapState        || 0;
        snap[k+'Compass']       = d.compassState    || 0;
        snap[k+'MaxSmallKeys']  = d.maxSmallKeys    || 0;
        snap[k+'BigKeyOnly']    = !!d.bigkeyOnly;
        // Boss state for the map's stripe overlay: send the selected boss
        // number (0 = unknown) and whether its item requirement is currently
        // met (always true for bosses with no requirement / unknown bosses).
        var _bossNum = d.bossState || 0;
        var _bossOk  = true;
        if (_bossNum > 0 && typeof BOSS_REQUIREMENTS !== 'undefined') {
            var _req = BOSS_REQUIREMENTS[_bossNum];
            _bossOk = _req ? !!_req() : true;
        }
        snap[k+'BossState'] = _bossNum;
        snap[k+'BossOk']    = _bossOk;
        // Get prize from DOM
        var prizeImg = document.querySelector('[data-dungeon-key="'+k+'"] .prize-img');
        if (prizeImg) {
            var src = prizeImg.src || '';
            var obtained = src.includes('1.png');
            var prizeName = 'crystal';
            if      (src.includes('greenpendant')) prizeName = 'greenpendant';
            else if (src.includes('pendant'))      prizeName = 'pendant';
            else if (src.includes('redcrystal'))   prizeName = 'redcrystal';
            else if (src.includes('unknown'))      prizeName = 'unknown';
            snap[k+'Prize']         = prizeName;
            snap[k+'PrizeObtained'] = obtained;
        }
    });
    snap.checks = parseInt((document.getElementById('toh-check-count')||{}).textContent||'0');
    snap.deaths = parseInt((document.getElementById('toh-death-count')||{}).textContent||'0');
    snap.bonks  = parseInt((document.getElementById('toh-bonk-count') ||{}).textContent||'0');
    window._itemsBc.postMessage({ type: 'items', data: snap });
}
window.broadcastItemSnap = broadcastItemSnap;

function cycleMedallionLabel(itemKey, slot) {
    const item = items[itemKey];
    // Default cycle — will be overridden by itemtracker.html with context-aware filtering
    const labels = ['', 'MM', 'TR', 'BOTH'];
    const currentIndex = labels.indexOf(item.medallionLabel);
    item.medallionLabel = labels[(currentIndex + 1) % labels.length];

    const labelDiv = slot.querySelector('.medallion-label');
    if (labelDiv) labelDiv.textContent = item.medallionLabel;
}

const SAVEDATA_START = 0xF5F000;

function connectWebSocket() {
    // In manual mode we never open a socket — the user tracks by hand.
    if (_trackingMode === 'manual') { updateConnectionStatus('Manual'); return; }
    // Close any existing socket cleanly before opening a new one
    if (ws) {
        ws.onopen = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;
        try { ws.close(); } catch(e) {}
        ws = null;
    }

    try {
        ws = new WebSocket(`ws://${wsHost}:${wsPort}`);
        ws.binaryType = 'arraybuffer';

        ws.onopen = () => {
            console.log('WebSocket connected - requesting device list');
            updateConnectionStatus('Connecting');
            _stopReconnect();
            ws.send(JSON.stringify({ Opcode: 'DeviceList', Space: 'SNES' }));
        };

        ws.onmessage = handleWebSocketMessage;

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            updateConnectionStatus('Error');
            _scheduleReconnect();
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            updateConnectionStatus('Disconnected');
            deviceAttached = false;
            _gamemodeValid = false;
            if (readTimer) { clearInterval(readTimer); readTimer = null; }
            _scheduleReconnect();
        };
    } catch (e) {
        console.error('Failed to create WebSocket connection:', e);
        updateConnectionStatus('Error');
        _scheduleReconnect();
    }
}

function _stopReconnect() {
    if (reconnectInterval) { clearTimeout(reconnectInterval); reconnectInterval = null; }
}

function _scheduleReconnect() {
    if (_trackingMode === 'manual') return;   // never auto-reconnect in manual mode
    _stopReconnect(); // always reset — ensures a clean single timer
    reconnectInterval = setTimeout(() => {
        reconnectInterval = null;
        console.log('Attempting to reconnect...');
        connectWebSocket();
    }, 5000);
}

function handleWebSocketMessage(event) {
    try {
        // Handle binary data (SRAM reads)
        if (event.data instanceof ArrayBuffer) {
            const data = new Uint8Array(event.data);
            // If we haven't confirmed gamemode yet, this is a gamemode check response
            if (!_gamemodeValid) {
                const gm = data[0];
                if (GAMEPLAY_MODES.indexOf(gm) !== -1 || KNOWN_ALTTP_MODES.indexOf(gm) !== -1) {
                    // Valid ALTTP mode (gameplay or menu/startup) — start SRAM reading
                    _gamemodeValid = true;
                    updateConnectionStatus('Connected');
                    startSRAMReading();
                } else {
                    // Unknown value — RetroArch not ready yet, retry DeviceList after 2s
                    updateConnectionStatus('No device found');
                    setTimeout(() => {
                        if (ws && ws.readyState === WebSocket.OPEN) {
                            ws.send(JSON.stringify({ Opcode: 'DeviceList', Space: 'SNES' }));
                        }
                    }, 2000);
                }
                return;
            }
            // Steady-state SRAM reads.  Discriminate by length: a 1-byte
            // response is the game-mode read we issue each cycle for the
            // timer window's benefit; everything else goes to processSRAMData.
            if (data.length === 1) {
                broadcastGamemode(data[0]);
                return;
            }
            processSRAMData(data);
            return;
        }
        
        // Handle JSON responses
        const response = JSON.parse(event.data);
        
        if (response.Results) {
            if (!deviceAttached) {
                // DeviceList response
                if (response.Results.length > 0) {
                    deviceName = response.Results[0];
                    console.log('Found device:', deviceName);
                    
                    // Attach to device
                    ws.send(JSON.stringify({
                        Opcode: 'Attach',
                        Space: 'SNES',
                        Operands: [deviceName]
                    }));
                    
                    deviceAttached = true;
                    _gamemodeValid = false;
                    updateConnectionStatus('Connected');

                    // Check gamemode first — wait for game to be running before reading SRAM
                    checkGamemode();
                } else {
                    updateConnectionStatus('No device found');
                    // Retry DeviceList automatically
                    clearTimeout(_deviceRetryTimer);
                    _deviceRetryTimer = setTimeout(() => {
                        if (ws && ws.readyState === WebSocket.OPEN) {
                            ws.send(JSON.stringify({ Opcode: 'DeviceList', Space: 'SNES' }));
                        }
                    }, 3000);
                }
            }
        }
    } catch (e) {
        console.error('Failed to handle WebSocket message:', e);
    }
}

function checkGamemode() {
    if (!ws || ws.readyState !== WebSocket.OPEN || !deviceAttached) return;
    ws.send(JSON.stringify({
        Opcode: 'GetAddress',
        Space: 'SNES',
        Operands: ['F50010', '01']
    }));
}

function startSRAMReading() {
    if (readTimer) {
        clearInterval(readTimer);
    }

    // Read SRAM every second
    readTimer = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN && deviceAttached) {
            // Game mode (1 byte). Read first so we can broadcast to the timer
            // window each cycle (lets the timer skip its own SNES poll when
            // the item tracker is feeding fresh data over BroadcastChannel).
            ws.send(JSON.stringify({
                Opcode: 'GetAddress',
                Space: 'SNES',
                Operands: ['F50010', '01']
            }));

            // Read inventory data (0x1ae bytes from F5F340)
            ws.send(JSON.stringify({
                Opcode: 'GetAddress',
                Space: 'SNES',
                Operands: [(SAVEDATA_START + 0x340).toString(16), '1ae']
            }));

            // Read full room/event data as single 0x500 read to guarantee ordering
            ws.send(JSON.stringify({
                Opcode: 'GetAddress',
                Space: 'SNES',
                Operands: [(SAVEDATA_START).toString(16), '500']
            }));
        }
    }, 1000);
}

// Push the latest game mode byte to any subscribers (timer window) so they
// can skip their own polling while we're feeding fresh data.
function broadcastGamemode(gm) {
    try {
        if (window._itemsBc) window._itemsBc.postMessage({ type: 'gamemode', data: gm });
    } catch (e) {}
}

let previousRoomData = null;
let roomChunk1 = null;        // first 0x280 chunk
let roomChunk1Time = 0;       // timestamp when chunk1 was stored

function processSRAMData(data) {
    if (data.length === 0x1ae) {
        processInventoryData(data);
    } else if (data.length === 0x280) {
        const now = Date.now();
        if (roomChunk1 === null || (now - roomChunk1Time) > 1500) {
            // No pending chunk, or the stored one is stale (>1.5s old) — store as first chunk
            roomChunk1 = data;
            roomChunk1Time = now;
        } else {
            // Have a fresh chunk1 — merge and process
            const merged = new Uint8Array(0x500);
            merged.set(roomChunk1, 0);
            merged.set(data, 0x280);
            roomChunk1 = null;
            roomChunk1Time = 0;
            processRoomData(merged);
        }
    } else if (data.length === 0x400 || data.length === 0x420 || data.length === 0x500) {
        processRoomData(data);
    }
}

function processRoomData(data) {
    // Check boss defeats and track chests
    for (const [key, dungeon] of Object.entries(dungeons)) {
        // Check boss defeat
        if (dungeon.bossAddr && dungeon.bossAddr < data.length) {
            const roomByte = data[dungeon.bossAddr];
            const bossDefeated = (roomByte & 0x08) !== 0;
            
            const slot = document.querySelector(`[data-dungeon-key="${key}"]`);
            if (slot && bossDefeated) {
                const prizeImg = slot.querySelector('.prize-img');
                if (prizeImg) {
                    const currentSrc = prizeImg.src;
                    if (currentSrc.includes('0.png')) {
                        prizeImg.src = currentSrc.replace('0.png', '1.png');
                        // Update completion status when prize is collected
                        updateDungeonCountDisplay(key);
                        updateBossCircle(key);   // grey out the boss image — boss defeated
                        if (typeof window.onPrizeCycled === 'function') window.onPrizeCycled();
                    }
                }
            }
        }
        
        // Track chests using [room, bitmask] locations
        if (dungeon.locations) {
            let chestsOpened = 0;
            
            for (const [room, bitmask] of dungeon.locations) {
                // For floor item locations (0x04): check both the floor pickup flag AND
                // chest-open flag (0x10) since KS mode places a chest there instead
                const effectiveMask = (bitmask === 0x04) ? (0x04 | 0x10) : bitmask;
                if (room < data.length && (data[room] & effectiveMask) !== 0) {
                    chestsOpened++;
                }
            }

            // High-water mark: chest count never goes down (handles flickering SRAM on BizHawk etc.)
            chestsOpened = Math.max(chestsOpened, dungeons[key].chestsMax || 0);
            dungeons[key].chestsMax = chestsOpened;
            
            // Calculate items = total chests - dungeon items - small keys
            // Subtract only items that are NOT shuffled into the general pool for this mode
            const diMode = (new URLSearchParams(window.location.search).get('dungeonitems') || localStorage.getItem('alttp-dungeon-items') || 'standard');
            const ksMode = diMode === 'keysanity';
            const mcMode = diMode === 'mapcompass';
            const mckMode = diMode === 'mapcompasskeys';
            let items;
            if (ksMode) {
                // KS: everything shuffled — count all chests raw
                items = chestsOpened;
            } else if (mckMode) {
                // MCK: map/compass/keys shuffled but big key stays — subtract big key only
                const bigKey = dungeon.bigkeyState > 0 ? 1 : 0;
                items = chestsOpened - bigKey;
            } else {
                let dungeonItems = 0;
                if (!mcMode && dungeon.compassState > 0) dungeonItems++; // compass is shuffled in MC+
                if (!mcMode && dungeon.mapState > 0) dungeonItems++;     // map is shuffled in MC+
                if (dungeon.bigkeyState > 0) dungeonItems++;
                // Use the high-water mark of small keys ever held so that using a key
                // doesn't cause the chest subtraction to drop and inflate the item count.
                // In standard/MC mode, cap at maxSmallKeys to prevent over-counting when
                // the floor item (0x04) also increments the SRAM small key counter.
                const smallKeys = dungeon.smallKeyMax || dungeon.smallKeyCount;
                const smallKeySubtract = Math.min(smallKeys, dungeon.maxSmallKeys);
                items = chestsOpened - dungeonItems - smallKeySubtract;
            }
            if (items < 0) items = 0;
            // Hard cap at maxItems. DP / ToH / GT have a floor-item location
            // (0x04 mask) that can briefly count toward chestsOpened before the
            // SRAM small-key counter ticks up, which would otherwise let the
            // subtraction lag and render e.g. 3/2. The cap keeps the displayed
            // value within bounds for every dungeon regardless of mode.
            if (items > dungeon.maxItems) items = dungeon.maxItems;

            // Update if changed
            if (items !== dungeon.itemCount) {
                dungeons[key].itemCount = items;
                updateDungeonCountDisplay(key);
            }
        }
    }
    
    previousRoomData = new Uint8Array(data);

    // Broadcast room data to map window via BroadcastChannel
    if (window._itemsBc) {
        window._itemsBc.postMessage({ type: 'rooms', data: Array.from(data) });
    }
}

function processInventoryData(data) {
    try {
    // Data starts at offset 0x340 in SRAM, we read up to 0x38F
    const changed = (offset) => {
        return !previousSRAM || data[offset] !== previousSRAM[offset];
    };
    
    // newbit: fires when a bit is set that wasn't set before
    // On first connect (!previousSRAM), read all items regardless to get current state
    const isFirstRead = !previousSRAM;
    const newbit = (offset, mask) => {
        if (isFirstRead) return (data[offset] & mask) !== 0;
        return changed(offset) && (data[offset] & mask) !== 0 && (previousSRAM[offset] & mask) === 0;
    };
    
    // Helper: only update if new state >= current (prevents blanking during save/quit menu)
    const updateIfBetter = (key, newState) => {
        if (newState >= items[key].currentState) updateItemState(key, newState);
    };

    // Based on autot.js tracking logic
    if (changed(0x00)) { // 0x340 - Bow
        const bowValue = data[0x00];
        const bowState = bowValue === 0x00 ? 0 : bowValue === 0x01 ? 1 : bowValue === 0x02 ? 2 : 3;
        updateIfBetter('bow', bowState);
    }
    
    // Boomerang
    if (changed(0x4C)) {
        const bits = data[0x4C] & 0xC0;
        if (bits === 0x80) updateIfBetter('boomerang', 1);
        else if (bits === 0x40) updateIfBetter('boomerang', 2);
        else if (bits === 0xC0) updateIfBetter('boomerang', 3);
        else if (changed(0x01)) updateIfBetter('boomerang', data[0x01]);
    }
    if (newbit(0x02, 0x01)) updateItemState('hookshot', 1); // 0x342
    if (changed(0x03)) {
        if (data[0x03] > 0) {
            // Bombs present — cancel any pending clear and ensure state is on
            if (_bombClearTimer) { clearTimeout(_bombClearTimer); _bombClearTimer = null; }
            updateIfBetter('bomb', 1);
        } else if (items['bomb'].currentState > 0) {
            // Bombs read as 0 but tracker shows them — debounce 5s before clearing
            // to avoid save/quit SRAM blips removing bombs mid-game
            if (!_bombClearTimer) {
                _bombClearTimer = setTimeout(function() {
                    _bombClearTimer = null;
                    updateItemState('bomb', 0);
                }, 5000);
            }
        }
    }
    
    // Mushroom/Powder - check randomizer logic first (0x38c)
    if (changed(0x4C)) { // 0x38C - Randomizer mushroom/powder/flute/shovel tracking
        const bits38c = data[0x4C];
        
        // Mushroom tracking
        const mushroomBits = bits38c & 0x28;
        if (mushroomBits === 0x28) updateItemState('mushroom', 1);
        else if (mushroomBits === 0x08) updateItemState('mushroom', 2);
        // Don't zero mushroom — it stays
        
        // Powder tracking - never remove
        if (bits38c & 0x10) updateItemState('powder', 1);
        
        // Flute tracking (bits 0x03)
        const fluteState = bits38c & 0x03;
        if (fluteState === 0x01 || fluteState === 0x03) updateItemState('flute', 2);
        else if (fluteState === 0x02) updateIfBetter('flute', 1);
        // Don't zero flute
        
        // Shovel tracking - once obtained, it stays (bit 0x04)
        if ((bits38c & 0x04) && items.shovel.currentState === 0) {
            updateItemState('shovel', 1);
        }
    } // else if (changed(0x04)) { // 0x344 - Vanilla mushroom/powder
      //  const powderValue = data[0x04];
      //  if (powderValue === 0x01) {
      //      updateItemState('mushroom', 1);
      //     updateItemState('powder', 0);
      //  } else if (powderValue === 0x02) {
      //      updateItemState('powder', 1);
      //      updateItemState('mushroom', 2);
      //  } else {
      //      updateItemState('mushroom', 0);
      //      updateItemState('powder', 0);
      //  }
    // }
    
    if (newbit(0x05, 0x01)) updateItemState('firerod', 1); // 0x345
    if (newbit(0x06, 0x01)) updateItemState('icerod', 1); // 0x346
    if (newbit(0x07, 0x01)) updateItemState('bombos', 1); // 0x347
    if (newbit(0x08, 0x01)) updateItemState('ether', 1); // 0x348
    if (newbit(0x09, 0x01)) updateItemState('quake', 1); // 0x349
    if (newbit(0x0A, 0x01)) updateItemState('lamp', 1); // 0x34A
    if (newbit(0x0B, 0x01)) updateItemState('hammer', 1); // 0x34B
    if (newbit(0x0D, 0x01)) updateItemState('net', 1); // 0x34D
    if (newbit(0x0E, 0x01)) updateItemState('book', 1); // 0x34E
    
    // Bottles 0x35C-0x35F — track contents of each bottle individually
    // SRAM values: 0x00=none, 0x02=empty, 0x03=red, 0x04=green, 0x05=blue, 0x06=fairy, 0x07=bee, 0x08=goodbee
    const bottleContentMap = { 0x00: 0, 0x02: 1, 0x03: 2, 0x04: 3, 0x05: 4, 0x06: 5, 0x07: 6, 0x08: 7 };
    const bottleKeys = ['bottle1', 'bottle2', 'bottle3', 'bottle4'];
    for (let i = 0; i < 4; i++) {
        const val = data[0x1C + i];
        const state = bottleContentMap[val] !== undefined ? bottleContentMap[val] : 0;
        // Only update if obtained (state > 0) or bottle was never obtained
        if (state > 0 || items[bottleKeys[i]].currentState === 0) {
            updateItemState(bottleKeys[i], state);
        }
    }
    // Update trackerItems.bottle count for map logic compatibility
    if (window.trackerItems) {
        window.trackerItems.bottle = bottleKeys.filter((k, i) => data[0x1C + i] > 0).length;
    }
    
    if (newbit(0x10, 0x01)) updateItemState('somaria', 1); // 0x350
    if (newbit(0x11, 0x01)) updateItemState('byrna', 1); // 0x351
    if (newbit(0x12, 0x01)) updateItemState('cape', 1); // 0x352
    if (newbit(0x13, 0x02)) updateItemState('mirror', 1); // 0x353
    
    if (changed(0x14)) updateIfBetter('gloves', data[0x14]); // 0x354
    if (newbit(0x15, 0x01)) updateItemState('boots', 1); // 0x355
    if (newbit(0x16, 0x01)) updateItemState('flippers', 1); // 0x356
    if (newbit(0x17, 0x01)) updateItemState('moonpearl', 1); // 0x357
    if (changed(0x19)) updateIfBetter('sword', data[0x19] === 0xFF ? 0 : data[0x19]); // 0x359
    if (changed(0x1A)) updateIfBetter('shield', data[0x1A]); // 0x35A
    if (changed(0x1B)) updateIfBetter('tunic', data[0x1B]); // 0x35B
    if (changed(0x3B)) { if (data[0x3B] > 0) updateItemState('halfmagic', 1); } // 0x37B - never remove halfmagic
    
    // Agahnim tracking (0x3C5 - offset 0x85 from 0x340)
    if (changed(0x85)) {
        if (data[0x85] >= 3) updateItemState('agahnim', 1); // Defeated — never go back to 0
    }
    
    // Small key tracking for dungeons (0x4E0-0x4ED range)
    for (const [key, dungeon] of Object.entries(dungeons)) {
        if (dungeon.smallKeyAddr) {
            const keyOffset = dungeon.smallKeyAddr - 0x340;
            if (keyOffset >= 0 && keyOffset < data.length && changed(keyOffset)) {
                const rawKeyCount = data[keyOffset];
                const keyCount = (dungeon.maxSmallKeys > 0) ? Math.min(rawKeyCount, dungeon.maxSmallKeys) : rawKeyCount;
                // When autotracking, only increase (protects against save/quit zeroing)
                // When manual, allow decrease so right-click works
                const shouldUpdate = deviceAttached ? keyCount > (dungeons[key].smallKeyCount || 0) : keyCount !== dungeons[key].smallKeyCount;
                if (shouldUpdate) {
                    dungeons[key].smallKeyCount = keyCount;
                    if (keyCount > (dungeons[key].smallKeyMax || 0)) {
                        dungeons[key].smallKeyMax = keyCount;
                    }
                    updateDungeonCountDisplay(key);
                }
            }
        }
    }
    
    // Big key, Compass, and Map tracking (0x364-0x369)
    // Check bytes 0x24-0x29 (offsets from 0x340)
    if (changed(0x24) || changed(0x25) || changed(0x26) || changed(0x27) || changed(0x28) || changed(0x29)) {
        for (const [key, dungeon] of Object.entries(dungeons)) {
            const slot = document.querySelector(`[data-dungeon-key="${key}"]`);
            if (!slot) continue;
            
            // Big key tracking
            const bigkeyOffset = dungeon.bigkeyAddr - 0x340;
            if (bigkeyOffset >= 0 && bigkeyOffset < data.length) {
                const bigkeyByte = data[bigkeyOffset];
                const hasBigKey = (bigkeyByte & dungeon.bigkeyMask) !== 0;
                
                if (hasBigKey && dungeons[key].bigkeyState === 0) {
                    dungeons[key].bigkeyState = 1;
                    const bigkeyImg = slot.querySelector('.bigkey-img');
                    if (bigkeyImg) {
                        bigkeyImg.src = `${BASE_URL}/bigkey1.png`;
                    }
                    updateDungeonCountDisplay(key);
                    if (window.broadcastItemSnap) window.broadcastItemSnap();
                }
            }
            
            // Compass tracking
            const compassOffset = dungeon.compassAddr - 0x340;
            if (compassOffset >= 0 && compassOffset < data.length) {
                const compassByte = data[compassOffset];
                const hasCompass = (compassByte & dungeon.compassMask) !== 0;
                
                if (hasCompass && dungeons[key].compassState === 0) {
                    dungeons[key].compassState = 1;
                    const compassImg = slot.querySelector('.compass-img');
                    if (compassImg) {
                        compassImg.src = `${BASE_URL}/compass1.png`;
                    }
                    // Recalculate chest item count now that compass is subtracted.
                    updateDungeonCountDisplay(key);
                    if (window.broadcastItemSnap) window.broadcastItemSnap();
                }
            }

            // Map tracking
            const mapOffset = dungeon.mapAddr - 0x340;
            if (mapOffset >= 0 && mapOffset < data.length) {
                const mapByte = data[mapOffset];
                const hasMap = (mapByte & dungeon.mapMask) !== 0;

                if (hasMap && dungeons[key].mapState === 0) {
                    dungeons[key].mapState = 1;
                    const mapImg = slot.querySelector('.map-img');
                    if (mapImg) {
                        mapImg.src = `${BASE_URL}/map1.png`;
                    }
                    // Recalculate chest item count now that map is subtracted.
                    updateDungeonCountDisplay(key);
                    // Notify map window so it can show map1.png as prize placeholder
                    if (typeof broadcastPrizes === 'function') setTimeout(broadcastPrizes, 50);
                    if (window.broadcastItemSnap) window.broadcastItemSnap();
                }
            }
        }
    }
    
    } catch(e) { console.error('processInventoryData error:', e); }
    
    // Store current data for next comparison
    previousSRAM = new Uint8Array(data);

    // Broadcast item states to map window via BroadcastChannel
    if (window._itemsBc) {
        var snap = {};
        var copyKeys = ['bow','boomerang','hookshot','bomb','mushroom','powder','firerod','icerod',
                        'bombos','ether','quake','lamp','hammer','shovel','flute','net','book',
                        'bottle1','bottle2','bottle3','bottle4',
                        'somaria','byrna','cape','mirror','boots','gloves','flippers',
                        'moonpearl','sword','shield','tunic','agahnim','halfmagic'];
        copyKeys.forEach(function(k) {
            if (items[k]) snap[k] = items[k].currentState;
        });
        snap.bottle = ['bottle1','bottle2','bottle3','bottle4'].filter(k => items[k] && items[k].currentState > 0).length;
        // Crystal count from trackerItems if available, else from items
        snap.crystals = (window.trackerItems && window.trackerItems.crystals) || 0;
        snap.mmMedallion = (window.trackerItems && window.trackerItems.mmMedallion) || 0;
        snap.trMedallion = (window.trackerItems && window.trackerItems.trMedallion) || 0;
        snap.ctSmallKeys = (window.trackerItems && window.trackerItems.ctSmallKeys) || 0;
        snap.spSmallKeys = (window.trackerItems && window.trackerItems.spSmallKeys) || 0;
        snap.dpSmallKeys  = (window.trackerItems && window.trackerItems.dpSmallKeys)  || 0;
        snap.tohSmallKeys  = (window.trackerItems && window.trackerItems.tohSmallKeys)  || 0;
        snap.podSmallKeys  = (window.trackerItems && window.trackerItems.podSmallKeys)  || 0;
        snap.ttSmallKeys  = (window.trackerItems && window.trackerItems.ttSmallKeys)  || 0;
        snap.ipSmallKeys  = (window.trackerItems && window.trackerItems.ipSmallKeys)  || 0;
        snap.mmSmallKeys  = (window.trackerItems && window.trackerItems.mmSmallKeys)  || 0;
        snap.trSmallKeys  = (window.trackerItems && window.trackerItems.trSmallKeys)  || 0;
        snap.swSmallKeys  = (window.trackerItems && window.trackerItems.swSmallKeys)  || 0;
        snap.gtSmallKeys  = (window.trackerItems && window.trackerItems.gtSmallKeys)  || 0;
        snap.epBigKey     = (window.trackerItems && window.trackerItems.epBigKey)     || 0;
        snap.dpBigKey     = (window.trackerItems && window.trackerItems.dpBigKey)     || 0;
        snap.tohBigKey     = (window.trackerItems && window.trackerItems.tohBigKey)     || 0;
        snap.podBigKey     = (window.trackerItems && window.trackerItems.podBigKey)     || 0;
        snap.ttBigKey     = (window.trackerItems && window.trackerItems.ttBigKey)     || 0;
        snap.ipBigKey     = (window.trackerItems && window.trackerItems.ipBigKey)     || 0;
        snap.mmBigKey     = (window.trackerItems && window.trackerItems.mmBigKey)     || 0;
        snap.trBigKey     = (window.trackerItems && window.trackerItems.trBigKey)     || 0;
        snap.spBigKey     = (window.trackerItems && window.trackerItems.spBigKey)     || 0;
        snap.swBigKey     = (window.trackerItems && window.trackerItems.swBigKey)     || 0;
        // GT big key: read directly from dungeons object (bigkeyState tracked via SRAM/click).
        // This inline snap omitted gtBigKey, causing the map to reset it to 0 on every SRAM
        // poll tick — producing the green/yellow flash in entrance shuffle keysanity mode.
        snap.gtBigKey     = (dungeons.gt && dungeons.gt.bigkeyState) || 0;


        // Count obtained prizes from dungeon slots for check logic
        // prizeState tells us the TYPE
        // Standard:   0=crystal,1=redcrystal,2=pendant,3=greenpendant
        // Key Sanity: 0=unknown,1=crystal,2=redcrystal,3=pendant,4=greenpendant,5=unknown(obtained)
        var crystalCount = 0, redCrystalCount = 0, pendantCount = 0, greenPendantCount = 0;
        Object.keys(dungeons).forEach(function(key) {
            var d = dungeons[key];
            var slot = document.querySelector('[data-dungeon-key="' + key + '"]');
            var obtained = false;
            var prizeName = 'unknown';
            if (slot) {
                var prizeImg = slot.querySelector('.prize-img');
                obtained = prizeImg && prizeImg.src.includes('1.png');
                var src = prizeImg ? prizeImg.src : '';
                if      (src.includes('greenpendant')) prizeName = 'greenpendant';
                else if (src.includes('pendant'))      prizeName = 'pendant';
                else if (src.includes('redcrystal'))   prizeName = 'redcrystal';
                else if (src.includes('crystal'))      prizeName = 'crystal';
            }
            if (!obtained) return;
            if      (prizeName === 'crystal')      crystalCount++;
            else if (prizeName === 'redcrystal')   { crystalCount++; redCrystalCount++; }
            else if (prizeName === 'pendant')      pendantCount++;
            else if (prizeName === 'greenpendant') { pendantCount++; greenPendantCount++; }
        });
        snap.redCrystal   = redCrystalCount;
        snap.crystals     = crystalCount;
        snap.pendants     = pendantCount;
        snap.greenPendant = greenPendantCount;
        window._itemsBc.postMessage({ type: 'items', data: snap });
    }

    // Check count (SRAM 0xF5F423 = inv offset 0xE3) and death count (0xF5F449 = inv offset 0x109)
    const checkEl = document.getElementById('toh-check-count');
    const deathEl = document.getElementById('toh-death-count');
    if (checkEl && 0xE3 < data.length) {
        const newChecks = data[0xE3];
        if (newChecks >= parseInt(checkEl.textContent || '0')) {
            checkEl.textContent = newChecks;
            if (window._itemsBc) window._itemsBc.postMessage({ type: 'stats', checks: newChecks, deaths: parseInt((document.getElementById('toh-death-count')||{}).textContent||'0'), bonks: parseInt((document.getElementById('toh-bonk-count')||{}).textContent||'0') });
        }
    }
    if (deathEl && 0x10a < data.length) {
        const deaths = data[0x109] | (data[0x10a] << 8);
        if (deaths >= parseInt(deathEl.textContent || '0')) {
            deathEl.textContent = deaths;
            if (window._itemsBc) window._itemsBc.postMessage({ type: 'stats', checks: parseInt((document.getElementById('toh-check-count')||{}).textContent||'0'), deaths: deaths, bonks: parseInt((document.getElementById('toh-bonk-count')||{}).textContent||'0') });
        }
    }
    // Bonk count (SRAM 0xF5F420 = inv offset 0xE0)
    const bonkEl = document.getElementById('toh-bonk-count');
    if (bonkEl && 0xE0 < data.length) {
        const newBonks = data[0xE0];
        if (newBonks >= parseInt(bonkEl.textContent || '0')) {
            bonkEl.textContent = newBonks;
            if (window._itemsBc) window._itemsBc.postMessage({ type: 'stats', checks: parseInt((document.getElementById('toh-check-count')||{}).textContent||'0'), deaths: parseInt((document.getElementById('toh-death-count')||{}).textContent||'0'), bonks: newBonks });
        }
    }
    // Heart piece count (SRAM 0xF5F36B = inv offset 0x2B) — pieces toward the
    // next heart container. Rolls 0..4 so there's no high-water mark; just
    // clamp to guard against garbage SRAM reads during menus / save & quit.
    const heartEl = document.getElementById('toh-heartpiece-count');
    if (heartEl && 0x2B < data.length) {
        let hp = data[0x2B];
        if (hp > 4) hp = 4;
        if (hp < 0) hp = 0;
        heartEl.textContent = hp + '/4';
    }
    // Revival count (SRAM 0xF5F453 = inv offset 0x113). Cumulative counter, so
    // use a high-water mark like checks/deaths/bonks — only ever increases,
    // which also guards against garbage SRAM reads.
    const revivalEl = document.getElementById('toh-revival-count');
    if (revivalEl && 0x113 < data.length) {
        const newRevivals = data[0x113];
        if (newRevivals >= parseInt(revivalEl.textContent || '0')) {
            revivalEl.textContent = newRevivals;
        }
    }
    // CT small key count (SRAM 0xF5F4E4 = inv offset 0x1a4) — Key Sanity only
    // Use high water mark so count doesn't drop when keys are used
    const ctKeyEl = document.getElementById('toh-ctkey-count');
    if (0x1a4 < data.length) {
        const ctKeysRaw = data[0x1a4];
        if (!window.trackerItems) window.trackerItems = {};
        const prev = window.trackerItems.ctSmallKeysMax || 0;
        const ctKeys = Math.max(ctKeysRaw, prev);
        window.trackerItems.ctSmallKeysMax = ctKeys;
        window.trackerItems.ctSmallKeys = ctKeys;
        if (ctKeyEl) {
            ctKeyEl.textContent = ctKeys + '/2';
            ctKeyEl.style.color = ctKeys >= 2 ? '#2ecc71' : '';
        }
    }
    // SP small key count (SRAM 0xF5F4E5 = inv offset 0x1a5) — KS/MCK map logic
    if (0x1a5 < data.length) {
        if (!window.trackerItems) window.trackerItems = {};
        const spRaw = data[0x1a5];
        const spPrev = window.trackerItems.spSmallKeysMax || 0;
        const spKeys = Math.max(spRaw, spPrev);
        window.trackerItems.spSmallKeysMax = spKeys;
        window.trackerItems.spSmallKeys = spKeys;
    }
    // Remaining dungeon small key counts — KS/MCK map logic (high water mark)
    const _skDungeons = [
        { key: 'dp',  offset: 0x1a3 },
        { key: 'toh', offset: 0x1aa },
        { key: 'pod', offset: 0x1a6 },
        { key: 'tt',  offset: 0x1ab },
        { key: 'ip',  offset: 0x1a9 },
        { key: 'mm',  offset: 0x1a7 },
        { key: 'tr',  offset: 0x1ac },
        { key: 'sw',  offset: 0x1a8 },
        { key: 'gt',  offset: 0x1ad },
    ];
    if (!window.trackerItems) window.trackerItems = {};
    _skDungeons.forEach(function(d) {
        if (d.offset < data.length) {
            const raw = data[d.offset];
            const prev = window.trackerItems[d.key + 'SmallKeysMax'] || 0;
            const val = Math.max(raw, prev);
            window.trackerItems[d.key + 'SmallKeysMax'] = val;
            window.trackerItems[d.key + 'SmallKeys'] = val;
        }
    });
    // Big key states — read from dungeon bigkeyState (already tracked via SRAM in processRoomData)
    // Expose on trackerItems for map logic
    const _bkDungeons = ['ep','dp','toh','pod','sp','sw','tt','ip','mm','tr'];
    _bkDungeons.forEach(function(k) {
        if (dungeons[k]) {
            window.trackerItems[k + 'BigKey'] = dungeons[k].bigkeyState || 0;
        }
    });
}

function updateItemState(itemKey, state) {
    const item = items[itemKey];
    if (!item || item.isGoMode) return;
    
    // Ensure state is within valid range
    state = Math.min(state, item.states.length - 1);
    item.currentState = state;
    
    const slot = document.querySelector(`[data-item-key="${itemKey}"]`);
    if (slot) {
        const img = slot.querySelector('img');
        if (!img) return;
        const newState = item.states[item.currentState];
        img.src = newState.img;
        img.alt = newState.name;
        slot.dataset.itemName = newState.name;
    }

    // Autotracker updated an item — re-evaluate boss circle requirement colors
    refreshAllBossCircles();
    // …and the item-background fills (settings customization)
    if (window.refreshItemFills) window.refreshItemFills();
    // Push updated bossOk state to map so stripe clears when autotracker
    // grants a boss-required item (e.g. icerod unlocking Trinexx stripe).
    if (window.broadcastItemSnap) window.broadcastItemSnap();
}

function resetItemTracker() {
    // Reset all item states to default
    Object.keys(items).forEach(function(key) {
        items[key].currentState = 0;
        const slot = document.querySelector(`[data-item-key="${key}"]`);
        if (!slot) return;
        if (items[key].isGoMode) {
            slot.style.color = items[key].states[0].color;
            slot.style.background = 'transparent';
        } else {
            const img = slot.querySelector('img');
            if (img) { img.src = items[key].states[0].img; img.alt = items[key].states[0].name; }
        }
        if (['bombos','ether','quake'].includes(key)) {
            items[key].medallionLabel = '';
            const lbl = slot.querySelector('.medallion-label');
            if (lbl) lbl.textContent = '';
        }
    });

    // Reset all dungeon states
    const _ksMode = (new URLSearchParams(window.location.search).get('dungeonitems') || localStorage.getItem('alttp-dungeon-items') || 'standard');
    const _isShuffled = ['keysanity','mapcompass','mapcompasskeys','other'].includes(_ksMode);
    Object.keys(dungeons).forEach(function(key) {
        const d = dungeons[key];
        d.smallKeyCount = 0;
        d.smallKeyMax   = 0;
        d.itemCount     = 0;
        d.chestsMax     = 0;
        d.bigkeyState   = 0;
        d.compassState  = 0;
        d.mapState      = 0;
        d.prizeState    = 0;
        d.bossState     = 0;
        d.otherCleared  = false;
        const slot = document.querySelector(`[data-dungeon-key="${key}"]`);
        if (!slot) return;
        // Reset prize image
        const prizeImg = slot.querySelector('.prize-img');
        if (prizeImg) prizeImg.src = `${BASE_URL}/${_isShuffled ? 'unknown0.png' : 'crystal0.png'}`;
        // Reset bigkey/compass/map icons
        const bigkeyImg = slot.querySelector('.bigkey-img');
        if (bigkeyImg) bigkeyImg.src = `${BASE_URL}/bigkey0.png`;
        const compassImg = slot.querySelector('.compass-img');
        if (compassImg) compassImg.src = `${BASE_URL}/compass0.png`;
        const mapImg = slot.querySelector('.map-img');
        if (mapImg) mapImg.src = `${BASE_URL}/map0.png`;
        // Reset other chest
        const otherChest = slot.querySelector('.other-chest');
        if (otherChest) otherChest.src = `${BASE_URL}/chest0.png`;
        updateDungeonCountDisplay(key);
        // Reset boss circle back to boss0 (neutral)
        updateBossCircle(key);
    });

    // Reset stats display
    var checkEl = document.getElementById('toh-check-count');
    var deathEl = document.getElementById('toh-death-count');
    var bonkEl  = document.getElementById('toh-bonk-count');
    var heartEl = document.getElementById('toh-heartpiece-count');
    var revivalEl = document.getElementById('toh-revival-count');
    if (checkEl) checkEl.textContent = '0';
    if (deathEl) deathEl.textContent = '0';
    if (bonkEl)  bonkEl.textContent  = '0';
    if (heartEl) heartEl.textContent = '0/4';
    if (revivalEl) revivalEl.textContent = '0';

    // Reset SRAM state so autotracking picks up fresh
    if (_bombClearTimer) { clearTimeout(_bombClearTimer); _bombClearTimer = null; }
    previousSRAM = null;
    previousRoomData = null;
    roomChunk1 = null;
    roomChunk1Time = 0;
    if (window.trackerItems) {
        window.trackerItems.bottle       = 0;
        window.trackerItems.crystals     = 0;
        window.trackerItems.pendants     = 0;
        window.trackerItems.greenPendant = 0;
        window.trackerItems.redCrystal   = 0;
        // Medallion assignments (MM / TR labels on bombos/ether/quake). The
        // item tracker's own labels are cleared above, but trackerItems is
        // what broadcastItemSnap sends to the broadcast view — without this,
        // the snap re-applies the old assignment after the newgame resetAll
        // already cleared the labels there.
        window.trackerItems.mmMedallion  = 0;
        window.trackerItems.trMedallion  = 0;
        // Reset every dungeon's per-dungeon small-key tracking. Previously
        // only CT and SP were cleared here, so the other nine dungeons kept
        // their stale *SmallKeysMax across New Game. Because the auto-tracker
        // updates trackerItems via Math.max(raw, prev), a stale prev (e.g. 85
        // from RetroArch garbage during save & quit) would never decrease
        // back to 0 — and the broadcast view, which reads small keys from
        // trackerItems, would show "85/1" while the item tracker (which
        // reads from dungeons[k].smallKeyCount) correctly showed 0.
        ['ct','sp','dp','toh','pod','sw','tt','ip','mm','tr','gt'].forEach(function(k) {
            window.trackerItems[k + 'SmallKeys']    = 0;
            window.trackerItems[k + 'SmallKeysMax'] = 0;
        });
        // While we're here, also clear the per-dungeon BigKey trackerItems
        // entries so the same staleness can't bite us on big-key visuals.
        ['ep','dp','toh','pod','sp','sw','tt','ip','mm','tr','gt'].forEach(function(k) {
            window.trackerItems[k + 'BigKey'] = 0;
        });
    }

    // If boss shuffle is off, re-seed vanilla bosses — resetItemTracker wiped them
    // and DOMContentLoaded won't fire again, so we must reapply manually.
    if (window._bossShuffle === 'no' && typeof setBoss === 'function') {
        var VANILLA_BOSSES = {
            ep: 1, dp: 2, toh: 3, pod: 4, sp: 5,
            sw: 6, tt: 7, ip: 8, mm: 9, tr: 10
        };
        Object.keys(VANILLA_BOSSES).forEach(function(key) {
            setBoss(key, VANILLA_BOSSES[key]);
        });
    }

    // Broadcast reset to map (guard prevents infinite loop)
    // Only broadcast if we weren't triggered BY a newgame message (avoid loop)
    if (!window._itemsResettingGame && window._itemsBc) window._itemsBc.postMessage({ type: 'newgame' });
    setTimeout(function() {}, 0); // yield before snap
    if (window.broadcastItemSnap) window.broadcastItemSnap();
    if (typeof broadcastPrizes === 'function') setTimeout(broadcastPrizes, 50);
    // Clear item-background fills now that every item is back to state 0
    if (window.refreshItemFills) window.refreshItemFills();
}

function manualReconnect() {
    const btn = document.getElementById('item-reconnect-btn') || document.querySelector('.reconnect-btn');
    if (btn) { btn.classList.add('reconnecting'); btn.disabled = true; }
    _stopReconnect();
    if (readTimer) { clearInterval(readTimer); readTimer = null; }
    deviceAttached = false;
    previousSRAM = null;
    updateConnectionStatus('Connecting');
    connectWebSocket(); // connectWebSocket now closes stale socket itself
    setTimeout(() => {
        if (btn) { btn.classList.remove('reconnecting'); btn.disabled = false; }
    }, 3000);
}

// Fully tear down the live connection so nothing overwrites manual edits.
function _disconnectTracking() {
    _stopReconnect();
    if (readTimer) { clearInterval(readTimer); readTimer = null; }
    if (typeof _deviceRetryTimer !== 'undefined' && _deviceRetryTimer) {
        clearTimeout(_deviceRetryTimer); _deviceRetryTimer = null;
    }
    deviceAttached = false;
    _gamemodeValid = false;
    if (ws) {
        ws.onopen = ws.onmessage = ws.onerror = ws.onclose = null;
        try { ws.close(); } catch (e) {}
        ws = null;
    }
}

// Switch between 'auto' (live memory poll) and 'manual' (hand tracking).
function setTrackingMode(mode) {
    _trackingMode = (mode === 'manual') ? 'manual' : 'auto';
    try { localStorage.setItem('alttp-tracking-mode', _trackingMode); } catch (e) {}
    _syncModeToggleUI();
    if (_trackingMode === 'manual') {
        _disconnectTracking();
        updateConnectionStatus('Manual');
    } else {
        // reconnect and resume live tracking
        previousSRAM = null;
        updateConnectionStatus('Connecting');
        connectWebSocket();
    }
}

function toggleTrackingMode() {
    setTrackingMode(_trackingMode === 'auto' ? 'manual' : 'auto');
}

// Reflect current mode on the toggle button (label + styling), if present.
function _syncModeToggleUI() {
    const btn = document.getElementById('item-mode-toggle');
    if (!btn) return;
    if (_trackingMode === 'manual') {
        btn.textContent = '✋ Manual';
        btn.title = 'Manual tracking — tap to switch to Auto (live)';
        btn.style.background = '#3a2a1a';
        btn.style.color = '#f5b87a';
        btn.style.borderColor = '#7a4e2a';
    } else {
        btn.textContent = '⟲ Auto';
        btn.title = 'Auto tracking (live) — tap to switch to Manual';
        btn.style.background = '#1a2e4a';
        btn.style.color = '#7ab8f5';
        btn.style.borderColor = '#2a4e7a';
    }
}

function ensureBottomBar() {
    // Bottom bar is in itemtracker.html — nothing to create
}

// Keep alias for legacy calls
function ensureReconnectButton() { ensureBottomBar(); }

function updateConnectionStatus(status) {
    let statusDiv = document.getElementById('item-conn-status') ||
                    document.querySelector('.connection-status');
    if (!statusDiv) return;
    
    const statusText = {
        'Connected': '● Connected',
        'Connecting': '○ Connecting',
        'Disconnected': '○ Disconnected',
        'Error': '○ Error',
        'No device found': '○ No device',
        'Manual': '✋ Manual'
    };
    
    const statusColor = {
        'Connected': '#2ecc71',
        'Connecting': '#f39c12',
        'Disconnected': '#e74c3c',
        'Error': '#e74c3c',
        'No device found': '#e67e22',
        'Manual': '#f5b87a'
    };
    
    statusDiv.textContent = statusText[status] || status;
    statusDiv.style.color = statusColor[status] || '#95a5a6';
}

document.addEventListener('DOMContentLoaded', () => {
    try {
        createTracker();
        // If swordless mode, replace sword slot image with swordno.png
        var p = new URLSearchParams(window.location.search);
        var _swordless = p.get('swordless') || localStorage.getItem('alttp-swordless') || 'no';
        if (_swordless === 'yes') {
            var swordSlot = document.querySelector('[data-item-key="sword"]');
            if (swordSlot) {
                var swordImg = swordSlot.querySelector('img');
                if (swordImg) swordImg.src = swordImg.src.replace(/sword\d\.png/, 'swordno.png');
                // Also update the items definition so cycling keeps swordno as state 0
                if (items['sword'] && items['sword'].states) {
                    items['sword'].states[0].img = items['sword'].states[0].img.replace(/sword\d\.png/, 'swordno.png');
                }
            }
        }
        // WebSocket is managed by tracker.js / itemtracker.html
    } catch (error) {
        console.error('Error initializing tracker:', error);
    }
});
