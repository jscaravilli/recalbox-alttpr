/**
 * checklogic.js — overworld check accessibility logic
 *
 * Returns one of: 'green' (available), 'yellow' (possible/dark room),
 *                 'orange' (visible but unreachable), 'red' (unavailable)
 *
 * Item keys match items.js:
 *   bow (0=none,1=bow,2=bow+arrows,3=silver), sword (0-4), gloves (0-2),
 *   boots, hookshot, flippers, moonpearl (pearl), mirror, lamp, hammer,
 *   flute (0=none,1=flute,2=flute+bird), firerod, icerod, somaria, byrna,
 *   cape, book, mushroom, powder, bottle (0-4), shovel, bombos, ether, quake,
 *   agahnim (1=defeated), net, bomb
 *
 * Translated from logic.js (original ALTTP randomizer tracker logic)
 */
'use strict';

(function() {

// ── Region helpers ────────────────────────────────────────────────────────────
function checkLogic(it) {
  // Shorthand booleans matching logic.js helper functions
  var pearl     = it.moonpearl >= 1;
  var glove     = it.gloves >= 1;
  var titan     = it.gloves >= 2;
  var boots     = it.boots >= 1;
  var hookshot  = it.hookshot >= 1;
  var hammer    = it.hammer >= 1;
  var mirror    = it.mirror >= 1;
  var lamp      = it.lamp >= 1;
  var flute     = it.flute >= 1;
  var firerod   = it.firerod >= 1;
  var icerod    = it.icerod >= 1;
  var somaria   = it.somaria >= 1;
  var byrna     = it.byrna >= 1;
  var cape      = it.cape >= 1;
  var book      = it.book >= 1;
  var bombos    = it.bombos >= 1;
  var ether     = it.ether >= 1;
  var quake     = it.quake >= 1;
  var net       = it.net >= 1;
  var powder    = it.powder >= 1;
  var shovel    = it.shovel >= 1;
  var flippers  = it.flippers >= 1;
  var sword1    = it.sword >= 1;
  var sword2    = it.sword >= 2;
  var bow2      = it.bow >= 2;   // bow + arrows (can fight)
  var aga       = it.agahnim >= 1;
  var bottle1   = it.bottle >= 1;
  var mushroom  = it.mushroom >= 1;

  // ── Region access ────────────────────────────────────────────────────────
  var climbDM   = glove || flute;                // can get up Death Mountain
  var eastDM    = climbDM && (hookshot || (mirror && hammer));
  var DMlight   = lamp || flute;                 // Death Mountain without dark
  var fire      = lamp || firerod;               // can light torches
  var cane      = somaria || byrna;

  var dwNW = pearl && (titan || (glove && hammer) || (aga && hookshot && (hammer || glove || flippers)));
  var dwEast = pearl && (aga || (hammer && glove) || (titan && flippers));
  var dwSouth = dwNW || (aga && pearl && hammer);
  var darkEastDM = eastDM && pearl && titan;

  // ── Medallion helper ─────────────────────────────────────────────────────
  // Returns: 'green' = confirmed available, 'yellow' = maybe, 'red' = no
  function medallionColor(dungeonKey) {
    if (!sword1) return 'red';
    var req = (dungeonKey === 'mm') ? it.mmMedallion : it.trMedallion;
    if (req === 0) {
      // Unknown — if we have all three, definitely fine
      if (bombos && ether && quake) return 'green';
      // If we have at least one, maybe
      if (bombos || ether || quake) return 'yellow';
      return 'red';
    }
    if (req === 1 && bombos) return 'green';
    if (req === 2 && ether)  return 'green';
    if (req === 3 && quake)  return 'green';
    return 'red';
  }

  // ── Combine worst of two colors ──────────────────────────────────────────
  var ORDER = { 'red':0, 'orange':1, 'yellow':2, 'green':3 };
  function worst(a, b) { return ORDER[a] < ORDER[b] ? a : b; }

  // ── Per-check logic ──────────────────────────────────────────────────────
  // Returns 'green','yellow','orange','red'
  return {

    // ── Light World ──────────────────────────────────────────────────────

    // 0: King's Tomb
    0: function() {
      if (!boots) return 'red';
      if (titan) return 'green';
      if (dwNW && mirror) return 'green';
      return 'red';
    },

    // 1: Swamp Ruins / Dam
    1: function() { return 'green'; },

    // 2: Link's House
    2: function() { return 'green'; },

    // 3: Spiral Cave
    3: function() {
      if (!climbDM) return 'red';
      return DMlight ? 'green' : 'yellow';
    },

    // 4: Mimic Cave  (lw — requires TR entry items + lamp)
    4: function() {
      if (!pearl || !hammer || !titan || !somaria || !mirror) return 'red';
      var med = medallionColor('tr');
      if (med === 'red') return 'red';
      if (!firerod) return worst(med, 'yellow');
      if (!DMlight) return worst(med, 'yellow');
      return worst(med, 'green');
    },

    // 5: Tavern
    5: function() { return 'green'; },

    // 6: Chicken House
    6: function() { return 'green'; },

    // 7: Brewery
    7: function() { return dwNW ? 'green' : 'red'; },

    // 8: C-Shaped House
    8: function() { return dwNW ? 'green' : 'red'; },

    // 9: Aginah's Cave
    9: function() { return 'green'; },

    // 10: Mire Shed (2)
    10: function() {
      return (pearl && flute && titan) ? 'green' : 'red';
    },

    // 11: Super Bunny Cave (2) / Hookshot Cave area
    11: function() {
      if (!pearl || !titan || !eastDM) return 'red';
      return DMlight ? 'green' : 'yellow';
    },

    // 12: Sahasrahla's Hut (3)
    12: function() { return 'green'; },

    // 13: Spike Cave
    13: function() {
      if (!pearl || !glove || !hammer || (!byrna && !cape)) return 'red';
      return DMlight ? 'green' : 'yellow';
    },

    // 14: Kakariko Well (5)
    14: function() { return 'green'; },

    // 15: Blind's Hut (5)
    15: function() { return 'green'; },

    // 16: Hype Cave (5)
    16: function() { return dwSouth ? 'green' : 'red'; },

    // 17: Paradox Cave (7)
    17: function() {
      if (!eastDM) return 'red';
      return DMlight ? 'green' : 'yellow';
    },

    // 18: Bonk Rock Cave
    18: function() { return boots ? 'green' : 'red'; },

    // 19: Mini Moldorm Cave (5)
    19: function() { return 'green'; },

    // 20: Ice Rod Cave
    20: function() { return 'green'; },

    // 21: Hookshot Cave Bot. R
    21: function() {
      if (!pearl || !titan) return 'red';
      if (hookshot || (mirror && hammer && boots)) return DMlight ? 'green' : 'yellow';
      return 'red';
    },

    // 22: Hookshot Cave (3)
    22: function() {
      if (!pearl || !titan || !hookshot) return 'red';
      return DMlight ? 'green' : 'yellow';
    },

    // 63: Zora's Domain Fairy (always accessible)
    63: function() { return 'green'; },

    // 64: Chest Game
    64: function() { return dwNW ? 'green' : 'red'; },

    // 65: Bottle Merchant
    65: function() { return 'green'; },

    // 66: Sahasrahla NPC
    66: function() {
      // Needs green pendant (from EP, DP, or ToH — tracker knows via crystals/prizes)
      // We approximate: if agahnim alive or has green pendant tracked
      // Use greenPendant from prizes if available
      var gp = (window.trackerItems && window.trackerItems.greenPendant) ? window.trackerItems.greenPendant : 0;
      return gp ? 'green' : 'red';
    },

    // 67: Stumpy
    67: function() { return dwSouth ? 'green' : 'red'; },

    // 68: Sick Kid
    68: function() { return bottle1 ? 'green' : 'red'; },

    // 69: Purple Chest
    69: function() { return (pearl && titan) ? 'green' : 'red'; },

    // 70: Hobo
    70: function() { return flippers ? 'green' : 'red'; },

    // 71: Ether Tablet
    71: function() {
      if (!book || !climbDM) return 'red';
      if (!(mirror || (hookshot && hammer))) return 'red';
      if (!sword2) return 'orange';
      return DMlight ? 'green' : 'yellow';
    },

    // 72: Bombos Tablet
    72: function() {
      if (!book || !mirror || !dwSouth) return 'red';
      if (!sword2) return 'orange';
      return 'green';
    },

    // 73: Catfish
    73: function() { return (dwEast && glove) ? 'green' : 'red'; },

    // 74: King Zora
    74: function() {
      return (flippers || glove) ? 'green' : 'red';
    },

    // 75: Old Man
    75: function() {
      if (!climbDM) return 'red';
      return lamp ? 'green' : 'yellow';
    },

    // 76: Potion Shop
    76: function() { return mushroom ? 'green' : 'red'; },

    // 77: Lost Woods Hideout
    77: function() { return 'green'; },

    // 78: Lumberjack Tree
    78: function() {
      if (!aga || !boots) return 'orange';
      return 'green';
    },

    // 79: Spectacle Rock Cave
    79: function() {
      if (!climbDM) return 'red';
      return DMlight ? 'green' : 'yellow';
    },

    // 80: Cave 45
    80: function() {
      if (!mirror) return 'red';
      if (dwNW || (aga && pearl && hammer)) return 'green';
      return 'red';
    },

    // 81: Graveyard Ledge
    81: function() {
      return (dwNW && mirror) ? 'green' : 'red';
    },

    // 82: Checkerboard Cave
    82: function() {
      return (flute && titan && mirror) ? 'green' : 'red';
    },

    // 83: Hammer Pegs
    83: function() { return (pearl && titan && hammer) ? 'green' : 'red'; },

    // 84: Library
    84: function() {
      return boots ? 'green' : 'orange';
    },

    // 85: Mushroom
    85: function() { return 'green'; },

    // 86: Spectacle Rock
    86: function() {
      if (!climbDM) return 'red';
      if (!mirror) return 'orange';
      return DMlight ? 'green' : 'yellow';
    },

    // 87: Floating Island
    87: function() {
      if (!eastDM) return 'red';
      if (!mirror || !pearl || !titan) return 'orange';
      return DMlight ? 'green' : 'yellow';
    },

    // 88: Race Minigame
    88: function() { return 'green'; },

    // 89: Desert West Ledge
    89: function() {
      if (book) return 'green';
      if (titan && flute && mirror) return 'green';
      return 'orange';
    },

    // 90: Lake Hylia Island
    90: function() {
      if (!flippers) return 'orange';
      if (pearl && mirror && (aga || titan || (glove && hammer))) return 'green';
      return 'orange';
    },

    // 91: Bumper Cave Ledge
    91: function() {
      if (!dwNW) return 'red';
      if (cape && glove) return 'green';
      return 'orange';
    },

    // 92: Pyramid
    92: function() {
      return (aga || dwEast) ? 'green' : 'red';
    },

    // 93: Digging Game
    93: function() { return dwSouth ? 'green' : 'red'; },

    // 94: Zora's Ledge
    94: function() { return flippers ? 'green' : 'red'; },

    // 95: Flute Boy Spot
    95: function() { return shovel ? 'green' : 'red'; },

    // 96: Escape Sewers (3)
    96: function() {
      // Always accessible via front or via gloves; dark room without lamp
      return lamp ? 'green' : 'yellow';
    },

    // 97: Uncle + Passage (2)
    97: function() { return 'green'; },

    // 98: Hyrule Castle (3)
    98: function() { return 'green'; },

    // 99: Sanctuary
    99: function() { return 'green'; },

    // 100: Magic Bat
    100: function() {
      if (!powder) return 'red';
      if (hammer) return 'green';
      if (dwNW && mirror) return 'green';
      return 'red';
    },

    // 101: Blacksmith
    101: function() { return (pearl && titan) ? 'green' : 'red'; },

    // 102: Pyramid Fairy (2)
    102: function() {
      var crystals2 = (window.trackerItems && window.trackerItems.redCrystal >= 2) || false;
      if (!crystals2) return 'red';
      return (aga || dwEast) ? 'green' : 'red';
    },

    // 103: Master Sword Pedestal
    103: function() {
      var pendants = (window.trackerItems && window.trackerItems.pendants) || 0;
      if (pendants >= 3) return 'green';
      return book ? 'orange' : 'red';
    },

    // 104: Dark Cross (Castle Tower)
    104: function() {
      return lamp ? 'green' : 'yellow';
    },

    // 105: Waterfall Fairy (2)
    105: function() { return flippers ? 'green' : 'red'; },

  };
}

// ── Public API ────────────────────────────────────────────────────────────────
window.checkColor = function(id) {
  if (!window.trackerItems) return 'green';
  var it = window.trackerItems;
  var checks = checkLogic(it);
  var fn = checks[id];
  if (!fn) return 'green';
  return fn();
};

})();
