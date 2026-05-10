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

function assertOk(responses: string[], cmd: string) {
  const last = responses[responses.length - 1];
  if (!last || !last.startsWith('OK')) {
    const err = responses.find(r => r.startsWith('ERROR:')) || 'Unknown error';
    throw new ProtocolError(`Command '${cmd}' failed: ${err}`);
  }
}

export class BoardProtocol {
  constructor(private serial: SerialConnection) {}

  async getConfigStatus(): Promise<string> {
    const responses = await this.serial.commandResponse('GET_CONFIG_STATUS');
    assertOk(responses, 'GET_CONFIG_STATUS');
    const statusLine = responses.find(r => r.startsWith('CONFIG_STATUS:'));
    return statusLine ? statusLine.substring('CONFIG_STATUS:'.length).trim() : 'UNKNOWN';
  }

  async getConfigSchema(): Promise<string> {
    const responses = await this.serial.commandResponse('GET_CONFIG_SCHEMA');
    assertOk(responses, 'GET_CONFIG_SCHEMA');
    const schemaLine = responses.find(r => r.startsWith('CONFIG_SCHEMA:'));
    return schemaLine ? schemaLine.substring('CONFIG_SCHEMA:'.length).trim() : '{}';
  }

  async getPersonaSchema(persona: 'generic' | 'xbox'): Promise<string> {
    const responses = await this.serial.commandResponse(`GET_PERSONA_SCHEMA ${persona}`);
    assertOk(responses, `GET_PERSONA_SCHEMA ${persona}`);
    const prefix = `PERSONA_SCHEMA_${persona.toUpperCase()}:`;
    const schemaLine = responses.find(r => r.startsWith(prefix));
    return schemaLine ? schemaLine.substring(prefix.length).trim() : '{}';
  }

  async getInputCatalog(): Promise<string> {
    const responses = await this.serial.commandResponse('GET_INPUT_CATALOG');
    assertOk(responses, 'GET_INPUT_CATALOG');
    const catalogLine = responses.find(r => r.startsWith('INPUT_CATALOG:'));
    return catalogLine ? catalogLine.substring('INPUT_CATALOG:'.length).trim() : '[]';
  }

  async getConfigJson(): Promise<RuntimeConfig | null> {
    const responses = await this.serial.commandResponse('GET_CONFIG_JSON');
    assertOk(responses, 'GET_CONFIG_JSON');
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
    const responses = await this.serial.commandResponse('SAVE_CONFIG');
    assertOk(responses, 'SAVE_CONFIG');
  }

  async loadConfig(): Promise<void> {
    const responses = await this.serial.commandResponse('LOAD_CONFIG');
    assertOk(responses, 'LOAD_CONFIG');
  }

  async resetConfig(): Promise<void> {
    const responses = await this.serial.commandResponse('RESET_CONFIG');
    assertOk(responses, 'RESET_CONFIG');
  }

  async startConfigured(): Promise<void> {
    const responses = await this.serial.commandResponse('START_CONFIGURED');
    assertOk(responses, 'START_CONFIGURED');
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
    let responses = await this.serial.commandResponse(`BEGIN_CONFIG_JSON ${chunks.length} ${checksum}`);
    assertOk(responses, 'BEGIN_CONFIG_JSON');

    // Chunks
    for (let i = 0; i < chunks.length; i++) {
      responses = await this.serial.commandResponse(`CONFIG_JSON_CHUNK ${i} ${chunks[i]}`);
      assertOk(responses, `CONFIG_JSON_CHUNK ${i}`);
    }

    // Commit
    responses = await this.serial.commandResponse('COMMIT_CONFIG_JSON');
    assertOk(responses, 'COMMIT_CONFIG_JSON');
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
