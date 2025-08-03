import { Injectable, Logger } from '@nestjs/common';

// ANSI color codes for terminal output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',
  gray: '\x1b[90m',
};

// Helper functions for colored text
const colorize = (color: string, text: string) =>
  `${color}${text}${colors.reset}`;
const bold = (text: string) => `${colors.bright}${text}${colors.reset}`;
const dim = (text: string) => `${colors.dim}${text}${colors.reset}`;

const chalk = {
  bold,
  green: (text: string) => colorize(colors.green, text),
  yellow: (text: string) => colorize(colors.yellow, text),
  red: (text: string) => colorize(colors.red, text),
  dim,
};

export interface LogContext {
  requestId?: string;
  userId?: string;
  postId?: string;
  action?: string;
  method?: string;
  url?: string;
  statusCode?: number;
  responseTime?: string;
  metadata?: Record<string, any>;
}

interface EnhancedLogData {
  message: string;
  context?: string;
  requestId?: string;
  method?: string;
  url?: string;
  statusCode?: number;
  responseTime?: string;
  [key: string]: any;
}

@Injectable()
export class LoggerService {
  private readonly logger = new Logger(LoggerService.name);

  log(message: string, context?: LogContext) {
    const logData = this.buildLogData(message, context);
    this.logger.log(logData);
  }

  debug(message: string, context?: LogContext) {
    const logData = this.buildLogData(message, context);
    this.logger.debug(logData);
  }

  warn(message: string, context?: LogContext) {
    const logData = this.buildLogData(message, context);
    this.logger.warn(logData);
  }

  error(message: string, error?: Error, context?: LogContext) {
    const logData = this.buildLogData(message, context);
    if (error) {
      logData.stack = error.stack;
      logData.message = `${message}: ${error.message}`;
    }
    this.logger.error(logData);
  }

  verbose(message: string, context?: LogContext) {
    const logData = this.buildLogData(message, context);
    this.logger.verbose(logData);
  }

  // Specialized logging methods for common operations
  logApiRequest(method: string, url: string, context?: LogContext) {
    const emoji = this.getMethodEmoji(method);
    this.log(`${emoji} ${chalk.bold('Incoming Request')}`, {
      ...context,
      method,
      url,
      action: 'api_request',
    });
  }

  logApiResponse(
    method: string,
    url: string,
    statusCode: number,
    responseTime: number,
    context?: LogContext,
  ) {
    const emoji = this.getStatusEmoji(statusCode);
    const status = this.getStatusText(statusCode);
    this.log(`${emoji} ${chalk.bold('Request Completed')} - ${status}`, {
      ...context,
      method,
      url,
      statusCode,
      responseTime: `${responseTime}ms`,
      action: 'api_response',
    });
  }

  logAiAnalysis(
    postId: string,
    verdict: string,
    confidence: number,
    context?: LogContext,
  ) {
    const emoji =
      verdict === 'ai_slop' ? '🤖' : verdict === 'human_content' ? '👤' : '❓';
    const confidenceBar = this.getConfidenceBar(confidence);
    this.log(
      `${emoji} ${chalk.bold('AI Analysis Complete')} - ${verdict.toUpperCase()} ${confidenceBar}`,
      {
        ...context,
        postId,
        action: 'ai_analysis',
        metadata: {
          ...context?.metadata,
          verdict,
          confidence,
        },
      },
    );
  }

  logContentExtraction(
    postId: string,
    contentLength: number,
    context?: LogContext,
  ) {
    const emoji = '📝';
    const sizeIndicator = this.getSizeIndicator(contentLength);
    this.log(
      `${emoji} ${chalk.bold('Content Extracted')} - ${contentLength} chars ${sizeIndicator}`,
      {
        ...context,
        postId,
        action: 'content_extraction',
        metadata: {
          ...context?.metadata,
          contentLength,
        },
      },
    );
  }

  logError(operation: string, error: Error, context?: LogContext) {
    const emoji = '❌';
    this.error(
      `${emoji} ${chalk.bold('Operation Failed')} - ${operation}`,
      error,
      {
        ...context,
        action: 'error',
        metadata: {
          ...context?.metadata,
          operation,
          errorType: error.constructor.name,
        },
      },
    );
  }

  private buildLogData(message: string, context?: LogContext): EnhancedLogData {
    const logData: EnhancedLogData = { message };

    if (context) {
      if (context.requestId) logData.requestId = context.requestId;
      if (context.method) logData.method = context.method;
      if (context.url) logData.url = context.url;
      if (context.statusCode) logData.statusCode = context.statusCode;
      if (context.responseTime) logData.responseTime = context.responseTime;
      if (context.action) logData.context = context.action;

      // Add other context properties as metadata
      const otherProps = Object.keys(context).filter(
        (key) =>
          ![
            'requestId',
            'method',
            'url',
            'statusCode',
            'responseTime',
            'action',
          ].includes(key),
      );

      otherProps.forEach((key) => {
        logData[key] = context[key as keyof LogContext];
      });
    }

    return logData;
  }

  private getMethodEmoji(method: string): string {
    const methodEmojis: Record<string, string> = {
      GET: '📥',
      POST: '📤',
      PUT: '🔄',
      DELETE: '🗑️',
      PATCH: '✏️',
    };
    return methodEmojis[method.toUpperCase()] || '📡';
  }

  private getStatusEmoji(statusCode: number): string {
    if (statusCode >= 200 && statusCode < 300) return '✅';
    if (statusCode >= 300 && statusCode < 400) return '🔄';
    if (statusCode >= 400 && statusCode < 500) return '⚠️';
    if (statusCode >= 500) return '❌';
    return '❓';
  }

  private getStatusText(statusCode: number): string {
    if (statusCode >= 200 && statusCode < 300)
      return chalk.green(`${statusCode} Success`);
    if (statusCode >= 300 && statusCode < 400)
      return chalk.yellow(`${statusCode} Redirect`);
    if (statusCode >= 400 && statusCode < 500)
      return chalk.yellow(`${statusCode} Client Error`);
    if (statusCode >= 500) return chalk.red(`${statusCode} Server Error`);
    return `${statusCode} Unknown`;
  }

  private getConfidenceBar(confidence: number): string {
    const blocks = '█'.repeat(Math.round(confidence / 10));
    const empty = '░'.repeat(10 - Math.round(confidence / 10));
    const colorFunc =
      confidence > 80
        ? chalk.green
        : confidence > 60
          ? chalk.yellow
          : chalk.red;
    return `${colorFunc(blocks)}${chalk.dim(empty)} ${confidence}%`;
  }

  private getSizeIndicator(size: number): string {
    if (size < 100) return chalk.dim('(tiny)');
    if (size < 500) return chalk.dim('(small)');
    if (size < 1000) return chalk.dim('(medium)');
    if (size < 5000) return chalk.dim('(large)');
    return chalk.dim('(huge)');
  }
}
