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
  const manifestUrl = new URL('/T2/firmware/manifest.json', window.location.href).href;
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
  els.selProfile.value = currentConfig.selected_profile || 'custom_runtime';
  els.chkAutoStartPersona.checked = currentConfig.bridge?.auto_start_persona ?? true;
  els.chkAutoStartBridge.checked = currentConfig.bridge?.auto_start_bridge ?? false;
  els.inpRateHz.value = (currentConfig.bridge?.rate_hz || 50).toString();

  renderMappings();
}

function renderMappings() {
  els.mappingsTbody.innerHTML = '';
  if (!currentConfig || !currentConfig.mappings) return;

  currentConfig.mappings.forEach((rule, idx) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input type="text" class="map-inp" data-field="source_vendor_id" data-idx="${idx}" value="0x${rule.source_vendor_id.toString(16)}"></td>
      <td><input type="text" class="map-inp" data-field="source_product_id" data-idx="${idx}" value="0x${rule.source_product_id.toString(16)}"></td>
      <td><input type="number" class="map-inp" data-field="source_interface_id" data-idx="${idx}" value="${rule.source_interface_id}"></td>
      <td><input type="text" class="map-inp" data-field="source_control_id" data-idx="${idx}" value="${rule.source_control_id}"></td>
      <td><input type="text" class="map-inp" data-field="target_control_id" data-idx="${idx}" value="${rule.target_control_id}"></td>
      <td><input type="checkbox" class="map-inp" data-field="invert" data-idx="${idx}" ${rule.invert ? 'checked' : ''}></td>
      <td><input type="number" class="map-inp" data-field="deadzone" data-idx="${idx}" value="${rule.deadzone ?? ''}"></td>
      <td><input type="text" class="map-inp" data-field="transform_type" data-idx="${idx}" value="${rule.transform?.type ?? ''}"></td>
      <td><button class="btn-remove-mapping" data-idx="${idx}">Remove</button></td>
    `;
    els.mappingsTbody.appendChild(tr);
  });

  document.querySelectorAll('.map-inp').forEach(inp => {
    inp.addEventListener('change', (e) => {
      const target = e.target as HTMLInputElement;
      const field = target.getAttribute('data-field')!;
      const idx = parseInt(target.getAttribute('data-idx')!);
      const rule = currentConfig!.mappings[idx];

      if (field === 'source_vendor_id' || field === 'source_product_id') {
        const val = target.value.startsWith('0x') ? parseInt(target.value, 16) : parseInt(target.value, 10);
        if (!isNaN(val)) (rule as any)[field] = val;
      } else if (field === 'source_interface_id') {
        rule.source_interface_id = parseInt(target.value, 10) || 0;
      } else if (field === 'invert') {
        rule.invert = target.checked;
      } else if (field === 'deadzone') {
        rule.deadzone = target.value ? parseInt(target.value, 10) : null;
      } else if (field === 'transform_type') {
        if (target.value) {
          rule.transform = { type: target.value };
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
  currentConfig.bridge.rate_hz = parseInt(els.inpRateHz.value, 10);
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
    try {
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
    try {
      await protocol.startConfigured();
      alert('Configured persona/bridge started.');
    } catch (e: any) {
      showError(e.message);
    }
  });

  els.btnImportJson.addEventListener('click', () => {
    try {
      currentConfig = JSON.parse(els.txtJsonConfig.value);
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
    currentConfig.mappings.push({
      source_vendor_id: 0,
      source_product_id: 0,
      source_interface_id: 0,
      source_control_id: 'axis_01_30',
      target_control_id: 'x',
      invert: false,
      deadzone: null,
      transform: null
    });
    renderMappings();
    els.txtJsonConfig.value = JSON.stringify(currentConfig, null, 2);
  });

  // Presets
  els.btnPresetGeneric.addEventListener('click', () => {
    currentConfig = JSON.parse(JSON.stringify(flightPackGeneric));
    renderConfig();
    document.querySelector('[data-tab="configure"]')?.dispatchEvent(new Event('click'));
  });

  els.btnPresetXbox.addEventListener('click', () => {
    currentConfig = JSON.parse(JSON.stringify(flightPackXbox));
    renderConfig();
    document.querySelector('[data-tab="configure"]')?.dispatchEvent(new Event('click'));
  });

  // Logs
  els.btnClearLogs.addEventListener('click', () => {
    els.logContainer.innerHTML = '';
  });
}

// Start
init();
