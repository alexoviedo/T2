export type SerialLogCallback = (dir: 'tx' | 'rx', text: string) => void;

export class SerialConnection {
  private static readonly CONNECT_SETTLE_MS = 2500;

  private port: SerialPort | null = null;
  private reader: ReadableStreamDefaultReader<string> | null = null;
  private writer: WritableStreamDefaultWriter<string> | null = null;
  private keepReading = true;
  private readPromise: Promise<void> | null = null;

  // A buffer for partial lines
  private rxBuffer = '';
  // Queue for lines that arrived before a readLine call
  private lineQueue: string[] = [];
  // Pending line resolution functions
  private pendingLines: ((line: string) => void)[] = [];

  // Mutex to prevent concurrent command interleaving
  private commandMutex: Promise<void> = Promise.resolve();

  constructor(private logCallback?: SerialLogCallback) {}

  async requestPort(): Promise<void> {
    if (!navigator.serial) {
      throw new Error('Web Serial is not supported in this browser.');
    }
    this.port = await navigator.serial.requestPort();
  }

  async connect(): Promise<void> {
    if (!this.port) {
      throw new Error('No port selected.');
    }

    await this.port.open({ baudRate: 115200 });
    this.keepReading = true;

    await this.setConsoleSignals();

    // Set up standard stream with TextDecoder
    const textDecoder = new TextDecoderStream();
    this.readPromise = this.port.readable!.pipeTo(textDecoder.writable as any).catch((e: any) => {
      console.error('Reader error:', e);
    });
    this.reader = textDecoder.readable.getReader();

    // Set up standard stream with TextEncoder
    const textEncoder = new TextEncoderStream();
    const writePromise = textEncoder.readable.pipeTo(this.port.writable as any).catch((e: any) => {
      console.error('Writer error:', e);
    });
    (this as any).writePromise = writePromise;
    this.writer = textEncoder.writable.getWriter();

    // Start background read loop
    this.readLoop();

    // Some ESP32-S3 USB CDC adapters reset or briefly stall the console when a
    // browser opens the port. Let boot chatter drain before the first command.
    await this.delay(SerialConnection.CONNECT_SETTLE_MS);
    this.clearBufferedInput();
  }

  async disconnect(): Promise<void> {
    this.keepReading = false;

    if (this.reader) {
      await this.reader.cancel();
      this.reader.releaseLock();
    }

    if (this.writer) {
      await this.writer.close();
      this.writer.releaseLock();
    }

    if ((this as any).writePromise) {
      await (this as any).writePromise;
    }

    if (this.readPromise) {
      await this.readPromise;
    }

    if (this.port) {
      await this.port.close();
      this.port = null;
    }

    this.rxBuffer = '';
    this.lineQueue = [];
    this.pendingLines = [];
  }

  isConnected(): boolean {
    return this.port !== null && this.keepReading;
  }

  private async readLoop() {
    if (!this.reader) return;

    try {
      while (this.keepReading) {
        const { value, done } = await this.reader.read();
        if (done) {
          this.keepReading = false;
          break;
        }
        if (value) {
          this.rxBuffer += value;
          let newlineIdx;
          while ((newlineIdx = this.rxBuffer.indexOf('\n')) >= 0) {
            const line = this.rxBuffer.slice(0, newlineIdx).replace(/\r$/, '');
            this.rxBuffer = this.rxBuffer.slice(newlineIdx + 1);

            if (this.logCallback) {
              this.logCallback('rx', line);
            }

            if (this.pendingLines.length > 0) {
              const resolver = this.pendingLines.shift()!;
              resolver(line);
            } else {
              this.lineQueue.push(line);
            }
          }
        }
      }
    } catch (e) {
      console.error('Read loop error:', e);
    }
  }

  private async setConsoleSignals(): Promise<void> {
    if (!this.port?.setSignals) {
      return;
    }

    try {
      await this.port.setSignals({
        dataTerminalReady: true,
        requestToSend: true,
      });
    } catch (e) {
      console.warn('Unable to set serial console signals:', e);
    }
  }

  private clearBufferedInput(): void {
    this.rxBuffer = '';
    this.lineQueue = [];
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async writeLine(line: string): Promise<void> {
    if (!this.writer) throw new Error('Not connected');

    if (this.logCallback) {
      this.logCallback('tx', line);
    }

    await this.writer.write(line + '\r\n');
  }

  async readLine(timeoutMs = 5000): Promise<string> {
    if (!this.keepReading) throw new Error('Not connected');

    if (this.lineQueue.length > 0) {
      return this.lineQueue.shift()!;
    }

    return new Promise((resolve, reject) => {
      let wrapper: (line: string) => void;

      const timer = setTimeout(() => {
        const idx = this.pendingLines.indexOf(wrapper);
        if (idx >= 0) {
          this.pendingLines.splice(idx, 1);
        }
        reject(new Error('Timeout waiting for response'));
      }, timeoutMs);

      wrapper = (line: string) => {
        clearTimeout(timer);
        resolve(line);
      };

      this.pendingLines.push(wrapper);
    });
  }

  async commandResponse(cmd: string, expectedPrefixes: string[] = [], timeoutMs = 10000): Promise<string[]> {
    const execute = async () => {
      // Drain stale lines before sending the command, but preserve pending lines
      this.lineQueue = [];

      await this.writeLine(cmd);
      const responses: string[] = [];
      const deadline = Date.now() + timeoutMs;
      const expectsData = expectedPrefixes.length > 0;

      while (true) {
        const remainingMs = deadline - Date.now();
        if (remainingMs <= 0) {
          throw new Error(`Timeout waiting for response to ${cmd}`);
        }

        let line = await this.readLine(remainingMs);
        if (!line) continue; // Skip flushed empty lines if any

        if (expectsData) {
          const expectedOffset = expectedPrefixes
            .map(prefix => line.indexOf(prefix))
            .filter(index => index >= 0)
            .sort((a, b) => a - b)[0];
          if (expectedOffset !== undefined && expectedOffset > 0) {
            line = line.slice(expectedOffset);
          }
        }

        responses.push(line);

        if (!expectsData && (line === 'OK' || line.startsWith('ERROR:'))) {
          break;
        }

        const hasExpectedPrefix = expectedPrefixes.some(prefix => line.startsWith(prefix));
        if (hasExpectedPrefix) {
          break;
        }
      }

      return responses;
    };

    // Acquire lock
    const currentMutex = this.commandMutex;
    let releaseMutex: () => void;
    this.commandMutex = new Promise<void>(resolve => {
      releaseMutex = resolve;
    });

    try {
      await currentMutex;
      return await execute();
    } finally {
      releaseMutex!();
    }
  }
}
