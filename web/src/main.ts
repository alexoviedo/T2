import { SerialConnection } from './serial';
import { BoardProtocol } from './protocol';
import { setupFlasher } from './flasher';
import { RuntimeConfig } from './config-model';
import { flightPackGeneric, flightPackXbox } from './presets';

// Application State
let serial: SerialConnection;
let protocol: BoardProtocol;
let currentConfig: RuntimeConfig | null = null;

// UI Elements
const els = {
  // Navigation
  tabs: document.querySelectorAll('.tab-btn') as NodeListOf<HTMLButtonElement>,
  tabContents: document.querySelectorAll('.tab-content') as NodeListOf<HTMLElement>,

  // Connection
  btnConnect: document.getElementById('btn-connect') as HTMLButtonElement,
  btnDisconnect: document.getElementById('btn-disconnect') as HTMLButtonElement,
  badgeConnection: document.getElementById('connection-badge') as HTMLDivElement,
  cardStatus: document.getElementById('status-card') as HTMLDivElement,
  lblConfigStatus: document.getElementById('lbl-config-status') as HTMLDivElement,

  // Error Banner
  errorBanner: document.getElementById('error-banner') as HTMLDivElement,
  errorMessage: document.getElementById('error-message') as HTMLSpanElement,
  btnDismissError: document.getElementById('dismiss-error') as HTMLButtonElement,

  // Configure
  inpDisplayName: document.getElementById('inp-display-name') as HTMLInputElement,
  selPersona: document.getElementById('sel-persona') as HTMLSelectElement,
  selProfile: document.getElementById('sel-profile') as HTMLSelectElement,
  chkAutoStartPersona: document.getElementById('chk-auto-start-persona') as HTMLInputElement,
  chkAutoStartBridge: document.getElementById('chk-auto-start-bridge') as HTMLInputElement,
  inpRateHz: document.getElementById('inp-rate-hz') as HTMLInputElement,
  txtJsonConfig: document.getElementById('txt-json-config') as HTMLTextAreaElement,

  btnCommitConfig: document.getElementById('btn-commit-config') as HTMLButtonElement,
  btnSaveConfig: document.getElementById('btn-save-config') as HTMLButtonElement,
  btnLoadConfig: document.getElementById('btn-load-config') as HTMLButtonElement,
  btnResetConfig: document.getElementById('btn-reset-config') as HTMLButtonElement,
  btnStartConfigured: document.getElementById('btn-start-configured') as HTMLButtonElement,
  btnImportJson: document.getElementById('btn-import-json') as HTMLButtonElement,

  // Mappings
  mappingsTbody: document.getElementById('mappings-tbody') as HTMLTableSectionElement,
  btnAddMapping: document.getElementById('btn-add-mapping') as HTMLButtonElement,
  btnRefreshCatalog: document.getElementById('btn-refresh-catalog') as HTMLButtonElement,
  preInputCatalog: document.getElementById('pre-input-catalog') as HTMLPreElement,
  btnRefreshSchemas: document.getElementById('btn-refresh-schemas') as HTMLButtonElement,
  preSchemaGeneric: document.getElementById('pre-schema-generic') as HTMLPreElement,
  preSchemaXbox: document.getElementById('pre-schema-xbox') as HTMLPreElement,

  // Presets
  btnPresetGeneric: document.getElementById('btn-preset-generic') as HTMLButtonElement,
  btnPresetXbox: document.getElementById('btn-preset-xbox') as HTMLButtonElement,

  // Logs
  logContainer: document.getElementById('serial-log-container') as HTMLDivElement,
  btnClearLogs: document.getElementById('btn-clear-logs') as HTMLButtonElement,
};

// Initialize
function init() {
  setupTabs();
  setupSerial();
  setupEvents();

  // Initialize Flasher with relative path assuming GitHub pages structure
  const manifestUrl = new URL('./firmware/manifest.json', window.location.href).href;
  setupFlasher('flasher-root', manifestUrl);
}

function setupTabs() {
  els.tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');

      els.tabs.forEach(t => t.classList.remove('active'));
      els.tabContents.forEach(c => c.classList.remove('active'));

      btn.classList.add('active');
      document.getElementById(`tab-${tabId}`)?.classList.add('active');
    });
  });
}

function showError(msg: string) {
  els.errorMessage.textContent = msg;
  els.errorBanner.classList.remove('hidden');
  console.error(msg);
}

els.btnDismissError.addEventListener('click', () => {
  els.errorBanner.classList.add('hidden');
});

function appendLog(dir: 'tx' | 'rx', text: string) {
  const line = document.createElement('div');
  line.className = `log-${dir}`;
  const timestamp = new Date().toISOString().substring(11, 23);
  line.textContent = `[${timestamp}] ${dir.toUpperCase()}: ${text}`;
  els.logContainer.appendChild(line);
  els.logContainer.scrollTop = els.logContainer.scrollHeight;
}

function setupSerial() {
  serial = new SerialConnection(appendLog);
  protocol = new BoardProtocol(serial);
}

function updateConnectionUI(connected: boolean) {
  if (connected) {
    els.btnConnect.classList.add('hidden');
    els.btnDisconnect.classList.remove('hidden');
    els.badgeConnection.textContent = 'Connected';
    els.badgeConnection.className = 'badge connected';
    els.cardStatus.classList.remove('hidden');
  } else {
    els.btnConnect.classList.remove('hidden');
    els.btnDisconnect.classList.add('hidden');
    els.badgeConnection.textContent = 'Disconnected';
    els.badgeConnection.className = 'badge disconnected';
    els.cardStatus.classList.add('hidden');
    els.lblConfigStatus.textContent = '-';
  }
}

async function refreshConfigStatus() {
  if (!serial.isConnected()) return;
  try {
    els.lblConfigStatus.textContent = await protocol.getConfigStatus();
  } catch (e: any) {
    showError(e.message);
  }
}

async function refreshConfig() {
  if (!serial.isConnected()) return;
  try {
    currentConfig = await protocol.getConfigJson();
    renderConfig();
  } catch (e: any) {
    showError(e.message);
  }
}

function renderConfig() {
  if (!currentConfig) {
    els.txtJsonConfig.value = '';
    return;
  }

  els.txtJsonConfig.value = JSON.stringify(currentConfig, null, 2);

  els.inpDisplayName.value = currentConfig.display_name || '';
  els.selPersona.value = currentConfig.selected_persona || 'generic_gamepad';

  // Synchronize Configure Form changes with JSON textarea
  const updateJsonFromForm = () => {
    buildConfigFromUI();
    els.txtJsonConfig.value = JSON.stringify(currentConfig, null, 2);
  };

  els.inpDisplayName.addEventListener('input', updateJsonFromForm);
  els.selPersona.addEventListener('change', updateJsonFromForm);
  els.selProfile.addEventListener('change', updateJsonFromForm);
  els.chkAutoStartPersona.addEventListener('change', updateJsonFromForm);
  els.chkAutoStartBridge.addEventListener('change', updateJsonFromForm);
  els.inpRateHz.addEventListener('input', updateJsonFromForm);

  // Filter options based on persona
  Array.from(els.selProfile.options).forEach(opt => {
    if (opt.value === 'custom_runtime') {
      opt.style.display = 'block';
    } else if (els.selPersona.value === 'generic_gamepad') {
      opt.style.display = (opt.value === 'generic_auto' || opt.value === 'flight_pack_demo') ? 'block' : 'none';
    } else if (els.selPersona.value === 'xbox_wireless_controller') {
      opt.style.display = (opt.value === 'xbox_auto' || opt.value === 'xbox_flight_pack_demo') ? 'block' : 'none';
    }
  });

  // Ensure current selection is valid for persona
  let selected = currentConfig.selected_profile || 'custom_runtime';
  const opt = Array.from(els.selProfile.options).find(o => o.value === selected);
  if (!opt || opt.style.display === 'none') {
    selected = 'custom_runtime';
  }

  els.selProfile.value = selected;
  els.chkAutoStartPersona.checked = currentConfig.bridge?.auto_start_persona ?? true;
  els.chkAutoStartBridge.checked = currentConfig.bridge?.auto_start_bridge ?? false;
  els.inpRateHz.value = (currentConfig.bridge?.rate_hz ?? 50).toString();

  renderMappings();
}

function renderMappings() {
  els.mappingsTbody.innerHTML = '';
  if (!currentConfig || !currentConfig.mappings) return;

  currentConfig.mappings.forEach((rule, idx) => {
    const tr = document.createElement('tr');

    // Vendor ID
    const inpVid = document.createElement('input');
    inpVid.type = 'text';
    inpVid.className = 'map-inp';
    inpVid.setAttribute('data-field', 'source_vendor_id');
    inpVid.setAttribute('data-idx', idx.toString());
    inpVid.value = rule.source_vendor_id != null ? `0x${rule.source_vendor_id.toString(16)}` : '';
    const tdVid = document.createElement('td');
    tdVid.appendChild(inpVid);
    tr.appendChild(tdVid);

    // Product ID
    const inpPid = document.createElement('input');
    inpPid.type = 'text';
    inpPid.className = 'map-inp';
    inpPid.setAttribute('data-field', 'source_product_id');
    inpPid.setAttribute('data-idx', idx.toString());
    inpPid.value = rule.source_product_id != null ? `0x${rule.source_product_id.toString(16)}` : '';
    const tdPid = document.createElement('td');
    tdPid.appendChild(inpPid);
    tr.appendChild(tdPid);

    // Interface ID
    const inpIface = document.createElement('input');
    inpIface.type = 'number';
    inpIface.className = 'map-inp';
    inpIface.setAttribute('data-field', 'source_interface_id');
    inpIface.setAttribute('data-idx', idx.toString());
    inpIface.value = rule.source_interface_id != null ? rule.source_interface_id.toString() : '';
    const tdIface = document.createElement('td');
    tdIface.appendChild(inpIface);
    tr.appendChild(tdIface);

    // Source Control ID
    const inpSrcCtrl = document.createElement('input');
    inpSrcCtrl.type = 'text';
    inpSrcCtrl.className = 'map-inp';
    inpSrcCtrl.setAttribute('data-field', 'source_control_id');
    inpSrcCtrl.setAttribute('data-idx', idx.toString());
    inpSrcCtrl.value = rule.source_control_id;
    const tdSrcCtrl = document.createElement('td');
    tdSrcCtrl.appendChild(inpSrcCtrl);
    tr.appendChild(tdSrcCtrl);

    // Target Control ID
    const inpTgtCtrl = document.createElement('input');
    inpTgtCtrl.type = 'text';
    inpTgtCtrl.className = 'map-inp';
    inpTgtCtrl.setAttribute('data-field', 'target_control_id');
    inpTgtCtrl.setAttribute('data-idx', idx.toString());
    inpTgtCtrl.value = rule.target_control_id;
    const tdTgtCtrl = document.createElement('td');
    tdTgtCtrl.appendChild(inpTgtCtrl);
    tr.appendChild(tdTgtCtrl);

    // Invert
    const inpInv = document.createElement('input');
    inpInv.type = 'checkbox';
    inpInv.className = 'map-inp';
    inpInv.setAttribute('data-field', 'invert');
    inpInv.setAttribute('data-idx', idx.toString());
    inpInv.checked = rule.invert;
    const tdInv = document.createElement('td');
    tdInv.appendChild(inpInv);
    tr.appendChild(tdInv);

    // Deadzone
    const inpDz = document.createElement('input');
    inpDz.type = 'number';
    inpDz.step = 'any';
    inpDz.className = 'map-inp';
    inpDz.setAttribute('data-field', 'deadzone');
    inpDz.setAttribute('data-idx', idx.toString());
    inpDz.value = rule.deadzone?.toString() ?? '';
    const tdDz = document.createElement('td');
    tdDz.appendChild(inpDz);
    tr.appendChild(tdDz);

    // Transform Type
    const inpTrans = document.createElement('select');
    inpTrans.className = 'map-inp';
    inpTrans.setAttribute('data-field', 'transform_type');
    inpTrans.setAttribute('data-idx', idx.toString());

    const optNone = document.createElement('option');
    optNone.value = '';
    optNone.text = 'None';
    inpTrans.appendChild(optNone);

    const optAtt = document.createElement('option');
    optAtt.value = 'axis_to_trigger';
    optAtt.text = 'axis_to_trigger';
    inpTrans.appendChild(optAtt);

    inpTrans.value = rule.transform?.type ?? '';
    const tdTrans = document.createElement('td');
    tdTrans.appendChild(inpTrans);
    tr.appendChild(tdTrans);

    // Remove btn
    const btnRm = document.createElement('button');
    btnRm.className = 'btn-remove-mapping';
    btnRm.setAttribute('data-idx', idx.toString());
    btnRm.textContent = 'Remove';
    const tdRm = document.createElement('td');
    tdRm.appendChild(btnRm);
    tr.appendChild(tdRm);

    els.mappingsTbody.appendChild(tr);
  });

  document.querySelectorAll('.map-inp').forEach(inp => {
    inp.addEventListener('change', (e) => {
      const target = e.target as HTMLInputElement;
      const field = target.getAttribute('data-field')!;
      const idx = parseInt(target.getAttribute('data-idx')!);
      const rule = currentConfig!.mappings[idx];

      if (field === 'source_vendor_id' || field === 'source_product_id') {
        if (!target.value.trim()) {
          (rule as any)[field] = null;
        } else {
          const val = target.value.startsWith('0x') ? parseInt(target.value, 16) : parseInt(target.value, 10);
          (rule as any)[field] = isNaN(val) ? null : val;
        }
      } else if (field === 'source_interface_id') {
        if (!target.value.trim()) {
          rule.source_interface_id = null;
        } else {
          const val = parseInt(target.value, 10);
          rule.source_interface_id = isNaN(val) ? null : val;
        }
      } else if (field === 'invert') {
        rule.invert = target.checked;
      } else if (field === 'deadzone') {
        const parsedDz = parseFloat(target.value);
        rule.deadzone = isNaN(parsedDz) ? null : parsedDz;
      } else if (field === 'transform_type') {
        if (target.value) {
          if (!rule.transform) {
            rule.transform = { type: target.value };
          } else {
            rule.transform.type = target.value;
          }
          if (target.value === 'axis_to_trigger') {
            rule.transform.source_min = rule.transform.source_min ?? -32768;
            rule.transform.source_max = rule.transform.source_max ?? 32767;
            rule.transform.invert = rule.transform.invert ?? false;
          }
        } else {
          rule.transform = null;
        }
      } else {
        (rule as any)[field] = target.value;
      }

      els.txtJsonConfig.value = JSON.stringify(currentConfig, null, 2);
    });
  });

  document.querySelectorAll('.btn-remove-mapping').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const idx = parseInt((e.target as HTMLButtonElement).getAttribute('data-idx')!);
      currentConfig!.mappings.splice(idx, 1);
      renderMappings();
      els.txtJsonConfig.value = JSON.stringify(currentConfig, null, 2);
    });
  });
}

function buildConfigFromUI(): RuntimeConfig | null {
  if (!currentConfig) return null;
  currentConfig.display_name = els.inpDisplayName.value;
  currentConfig.selected_persona = els.selPersona.value as any;
  currentConfig.selected_profile = els.selProfile.value;
  currentConfig.bridge.auto_start_persona = els.chkAutoStartPersona.checked;
  currentConfig.bridge.auto_start_bridge = els.chkAutoStartBridge.checked;

  const parsedRate = parseInt(els.inpRateHz.value, 10);
  if (isNaN(parsedRate) || parsedRate < 1 || parsedRate > 200) {
    currentConfig.bridge.rate_hz = 50;
    els.inpRateHz.value = '50';
  } else {
    currentConfig.bridge.rate_hz = parsedRate;
  }

  return currentConfig;
}

function setupEvents() {
  els.btnConnect.addEventListener('click', async () => {
    try {
      await serial.requestPort();
      await serial.connect();
      updateConnectionUI(true);
      await refreshConfigStatus();
      await refreshConfig();
    } catch (e: any) {
      showError(`Connection failed: ${e.message}`);
      updateConnectionUI(false);
    }
  });

  els.btnDisconnect.addEventListener('click', async () => {
    try {
      await serial.disconnect();
      updateConnectionUI(false);
    } catch (e: any) {
      showError(e.message);
    }
  });

  // Action Buttons
  els.btnCommitConfig.addEventListener('click', async () => {
    const config = buildConfigFromUI();
    if (!config) return;
    try {
      await protocol.importConfig(config);
      await refreshConfigStatus();
      await refreshConfig();
      alert('Config committed to runtime successfully.');
    } catch (e: any) {
      showError(e.message);
    }
  });

  els.btnSaveConfig.addEventListener('click', async () => {
    const config = buildConfigFromUI();
    if (!config) return;
    try {
      await protocol.importConfig(config);
      await protocol.saveConfig();
      await refreshConfigStatus();
      alert('Config saved to NVS successfully.');
    } catch (e: any) {
      showError(e.message);
    }
  });

  els.btnLoadConfig.addEventListener('click', async () => {
    try {
      await protocol.loadConfig();
      await refreshConfigStatus();
      await refreshConfig();
    } catch (e: any) {
      showError(e.message);
    }
  });

  els.btnResetConfig.addEventListener('click', async () => {
    try {
      await protocol.resetConfig();
      await refreshConfigStatus();
      await refreshConfig();
    } catch (e: any) {
      showError(e.message);
    }
  });

  els.btnStartConfigured.addEventListener('click', async () => {
    const config = buildConfigFromUI();
    if (!config) return;
    try {
      await protocol.importConfig(config);
      await protocol.startConfigured();
      alert('Configured persona/bridge started.');
    } catch (e: any) {
      showError(e.message);
    }
  });

  els.btnImportJson.addEventListener('click', () => {
    try {
      const parsed = JSON.parse(els.txtJsonConfig.value);
      if (!parsed || typeof parsed !== 'object') {
        throw new Error('Config must be an object');
      }
      if (!parsed.bridge || typeof parsed.bridge !== 'object') {
        throw new Error('Missing or invalid "bridge" configuration');
      }
      if (!Array.isArray(parsed.mappings)) {
        throw new Error('Missing or invalid "mappings" array');
      }
      currentConfig = parsed;
      renderConfig();
    } catch (e: any) {
      showError(`Invalid JSON: ${e.message}`);
    }
  });

  // Mappings Tab
  els.btnRefreshCatalog.addEventListener('click', async () => {
    try {
      els.preInputCatalog.textContent = await protocol.getInputCatalog();
    } catch (e: any) {
      showError(e.message);
    }
  });

  els.btnRefreshSchemas.addEventListener('click', async () => {
    try {
      els.preSchemaGeneric.textContent = await protocol.getPersonaSchema('generic');
      els.preSchemaXbox.textContent = await protocol.getPersonaSchema('xbox');
    } catch (e: any) {
      showError(e.message);
    }
  });

  els.btnAddMapping.addEventListener('click', () => {
    if (!currentConfig) return;

    // Find an unused target control id to avoid duplicates if possible
    let newTarget = 'x';
    const usedTargets = new Set(currentConfig.mappings.map(m => m.target_control_id));
    const commonTargets = ['x', 'y', 'z', 'rx', 'ry', 'rz', 'button_1', 'button_2', 'button_3', 'button_4', 'hat'];
    for (const t of commonTargets) {
      if (!usedTargets.has(t)) {
        newTarget = t;
        break;
      }
    }

    currentConfig.mappings.push({
      source_vendor_id: null,
      source_product_id: null,
      source_interface_id: null,
      source_control_id: 'axis_01_30',
      target_control_id: newTarget,
      invert: false,
      deadzone: null,
      transform: null
    });
    renderMappings();
    els.txtJsonConfig.value = JSON.stringify(currentConfig, null, 2);
  });

  // Presets
  els.selPersona.addEventListener('change', () => {
    renderConfig();
  });

  // Presets
  els.btnPresetGeneric.addEventListener('click', async () => {
    currentConfig = JSON.parse(JSON.stringify(flightPackGeneric));
    renderConfig();
    try {
      if (currentConfig && serial.isConnected()) {
        await protocol.importConfig(currentConfig);
        await refreshConfigStatus();
        alert('Flight Pack Generic applied to board.');
      }
    } catch (e: any) {
      showError(e.message);
    }
    document.querySelector('[data-tab="configure"]')?.dispatchEvent(new Event('click'));
  });

  els.btnPresetXbox.addEventListener('click', async () => {
    currentConfig = JSON.parse(JSON.stringify(flightPackXbox));
    renderConfig();
    try {
      if (currentConfig && serial.isConnected()) {
        await protocol.importConfig(currentConfig);
        await refreshConfigStatus();
        alert('Flight Pack Xbox applied to board.');
      }
    } catch (e: any) {
      showError(e.message);
    }
    document.querySelector('[data-tab="configure"]')?.dispatchEvent(new Event('click'));
  });

  // Logs
  els.btnClearLogs.addEventListener('click', () => {
    els.logContainer.innerHTML = '';
  });
}

// Start
init();
