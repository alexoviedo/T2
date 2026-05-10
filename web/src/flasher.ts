// We'll dynamically inject the esp-web-tools module script to avoid adding heavy NPM dependencies.
// See: https://esphome.github.io/esp-web-tools/

export function setupFlasher(containerId: string, manifestUrl: string) {
  const container = document.getElementById(containerId);
  if (!container) return;

  // Add the custom element to the container
  container.innerHTML = `
    <div class="flasher-container">
      <h3>Flash Firmware</h3>
      <p>Connect your ESP32-S3 board to flash the latest firmware directly from your browser.</p>

      <!-- ESP Web Tools component -->
      <esp-web-install-button manifest="${manifestUrl}"></esp-web-install-button>

      <div class="flasher-notes">
        <p><small>Note: Web Serial requires Chrome or Edge on desktop.</small></p>
      </div>
    </div>
  `;

  // Inject script if not already present
  if (!document.querySelector('script[src*="esp-web-tools"]')) {
    const script = document.createElement('script');
    script.type = 'module';
    script.src = 'https://unpkg.com/esp-web-tools@10.0.1/dist/web/install-button.js?module';
    document.head.appendChild(script);
  }
}
