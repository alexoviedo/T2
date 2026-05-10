import { SerialConnection } from './serial';
import { RuntimeConfig } from './config-model';

// Use same chunk size as python tool
const CHUNK_BYTES = 72;

export class ProtocolError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ProtocolError';
  }
}

function assertOkOrData(responses: string[], cmd: string, expectedPrefixes: string[] = []) {
  const last = responses[responses.length - 1];
  if (!last) {
    throw new ProtocolError(`Command '${cmd}' failed: Unknown error`);
  }

  if (last.startsWith('ERROR:')) {
    throw new ProtocolError(`Command '${cmd}' failed: ${last}`);
  }

  const hasOk = last.startsWith('OK');
  const hasExpectedPrefix = expectedPrefixes.some(p => last.startsWith(p));

  if (!hasOk && !hasExpectedPrefix) {
    throw new ProtocolError(`Command '${cmd}' failed: Unknown response`);
  }
}

export class BoardProtocol {
  constructor(private serial: SerialConnection) {}

  async getConfigStatus(): Promise<string> {
    const responses = await this.serial.commandResponse('GET_CONFIG_STATUS', ['CONFIG_STATUS:']);
    assertOkOrData(responses, 'GET_CONFIG_STATUS', ['CONFIG_STATUS:']);
    const statusLine = responses.find(r => r.startsWith('CONFIG_STATUS:'));
    return statusLine ? statusLine.substring('CONFIG_STATUS:'.length).trim() : 'UNKNOWN';
  }

  async getConfigSchema(): Promise<string> {
    const responses = await this.serial.commandResponse('GET_CONFIG_SCHEMA', ['CONFIG_SCHEMA:']);
    assertOkOrData(responses, 'GET_CONFIG_SCHEMA', ['CONFIG_SCHEMA:']);
    const schemaLine = responses.find(r => r.startsWith('CONFIG_SCHEMA:'));
    return schemaLine ? schemaLine.substring('CONFIG_SCHEMA:'.length).trim() : '{}';
  }

  async getPersonaSchema(persona: 'generic' | 'xbox'): Promise<string> {
    const responses = await this.serial.commandResponse(`GET_PERSONA_SCHEMA ${persona}`, ['PERSONA_SCHEMA_JSON:']);
    assertOkOrData(responses, `GET_PERSONA_SCHEMA ${persona}`, ['PERSONA_SCHEMA_JSON:']);
    const prefix = `PERSONA_SCHEMA_JSON:`;
    const schemaLine = responses.find(r => r.startsWith(prefix));
    return schemaLine ? schemaLine.substring(prefix.length).trim() : '{}';
  }

  async getInputCatalog(): Promise<string> {
    const responses = await this.serial.commandResponse('GET_INPUT_CATALOG', ['INPUT_CATALOG_JSON:']);
    assertOkOrData(responses, 'GET_INPUT_CATALOG', ['INPUT_CATALOG_JSON:']);
    const catalogLine = responses.find(r => r.startsWith('INPUT_CATALOG_JSON:'));
    return catalogLine ? catalogLine.substring('INPUT_CATALOG_JSON:'.length).trim() : '[]';
  }

  async getConfigJson(): Promise<RuntimeConfig | null> {
    const responses = await this.serial.commandResponse('GET_CONFIG_JSON', ['CONFIG_JSON:']);
    assertOkOrData(responses, 'GET_CONFIG_JSON', ['CONFIG_JSON:']);
    const configLine = responses.find(r => r.startsWith('CONFIG_JSON:'));
    if (!configLine) return null;
    try {
      return JSON.parse(configLine.substring('CONFIG_JSON:'.length).trim()) as RuntimeConfig;
    } catch (e) {
      console.error('Failed to parse config JSON', e);
      return null;
    }
  }

  async saveConfig(): Promise<void> {
    const responses = await this.serial.commandResponse('SAVE_CONFIG', ['CONFIG_ACTION:']);
    assertOkOrData(responses, 'SAVE_CONFIG', ['CONFIG_ACTION:']);
  }

  async loadConfig(): Promise<void> {
    const responses = await this.serial.commandResponse('LOAD_CONFIG', ['CONFIG_ACTION:']);
    assertOkOrData(responses, 'LOAD_CONFIG', ['CONFIG_ACTION:']);
  }

  async resetConfig(): Promise<void> {
    const responses = await this.serial.commandResponse('RESET_CONFIG', ['CONFIG_ACTION:']);
    assertOkOrData(responses, 'RESET_CONFIG', ['CONFIG_ACTION:']);
  }

  async startConfigured(): Promise<void> {
    const responses = await this.serial.commandResponse('START_CONFIGURED', ['CONFIG_ACTION:']);
    assertOkOrData(responses, 'START_CONFIGURED', ['CONFIG_ACTION:']);
  }

  async importConfig(config: RuntimeConfig): Promise<void> {
    // Minify and UTF-8 encode
    const jsonStr = JSON.stringify(config);
    const encoder = new TextEncoder();
    const payload = encoder.encode(jsonStr);

    // Compute SHA-256
    const hashBuffer = await crypto.subtle.digest('SHA-256', payload);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const checksum = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

    // Chunking
    const chunks: string[] = [];
    for (let i = 0; i < payload.length; i += CHUNK_BYTES) {
      const chunkBytes = payload.slice(i, i + CHUNK_BYTES);
      chunks.push(this.base64urlEncode(chunkBytes));
    }

    // Begin
    let responses = await this.serial.commandResponse(`BEGIN_CONFIG_JSON ${chunks.length} ${checksum}`, ['CONFIG_IMPORT:']);
    assertOkOrData(responses, 'BEGIN_CONFIG_JSON', ['CONFIG_IMPORT:']);

    // Chunks
    for (let i = 0; i < chunks.length; i++) {
      responses = await this.serial.commandResponse(`CONFIG_JSON_CHUNK ${i} ${chunks[i]}`, ['CONFIG_IMPORT:']);
      assertOkOrData(responses, `CONFIG_JSON_CHUNK ${i}`, ['CONFIG_IMPORT:']);
    }

    // Commit
    responses = await this.serial.commandResponse('COMMIT_CONFIG_JSON', ['CONFIG_IMPORT:']);
    assertOkOrData(responses, 'COMMIT_CONFIG_JSON', ['CONFIG_IMPORT:']);
  }

  private base64urlEncode(buffer: Uint8Array): string {
    let binary = '';
    for (let i = 0; i < buffer.byteLength; i++) {
      binary += String.fromCharCode(buffer[i]);
    }
    const base64 = btoa(binary);
    return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
}
