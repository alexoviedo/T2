export type SerialLogCallback = (dir: 'tx' | 'rx', text: string) => void;

export class SerialConnection {
  private port: SerialPort | null = null;
  private reader: ReadableStreamDefaultReader<string> | null = null;
  private writer: WritableStreamDefaultWriter<string> | null = null;
  private keepReading = true;
  private readPromise: Promise<void> | null = null;

  // A buffer for partial lines
  private rxBuffer = '';
  // Pending line resolution functions
  private pendingLines: ((line: string) => void)[] = [];

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

    // Set up standard stream with TextDecoder
    const textDecoder = new TextDecoderStream();
    this.readPromise = this.port.readable!.pipeTo(textDecoder.writable as any).catch((e: any) => {
      console.error('Reader error:', e);
    });
    this.reader = textDecoder.readable.getReader();

    // Set up standard stream with TextEncoder
    const textEncoder = new TextEncoderStream();
    textEncoder.readable.pipeTo(this.port.writable as any).catch((e: any) => {
      console.error('Writer error:', e);
    });
    this.writer = textEncoder.writable.getWriter();

    // Start background read loop
    this.readLoop();
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

    if (this.readPromise) {
      await this.readPromise;
    }

    if (this.port) {
      await this.port.close();
      this.port = null;
    }

    this.rxBuffer = '';
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
        if (done) break;
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
            }
          }
        }
      }
    } catch (e) {
      console.error('Read loop error:', e);
    }
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

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        const idx = this.pendingLines.indexOf(resolve);
        if (idx >= 0) {
          this.pendingLines.splice(idx, 1);
        }
        reject(new Error('Timeout waiting for response'));
      }, timeoutMs);

      this.pendingLines.push((line: string) => {
        clearTimeout(timer);
        resolve(line);
      });
    });
  }

  async commandResponse(cmd: string, timeoutMs = 5000): Promise<string[]> {
    await this.writeLine(cmd);
    const responses: string[] = [];

    while (true) {
      const line = await this.readLine(timeoutMs);
      if (line === 'OK' || line.startsWith('ERROR:')) {
        responses.push(line);
        break;
      }
      responses.push(line);
    }

    return responses;
  }
}
