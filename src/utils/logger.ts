type LogLevel = 'info' | 'warn' | 'error' | 'debug';

class Logger {
  private formatMessage(level: LogLevel, message: string, context?: Record<string, any>): string {
    const timestamp = new Date().toISOString();
    const contextStr = context ? ` ${JSON.stringify(context)}` : '';
    return `[${timestamp}] [${level.toUpperCase()}] ${message}${contextStr}`;
  }

  info(message: string, context?: Record<string, any>): void {
    console.log(this.formatMessage('info', message, context));
  }

  warn(message: string, context?: Record<string, any>): void {
    console.warn(this.formatMessage('warn', message, context));
  }

  error(message: string, context?: Record<string, any>): void {
    console.error(this.formatMessage('error', message, context));
  }

  debug(message: string, context?: Record<string, any>): void {
    if (process.env.DEBUG === 'true') {
      console.debug(this.formatMessage('debug', message, context));
    }
  }
}

export const logger = new Logger();
