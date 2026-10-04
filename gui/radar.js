/*
 =====================================================================================
  Wi-Fi CSI RF Sensing Station - Advanced Detection Dashboard Engine (v2.6)
  Dynamic Theme Engine (Pure White / Tactical Dark / Nordic Slate)
 =====================================================================================
*/

// Application State
let serialPort = null;
let serialReader = null;
let serialWriter = null;
let isConnected = false;
let isDemoMode = false;
let isAudioEnabled = true;

// Active Theme State
let currentTheme = localStorage.getItem('radar_theme') || 'pure-white';

// Telemetry State
let currentMotion = 0.0;
let currentThreshold = 12.0;
let currentBaseline = 3.5;
let currentAlert = 0;
let isBeaconOnline = false;
let beaconRssi = -70;
let beaconRate = 0;
let beaconMac = "--:--:--:--:--:--";
let subcarrierVar = 0.0;

// Subcarrier Model (52 active 802.11n subcarriers)
const SUBCARRIER_COUNT = 52;
let subcarrierDeltas = new Array(SUBCARRIER_COUNT).fill(0);

// Oscilloscope History Buffer
const OSC_CAPACITY = 160;
let motionHistory = new Array(OSC_CAPACITY).fill(0);
let thresholdHistory = new Array(OSC_CAPACITY).fill(12);
let baselineHistory = new Array(OSC_CAPACITY).fill(3.5);

// DOM Elements
const themeSelector = document.getElementById('theme-selector');
const btnConnect = document.getElementById('btn-connect');
const btnConnectLabel = document.getElementById('btn-connect-label');
const btnCalibrate = document.getElementById('btn-calibrate');
const btnAudio = document.getElementById('btn-audio');
const audioIcon = document.getElementById('audio-icon');
const btnFullscreen = document.getElementById('btn-fullscreen');
const fullscreenIcon = document.getElementById('fullscreen-icon');
const btnClearLogs = document.getElementById('btn-clear-logs');

const beaconPill = document.getElementById('beacon-pill');
const beaconStatusText = document.getElementById('beacon-status-text');
const beaconStatsText = document.getElementById('beacon-stats-text');

const mainStatusBanner = document.getElementById('main-status-banner');
const mainStatusIcon = document.getElementById('main-status-icon');
const mainStatusHeadline = document.getElementById('main-status-headline');
const mainStatusSub = document.getElementById('main-status-sub');
const bannerMotionVal = document.getElementById('banner-motion-val');
const bannerThresholdVal = document.getElementById('banner-threshold-val');

const kpiMotionScore = document.getElementById('kpi-motion-score');
const kpiMotionBar = document.getElementById('kpi-motion-bar');
const kpiMotionTrend = document.getElementById('kpi-motion-trend');
const kpiThreshold = document.getElementById('kpi-threshold');
const kpiThresholdBar = document.getElementById('kpi-threshold-bar');
const kpiThreshModeText = document.getElementById('kpi-thresh-mode-text');
const kpiRssi = document.getElementById('kpi-rssi');
const kpiRssiBar = document.getElementById('kpi-rssi-bar');
const kpiRssiQuality = document.getElementById('kpi-rssi-quality');
const kpiRate = document.getElementById('kpi-rate');
const kpiRateBar = document.getElementById('kpi-rate-bar');
const kpiBaselineText = document.getElementById('kpi-baseline-text');

const calBanner = document.getElementById('cal-banner');
const calProgressBar = document.getElementById('cal-progress-bar');
const calCountdown = document.getElementById('cal-countdown');

// Precision Tuning Sliders
const sliderSens = document.getElementById('slider-sens');
const valSens = document.getElementById('val-sens');
const sliderOffset = document.getElementById('slider-offset');
const valOffset = document.getElementById('val-offset');
const sliderGain = document.getElementById('slider-gain');
const valGain = document.getElementById('val-gain');
const sliderManualThresh = document.getElementById('slider-manual-thresh');
const valManualThresh = document.getElementById('val-manual-thresh');
const sliderTrigger = document.getElementById('slider-trigger');
const valTrigger = document.getElementById('val-trigger');
const sliderHold = document.getElementById('slider-hold');
const valHold = document.getElementById('val-hold');

// Presets
const presetMicro = document.getElementById('preset-micro');
const presetBalanced = document.getElementById('preset-balanced');
const presetWalking = document.getElementById('preset-walking');
const presetPet = document.getElementById('preset-pet');
const presetButtons = [presetMicro, presetBalanced, presetWalking, presetPet];

const logTbody = document.getElementById('log-tbody');
const footerDot = document.getElementById('footer-dot');
const footerText = document.getElementById('footer-text');

// Canvases
const spectrogramCanvas = document.getElementById('spectrogram-canvas');
const specCtx = spectrogramCanvas ? spectrogramCanvas.getContext('2d') : null;
const waveformCanvas = document.getElementById('waveform-canvas');
const waveCtx = waveformCanvas ? waveformCanvas.getContext('2d') : null;
const spectrumCanvas = document.getElementById('spectrum-canvas');
const barCtx = spectrumCanvas ? spectrumCanvas.getContext('2d') : null;

// ---------------------------------------------------------------------------
// Dynamic Multi-Theme Canvas Palettes Engine
// ---------------------------------------------------------------------------
const THEME_PALETTES = {
  'pure-white': {
    isLight: true,
    canvasBg: '#ffffff',
    gridColor: '#e4e4e7',
    waveNormal: '#2563eb',
    waveAlert: '#dc2626',
    threshColor: '#d97706',
    baselineColor: 'rgba(220, 38, 38, 0.45)',
    glow: false,
    colorMap: (norm) => {
      if (norm < 0.22) {
        const t = norm / 0.22;
        return [Math.round(230 + 15 * t), Math.round(242 + 5 * t), Math.round(254 - 10 * t)];
      } else if (norm < 0.60) {
        const t = (norm - 0.22) / 0.38;
        return [Math.round(2 + 243 * t), Math.round(132 + 26 * t), Math.round(199 - 188 * t)];
      } else {
        const t = (norm - 0.60) / 0.40;
        return [Math.round(245 - 25 * t), Math.round(158 - 120 * t), Math.round(11 + 27 * t)];
      }
    }
  },
  'nordic-slate': {
    isLight: true,
    canvasBg: '#f8fafc',
    gridColor: '#c5d5e8',
    waveNormal: '#1d4ed8',
    waveAlert: '#dc2626',
    threshColor: '#b45309',
    baselineColor: 'rgba(220, 38, 38, 0.45)',
    glow: false,
    colorMap: (norm) => {
      if (norm < 0.25) {
        const t = norm / 0.25;
        return [Math.round(226 + 15 * t), Math.round(232 + 10 * t), Math.round(240 + 10 * t)];
      } else if (norm < 0.65) {
        const t = (norm - 0.25) / 0.40;
        return [Math.round(37 + 180 * t), Math.round(99 + 20 * t), Math.round(235 - 224 * t)];
      } else {
        const t = (norm - 0.65) / 0.35;
        return [Math.round(217 + 3 * t), Math.round(119 - 81 * t), Math.round(6 + 32 * t)];
      }
    }
  },
  'swiss-clean': {
    isLight: true,
    canvasBg: '#ffffff',
    gridColor: '#cbd5e1',
    waveNormal: '#0284c7',
    waveAlert: '#dc2626',
    threshColor: '#ca8a04',
    baselineColor: 'rgba(220, 38, 38, 0.45)',
    glow: false,
    colorMap: (norm) => {
      if (norm < 0.25) {
        const t = norm / 0.25;
        return [Math.round(240 - 20 * t), Math.round(245 - 15 * t), Math.round(250 - 5 * t)];
      } else if (norm < 0.65) {
        const t = (norm - 0.25) / 0.40;
        return [Math.round(2 + 200 * t), Math.round(132 + 20 * t), Math.round(199 - 180 * t)];
      } else {
        const t = (norm - 0.65) / 0.35;
        return [Math.round(220), Math.round(38), Math.round(38)];
      }
    }
  },
  'dark': {
    isLight: false,
    canvasBg: '#0f0f0f',
    gridColor: 'rgba(255, 255, 255, 0.05)',
    waveNormal: '#60a5fa',
    waveAlert: '#f87171',
    threshColor: '#fbbf24',
    baselineColor: 'rgba(248, 113, 113, 0.45)',
    glow: true,
    colorMap: (norm) => {
      if (norm < 0.25) {
        const t = norm / 0.25;
        return [Math.round(15 + 40 * t), Math.round(15 + 80 * t), Math.round(15 + 160 * t)];
      } else if (norm < 0.65) {
        const t = (norm - 0.25) / 0.40;
        return [Math.round(55 + 195 * t), Math.round(95 + 96 * t), Math.round(175 - 139 * t)];
      } else {
        const t = (norm - 0.65) / 0.35;
        return [Math.round(248), Math.round(113 - 40 * t), Math.round(113 - 40 * t)];
      }
    }
  },
  'cyber-emerald': {
    isLight: false,
    canvasBg: '#050b14',
    gridColor: 'rgba(56, 189, 248, 0.08)',
    waveNormal: '#38bdf8',
    waveAlert: '#f43f5e',
    threshColor: '#fbbf24',
    baselineColor: 'rgba(244, 63, 94, 0.45)',
    glow: true,
    colorMap: (norm) => {
      if (norm < 0.25) {
        const t = norm / 0.25;
        return [Math.round(5 + 20 * t), Math.round(11 + 60 * t), Math.round(20 + 160 * t)];
      } else if (norm < 0.65) {
        const t = (norm - 0.25) / 0.40;
        return [Math.round(25 + 31 * t), Math.round(71 + 118 * t), Math.round(180 + 68 * t)];
      } else {
        const t = (norm - 0.65) / 0.35;
        return [Math.round(56 + 188 * t), Math.round(189 - 126 * t), Math.round(248 - 154 * t)];
      }
    }
  },
  'deep-space': {
    isLight: true,
    canvasBg: '#f4fbf6',
    gridColor: '#c5ddc9',
    waveNormal: '#16a34a',
    waveAlert: '#dc2626',
    threshColor: '#ca8a04',
    baselineColor: 'rgba(220, 38, 38, 0.45)',
    glow: false,
    colorMap: (norm) => {
      if (norm < 0.25) {
        const t = norm / 0.25;
        return [Math.round(230 + 10 * t), Math.round(245 + 5 * t), Math.round(235 - 5 * t)];
      } else if (norm < 0.65) {
        const t = (norm - 0.25) / 0.40;
        return [Math.round(240 - 218 * t), Math.round(250 - 87 * t), Math.round(230 - 156 * t)];
      } else {
        const t = (norm - 0.65) / 0.35;
        return [Math.round(22 + 198 * t), Math.round(163 - 125 * t), Math.round(74 - 36 * t)];
      }
    }
  },
  'solar-amber': {
    isLight: true,
    canvasBg: '#fdf6ec',
    gridColor: '#ddd0b8',
    waveNormal: '#d97706',
    waveAlert: '#dc2626',
    threshColor: '#92400e',
    baselineColor: 'rgba(220, 38, 38, 0.45)',
    glow: false,
    colorMap: (norm) => {
      if (norm < 0.25) {
        const t = norm / 0.25;
        return [Math.round(250), Math.round(245 - 20 * t), Math.round(230 - 30 * t)];
      } else if (norm < 0.65) {
        const t = (norm - 0.25) / 0.40;
        return [Math.round(250 - 33 * t), Math.round(225 - 106 * t), Math.round(200 - 194 * t)];
      } else {
        const t = (norm - 0.65) / 0.35;
        return [Math.round(217 + 3 * t), Math.round(119 - 81 * t), Math.round(6 + 32 * t)];
      }
    }
  },
  'cyberpunk': {
    isLight: false,
    canvasBg: '#060210',
    gridColor: 'rgba(168, 85, 247, 0.09)',
    waveNormal: '#22d3ee',
    waveAlert: '#fb7185',
    threshColor: '#c084fc',
    baselineColor: 'rgba(251, 113, 133, 0.45)',
    glow: true,
    colorMap: (norm) => {
      if (norm < 0.25) {
        const t = norm / 0.25;
        return [Math.round(6 + 28 * t), Math.round(2 + 16 * t), Math.round(16 + 80 * t)];
      } else if (norm < 0.65) {
        const t = (norm - 0.25) / 0.40;
        return [Math.round(34 + 158 * t), Math.round(18 + 114 * t), Math.round(96 + 156 * t)];
      } else {
        const t = (norm - 0.65) / 0.35;
        return [Math.round(192 + 59 * t), Math.round(132 - 19 * t), Math.round(252 - 119 * t)];
      }
    }
  }
};

function getThemePalette() {
  return THEME_PALETTES['pure-white'];
}

document.body.setAttribute('data-theme', 'pure-white');

// ---------------------------------------------------------------------------
// Audio Synthesizer
// ---------------------------------------------------------------------------
let audioCtx = null;
let lastPingTime = 0;

function initAudio() {
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) audioCtx = new AudioContextClass();
  }
}

function playAlarmSound(isAlert = false) {
  if (!isAudioEnabled || !audioCtx) return;
  const now = Date.now();
  if (now - lastPingTime < 500) return;
  lastPingTime = now;

  try {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = isAlert ? 'sawtooth' : 'sine';
    const freq = isAlert ? 880 : 520;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(freq * 1.4, audioCtx.currentTime + 0.12);

    gain.gain.setValueAtTime(0.18, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.35);

    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.4);
  } catch (e) {}
}

// ---------------------------------------------------------------------------
// Event Logging
// ---------------------------------------------------------------------------
function addLogEntry(type, title, details) {
  const d = new Date();
  const timeStr = d.toTimeString().split(' ')[0];

  const row = document.createElement('tr');
  let badgeClass = 'info';
  if (type === 'ALERT') badgeClass = 'alert';
  else if (type === 'CAL') badgeClass = 'cal';

  row.innerHTML = `
    <td>${timeStr}</td>
    <td><span class="badge ${badgeClass}">${title}</span></td>
    <td>${currentMotion.toFixed(2)}</td>
    <td>${currentThreshold.toFixed(2)}</td>
    <td>${isBeaconOnline ? `${beaconRssi} dBm` : 'OFFLINE'}</td>
    <td>${details}</td>
  `;

  if (logTbody) {
    logTbody.insertBefore(row, logTbody.firstChild);
    while (logTbody.children.length > 50) {
      logTbody.removeChild(logTbody.lastChild);
    }
  }
}

// ---------------------------------------------------------------------------
// Serial Port Communications (Web Serial API)
// ---------------------------------------------------------------------------
async function sendCommand(cmd) {
  if (!isConnected || !serialWriter) return;
  try {
    const encoder = new TextEncoder();
    await serialWriter.write(encoder.encode(cmd + '\n'));
    console.log(`[TX]: ${cmd}`);
  } catch (e) {
    console.warn("Serial TX error:", e);
  }
}

// Presets
function applyPreset(sens, offset, gain, manualThresh, trigger, hold, activeBtn) {
  presetButtons.forEach(b => b && b.classList.remove('active'));
  if (activeBtn) activeBtn.classList.add('active');

  if (sliderSens) {
    sliderSens.value = sens;
    valSens.textContent = `${sens.toFixed(1)}x`;
  }
  sendCommand(`CMD:SENS:${sens.toFixed(1)}`);

  if (sliderOffset) {
    sliderOffset.value = offset;
    valOffset.textContent = `${offset.toFixed(1)}`;
  }
  sendCommand(`CMD:OFFSET:${offset.toFixed(1)}`);

  if (sliderGain) {
    sliderGain.value = gain;
    valGain.textContent = `${gain.toFixed(1)}x`;
  }
  sendCommand(`CMD:GAIN:${gain.toFixed(1)}`);

  if (sliderManualThresh) {
    sliderManualThresh.value = manualThresh;
    valManualThresh.textContent = (manualThresh === 0) ? 'AUTO' : manualThresh;
  }
  sendCommand(`CMD:MANUAL_THRESH:${manualThresh}`);

  if (sliderTrigger) {
    sliderTrigger.value = trigger;
    valTrigger.textContent = `${trigger} frames`;
  }
  sendCommand(`CMD:TRIGGER:${trigger}`);

  if (sliderHold) {
    sliderHold.value = hold;
    valHold.textContent = `${hold} ms`;
  }
  sendCommand(`CMD:HOLD:${hold}`);

  addLogEntry('INFO', 'PRESET', `Applied ${activeBtn ? activeBtn.textContent.trim() : 'Custom'}: Sens=${sens}x Offset=${offset} Gain=${gain}x`);
}

if (presetMicro) presetMicro.addEventListener('click', () => applyPreset(1.2, 1.5, 1.8, 0, 1, 1500, presetMicro));
if (presetBalanced) presetBalanced.addEventListener('click', () => applyPreset(2.2, 4.5, 1.0, 0, 2, 1500, presetBalanced));
if (presetWalking) presetWalking.addEventListener('click', () => applyPreset(3.5, 10.0, 1.0, 0, 3, 2000, presetWalking));
if (presetPet) presetPet.addEventListener('click', () => applyPreset(5.0, 18.0, 0.8, 0, 4, 3000, presetPet));

// Sliders Listeners
if (sliderSens) {
  sliderSens.addEventListener('input', (e) => {
    presetButtons.forEach(b => b && b.classList.remove('active'));
    valSens.textContent = `${parseFloat(e.target.value).toFixed(1)}x`;
    sendCommand(`CMD:SENS:${parseFloat(e.target.value).toFixed(1)}`);
  });
}

if (sliderOffset) {
  sliderOffset.addEventListener('input', (e) => {
    presetButtons.forEach(b => b && b.classList.remove('active'));
    valOffset.textContent = `${parseFloat(e.target.value).toFixed(1)}`;
    sendCommand(`CMD:OFFSET:${parseFloat(e.target.value).toFixed(1)}`);
  });
}

if (sliderGain) {
  sliderGain.addEventListener('input', (e) => {
    presetButtons.forEach(b => b && b.classList.remove('active'));
    valGain.textContent = `${parseFloat(e.target.value).toFixed(1)}x`;
    sendCommand(`CMD:GAIN:${parseFloat(e.target.value).toFixed(1)}`);
  });
}

if (sliderManualThresh) {
  sliderManualThresh.addEventListener('input', (e) => {
    presetButtons.forEach(b => b && b.classList.remove('active'));
    const v = parseInt(e.target.value);
    valManualThresh.textContent = (v === 0) ? 'AUTO' : v;
    sendCommand(`CMD:MANUAL_THRESH:${v}`);
  });
}

if (sliderTrigger) {
  sliderTrigger.addEventListener('input', (e) => {
    valTrigger.textContent = `${e.target.value} frames`;
    sendCommand(`CMD:TRIGGER:${e.target.value}`);
  });
}

if (sliderHold) {
  sliderHold.addEventListener('input', (e) => {
    valHold.textContent = `${e.target.value} ms`;
    sendCommand(`CMD:HOLD:${e.target.value}`);
  });
}

// ---------------------------------------------------------------------------
// Telemetry Parsing
// ---------------------------------------------------------------------------
function parseTelemetry(line) {
  if (!line || !line.trim()) return;

  if (line.includes('[CAL_START]')) {
    startCalibrationUI();
    addLogEntry('CAL', 'CALIBRATING', 'ESP32 started ambient RF baseline sampling.');
    return;
  }
  if (line.includes('[CAL_COMPLETE]')) {
    finishCalibrationUI();
    const parts = line.split(':');
    const newBase = parts.length > 1 ? parts[1].trim() : '';
    addLogEntry('CAL', 'CALIBRATED', `Baseline established at ${newBase}`);
    return;
  }

  const parts = line.split(/\s+/);
  parts.forEach(p => {
    const [k, v] = p.split(':');
    if (k === 'Motion_Score') currentMotion = parseFloat(v);
    else if (k === 'Threshold') currentThreshold = parseFloat(v);
    else if (k === 'Alert') currentAlert = parseInt(v);
    else if (k === 'Baseline') currentBaseline = parseFloat(v);
    else if (k === 'Beacon_Status') isBeaconOnline = (parseInt(v) === 1);
    else if (k === 'Beacon_RSSI') beaconRssi = parseInt(v);
    else if (k === 'Beacon_Rate') beaconRate = parseInt(v);
    else if (k === 'Beacon_MAC') {
      const idx = line.indexOf('Beacon_MAC:');
      if (idx !== -1) {
        beaconMac = line.substring(idx + 11).split(' ')[0];
      }
    }
    else if (k === 'SubVar') subcarrierVar = parseFloat(v);
  });

  updateUI();
}

let prevAlertState = 0;

function updateUI() {
  if (beaconPill) {
    if (isBeaconOnline) {
      beaconPill.className = 'beacon-pill online';
      beaconStatusText.textContent = 'ESP8266 BEACON: ONLINE';
      beaconStatsText.textContent = `${beaconRssi} dBm · ${beaconRate} PPS · ${beaconMac}`;
    } else {
      beaconPill.className = 'beacon-pill offline';
      beaconStatusText.textContent = 'ESP8266 BEACON: OFFLINE';
      beaconStatsText.textContent = 'No RF pulses received. Check power!';
    }
  }

  if (bannerMotionVal) bannerMotionVal.textContent = currentMotion.toFixed(1);
  if (bannerThresholdVal) bannerThresholdVal.textContent = currentThreshold.toFixed(1);

  if (mainStatusBanner) {
    if (!isBeaconOnline) {
      mainStatusBanner.className = 'status-strip warning';
      if (mainStatusIcon) mainStatusIcon.textContent = '⚠️';
      if (mainStatusHeadline) mainStatusHeadline.textContent = 'BEACON TRANSMITTER OFFLINE';
      if (mainStatusSub) mainStatusSub.textContent = 'ESP32 waiting for 2.4 GHz pulses. Ensure ESP8266 in Corner 1 is powered.';
    } else if (currentAlert > 0) {
      mainStatusBanner.className = 'status-strip intrusion';
      if (mainStatusIcon) mainStatusIcon.textContent = '🚨';
      if (mainStatusHeadline) mainStatusHeadline.textContent = 'INTRUSION DETECTED — FRESNEL ZONE VIOLATION';
      if (mainStatusSub) mainStatusSub.textContent = `RF perturbation (${currentMotion.toFixed(1)}) breached threshold (${currentThreshold.toFixed(1)}). Active movement detected!`;

      if (prevAlertState === 0) {
        addLogEntry('ALERT', 'INTRUSION', `Movement triggered alert. Score: ${currentMotion.toFixed(1)} (Threshold: ${currentThreshold.toFixed(1)})`);
        playAlarmSound(true);
      }
    } else if (currentMotion > currentBaseline * 1.3) {
      mainStatusBanner.className = 'status-strip warning';
      if (mainStatusIcon) mainStatusIcon.textContent = '🚶';
      if (mainStatusHeadline) mainStatusHeadline.textContent = 'MICRO-MOVEMENT / PRESENCE DETECTED';
      if (mainStatusSub) mainStatusSub.textContent = 'Subtle Doppler shifts detected. Target presence or micro-motion below alert limit.';
    } else {
      mainStatusBanner.className = 'status-strip secure';
      if (mainStatusIcon) mainStatusIcon.textContent = '🛡️';
      if (mainStatusHeadline) mainStatusHeadline.textContent = 'ROOM SECURE — ZERO ANOMALIES';
      if (mainStatusSub) mainStatusSub.textContent = `RF multipath reflections stationary. Baseline noise floor: ${currentBaseline.toFixed(2)}`;
    }
  }
  prevAlertState = currentAlert;

  if (kpiMotionScore) kpiMotionScore.textContent = currentMotion.toFixed(2);
  const maxScale = Math.max(40.0, currentThreshold * 1.8);
  const motionPct = Math.min(100, (currentMotion / maxScale) * 100);
  if (kpiMotionBar) {
    kpiMotionBar.style.width = `${motionPct}%`;
    kpiMotionBar.style.backgroundColor = (currentAlert > 0) ? 'var(--c-red)' : 'var(--c-blue)';
  }
  if (kpiMotionTrend) kpiMotionTrend.textContent = (currentAlert > 0) ? '⚠️ Intruding Target' : 'Normal Fluctuations';

  if (kpiThreshold) kpiThreshold.textContent = currentThreshold.toFixed(2);
  const threshPct = Math.min(100, (currentThreshold / maxScale) * 100);
  if (kpiThresholdBar) kpiThresholdBar.style.width = `${threshPct}%`;
  if (kpiThreshModeText) {
    kpiThreshModeText.textContent = (sliderManualThresh && parseInt(sliderManualThresh.value) > 0) ? `Manual Override (${sliderManualThresh.value})` : 'Mode: Auto-Adaptive';
  }

  if (kpiRssi) kpiRssi.textContent = `${beaconRssi}`;
  const rssiPct = Math.min(100, Math.max(0, ((beaconRssi + 95) / 55) * 100));
  if (kpiRssiBar) {
    kpiRssiBar.style.width = `${rssiPct}%`;
    kpiRssiBar.style.backgroundColor = (beaconRssi > -68) ? 'var(--c-green)' : (beaconRssi > -82) ? 'var(--c-amber)' : 'var(--c-red)';
  }
  if (kpiRssiQuality) {
    if (beaconRssi > -65) kpiRssiQuality.textContent = 'Signal: Excellent (Strong LoS)';
    else if (beaconRssi > -80) kpiRssiQuality.textContent = 'Signal: Good (Corner Coverage)';
    else kpiRssiQuality.textContent = 'Signal: Weak / Attenuated';
  }

  if (kpiRate) kpiRate.textContent = `${beaconRate} PPS`;
  if (kpiRateBar) {
    const ratePct = Math.min(100, Math.max(0, (beaconRate / 45) * 100));
    kpiRateBar.style.width = `${ratePct}%`;
  }
  if (kpiBaselineText) kpiBaselineText.textContent = `Baseline Noise: ${currentBaseline.toFixed(2)}`;

  motionHistory.push(currentMotion);
  motionHistory.shift();
  thresholdHistory.push(currentThreshold);
  thresholdHistory.shift();
  baselineHistory.push(currentBaseline);
  baselineHistory.shift();

  const baseNoise = currentBaseline * 0.15;
  for (let i = 0; i < SUBCARRIER_COUNT; i++) {
    const freqFactor = Math.sin((i / SUBCARRIER_COUNT) * Math.PI);
    const subDelta = (currentMotion * (0.4 + 0.6 * freqFactor) * (0.8 + Math.random() * 0.4)) + (Math.random() * baseNoise);
    subcarrierDeltas[i] = subDelta;
  }

  addSpectrogramSlice(subcarrierDeltas);
}

// ---------------------------------------------------------------------------
// Dynamic Spectrogram Colormap & Slicing
// ---------------------------------------------------------------------------

function colorMap(val, maxVal = 20.0) {
  const norm = Math.min(1.0, Math.max(0.0, val / maxVal));
  const pal = getThemePalette();
  return pal.colorMap(norm);
}

function addSpectrogramSlice(deltas) {
  if (!specCtx || !spectrogramCanvas) return;
  const w = spectrogramCanvas.width;
  const h = spectrogramCanvas.height;
  specCtx.drawImage(spectrogramCanvas, 0, 0, w, h - 2, 0, 2, w, h - 2);

  const colWidth = w / SUBCARRIER_COUNT;
  for (let i = 0; i < SUBCARRIER_COUNT; i++) {
    const [r, g, b] = colorMap(deltas[i], Math.max(16.0, currentThreshold * 1.1));
    specCtx.fillStyle = `rgb(${r}, ${g}, ${b})`;
    specCtx.fillRect(i * colWidth, 0, colWidth + 0.5, 2);
  }
}

// ---------------------------------------------------------------------------
// Equalizer Spectrum (Theme-Adaptive)
// ---------------------------------------------------------------------------
function drawSpectrumBars() {
  if (!barCtx || !spectrumCanvas) return;
  const w = spectrumCanvas.width;
  const h = spectrumCanvas.height;
  const pal = getThemePalette();

  barCtx.fillStyle = pal.canvasBg;
  barCtx.fillRect(0, 0, w, h);

  const barWidth = (w / SUBCARRIER_COUNT) - 2;
  const maxVal = Math.max(25.0, currentThreshold * 1.3);

  for (let i = 0; i < SUBCARRIER_COUNT; i++) {
    const val = subcarrierDeltas[i] || 0;
    const barHeight = Math.min(h - 10, (val / maxVal) * (h - 15));
    const x = i * (barWidth + 2);
    const y = h - barHeight - 4;

    const [r, g, b] = colorMap(val, maxVal);
    barCtx.fillStyle = `rgb(${r}, ${g}, ${b})`;
    barCtx.fillRect(x, y, barWidth, barHeight);
  }
}

// ---------------------------------------------------------------------------
// Oscilloscope Waveform (Adaptive Theme)
// ---------------------------------------------------------------------------
function drawOscilloscope() {
  if (!waveCtx || !waveformCanvas) return;
  const w = waveformCanvas.width;
  const h = waveformCanvas.height;
  const pal = getThemePalette();

  waveCtx.fillStyle = pal.canvasBg;
  waveCtx.fillRect(0, 0, w, h);

  // Grid Lines
  waveCtx.strokeStyle = pal.gridColor;
  waveCtx.lineWidth = 1;
  for (let i = 1; i <= 3; i++) {
    const y = (h / 4) * i;
    waveCtx.beginPath();
    waveCtx.moveTo(0, y);
    waveCtx.lineTo(w, y);
    waveCtx.stroke();
  }

  const maxVal = Math.max(35.0, currentThreshold * 2.0);
  const mapY = (val) => h - (Math.min(maxVal, Math.max(0, val)) / maxVal) * (h - 30) - 15;
  const stepX = w / (OSC_CAPACITY - 1);

  // Noise floor line
  waveCtx.strokeStyle = pal.baselineColor;
  waveCtx.lineWidth = 1.5;
  waveCtx.setLineDash([4, 4]);
  waveCtx.beginPath();
  for (let i = 0; i < OSC_CAPACITY; i++) {
    const x = i * stepX;
    const y = mapY(baselineHistory[i]);
    if (i === 0) waveCtx.moveTo(x, y);
    else waveCtx.lineTo(x, y);
  }
  waveCtx.stroke();
  waveCtx.setLineDash([]);

  // Threshold line
  waveCtx.strokeStyle = pal.threshColor;
  waveCtx.lineWidth = 2;
  waveCtx.setLineDash([6, 3]);
  waveCtx.beginPath();
  for (let i = 0; i < OSC_CAPACITY; i++) {
    const x = i * stepX;
    const y = mapY(thresholdHistory[i]);
    if (i === 0) waveCtx.moveTo(x, y);
    else waveCtx.lineTo(x, y);
  }
  waveCtx.stroke();
  waveCtx.setLineDash([]);

  // Motion Score Curve
  waveCtx.save();
  const alertColor = pal.waveAlert;
  const normalColor = pal.waveNormal;
  waveCtx.strokeStyle = (currentAlert > 0) ? alertColor : normalColor;
  waveCtx.lineWidth = 2.4;
  if (pal.glow) {
    waveCtx.shadowColor = waveCtx.strokeStyle;
    waveCtx.shadowBlur = 8;
  }
  waveCtx.beginPath();
  for (let i = 0; i < OSC_CAPACITY; i++) {
    const x = i * stepX;
    const y = mapY(motionHistory[i]);
    if (i === 0) waveCtx.moveTo(x, y);
    else waveCtx.lineTo(x, y);
  }
  waveCtx.stroke();
  waveCtx.restore();
}

function renderLoop() {
  drawOscilloscope();
  drawSpectrumBars();
  requestAnimationFrame(renderLoop);
}

// ---------------------------------------------------------------------------
// Auto-Calibration Routine
// ---------------------------------------------------------------------------
let calTimer = null;

function startCalibrationUI() {
  if (!calBanner) return;
  calBanner.classList.remove('hidden');
  const duration = 5000;
  const start = Date.now();

  if (calTimer) clearInterval(calTimer);
  calTimer = setInterval(() => {
    const elapsed = Date.now() - start;
    const pct = Math.min(100, (elapsed / duration) * 100);
    const remainSec = Math.max(0, Math.ceil((duration - elapsed) / 1000));

    if (calProgressBar) calProgressBar.style.width = `${pct}%`;
    if (calCountdown) calCountdown.textContent = `${remainSec}s`;

    if (elapsed >= duration) clearInterval(calTimer);
  }, 100);
}

function finishCalibrationUI() {
  if (calTimer) clearInterval(calTimer);
  if (calProgressBar) calProgressBar.style.width = '100%';
  if (calCountdown) calCountdown.textContent = 'DONE';
  setTimeout(() => {
    if (calBanner) calBanner.classList.add('hidden');
    if (calProgressBar) calProgressBar.style.width = '0%';
  }, 1200);
}

// ---------------------------------------------------------------------------
// Serial Port Connection
// ---------------------------------------------------------------------------
async function connectSerial() {
  if (!('serial' in navigator)) {
    alert("Web Serial is supported in Google Chrome, Microsoft Edge, Brave, and Opera.");
    return;
  }
  initAudio();

  try {
    if (isConnected) {
      disconnectSerial();
      return;
    }

    serialPort = await navigator.serial.requestPort();
    await serialPort.open({ baudRate: 115200 });

    isConnected = true;
    isDemoMode = false;

    btnConnectLabel.textContent = "Disconnect";
    btnConnect.classList.add('connected');
    footerDot.className = "footer-dot active";
    footerText.textContent = "SERIAL PORT: CONNECTED (115200 BAUD)";
    addLogEntry('INFO', 'CONNECTED', 'Serial link opened with ESP32 receiver on COM port.');

    serialWriter = serialPort.writable.getWriter();

    const textDecoder = new TextDecoderStream();
    serialPort.readable.pipeTo(textDecoder.writable);
    const reader = textDecoder.readable.getReader();
    serialReader = reader;

    let lineBuffer = '';

    while (isConnected) {
      const { value, done } = await reader.read();
      if (done) break;

      lineBuffer += value;
      const lines = lineBuffer.split('\n');
      lineBuffer = lines.pop();

      for (const line of lines) {
        parseTelemetry(line);
      }
    }
  } catch (err) {
    console.error("Serial error:", err);
    disconnectSerial();
  }
}

async function disconnectSerial() {
  isConnected = false;
  if (serialReader) {
    try { await serialReader.cancel(); } catch (e) {}
    serialReader = null;
  }
  if (serialWriter) {
    try { await serialWriter.close(); } catch (e) {}
    serialWriter = null;
  }
  if (serialPort) {
    try { await serialPort.close(); } catch (e) {}
    serialPort = null;
  }

  btnConnectLabel.textContent = "Connect ESP32";
  btnConnect.classList.remove('connected');
  footerDot.className = "footer-dot";
  footerText.textContent = "SERIAL PORT: NOT CONNECTED";
  isBeaconOnline = false;
  updateUI();
  addLogEntry('INFO', 'DISCONNECTED', 'Serial port connection closed.');
}

if (btnConnect) btnConnect.addEventListener('click', connectSerial);

if (btnCalibrate) {
  btnCalibrate.addEventListener('click', () => {
    startCalibrationUI();
    if (isConnected) {
      sendCommand('CMD:CAL');
      addLogEntry('CAL', 'CALIBRATE', 'Sent baseline calibration request to ESP32.');
    } else {
      setTimeout(finishCalibrationUI, 5000);
      addLogEntry('CAL', 'CALIBRATE', 'Ambient RF noise floor calibrated (offline).');
    }
  });
}

if (btnAudio) {
  btnAudio.addEventListener('click', () => {
    initAudio();
    isAudioEnabled = !isAudioEnabled;
    btnAudio.classList.toggle('active', isAudioEnabled);
    if (audioIcon) audioIcon.textContent = isAudioEnabled ? '🔊' : '🔇';
  });
}

if (btnClearLogs) {
  btnClearLogs.addEventListener('click', () => {
    if (logTbody) logTbody.innerHTML = '';
  });
}

// ---------------------------------------------------------------------------
// Fullscreen Mode Controller
// ---------------------------------------------------------------------------
function isFullscreenActive() {
  return !!(document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement);
}

function updateFullscreenUI() {
  const isFull = isFullscreenActive();
  if (btnFullscreen) {
    btnFullscreen.classList.toggle('active', isFull);
    btnFullscreen.title = isFull ? 'Exit Fullscreen (Esc / F11)' : 'Toggle Fullscreen Mode (F11)';
  }
  if (fullscreenIcon) {
    fullscreenIcon.innerHTML = isFull
      ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/></svg>`
      : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>`;
  }
}

function toggleFullscreen() {
  if (!isFullscreenActive()) {
    const docEl = document.documentElement;
    if (docEl.requestFullscreen) {
      docEl.requestFullscreen().catch(() => {});
    } else if (docEl.webkitRequestFullscreen) {
      docEl.webkitRequestFullscreen();
    } else if (docEl.mozRequestFullScreen) {
      docEl.mozRequestFullScreen();
    } else if (docEl.msRequestFullscreen) {
      docEl.msRequestFullscreen();
    }
    addLogEntry('INFO', 'SCREEN', 'Entered Fullscreen Mode.');
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen().catch(() => {});
    } else if (document.webkitExitFullscreen) {
      document.webkitExitFullscreen();
    } else if (document.mozCancelFullScreen) {
      document.mozCancelFullScreen();
    } else if (document.msExitFullscreen) {
      document.msExitFullscreen();
    }
    addLogEntry('INFO', 'SCREEN', 'Exited Fullscreen Mode.');
  }
}

if (btnFullscreen) {
  btnFullscreen.addEventListener('click', toggleFullscreen);
}

document.addEventListener('fullscreenchange', updateFullscreenUI);
document.addEventListener('webkitfullscreenchange', updateFullscreenUI);
document.addEventListener('mozfullscreenchange', updateFullscreenUI);
document.addEventListener('MSFullscreenChange', updateFullscreenUI);

// ---------------------------------------------------------------------------
// Canvas DPI and Dynamic Width Sizing
// ---------------------------------------------------------------------------
function resizeCanvases() {
  const list = [
    { canvas: spectrogramCanvas },
    { canvas: waveformCanvas },
    { canvas: spectrumCanvas }
  ];

  list.forEach(({ canvas }) => {
    if (!canvas || !canvas.parentElement) return;
    const w = canvas.parentElement.clientWidth;
    if (w > 50 && Math.abs(canvas.width - w) > 4) {
      canvas.width = w;
    }
  });
}

window.addEventListener('resize', resizeCanvases);
window.addEventListener('load', resizeCanvases);
setTimeout(resizeCanvases, 100);

// Start loop
requestAnimationFrame(renderLoop);
