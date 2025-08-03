import * as winston from 'winston';
import { WinstonModuleOptions } from 'nest-winston';

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

const dim = (text: string) => `${colors.dim}${text}${colors.reset}`;

const isDevelopment = process.env.NODE_ENV !== 'production';
const logLevel = process.env.LOG_LEVEL || (isDevelopment ? 'debug' : 'info');

// Enhanced color functions for different log components
const logColors = {
  timestamp: (text: string) => colorize(colors.gray, text),
  debug: (text: string) => colorize(colors.cyan, text),
  info: (text: string) => colorize(colors.blue, text),
  warn: (text: string) => colorize(colors.yellow, text),
  error: (text: string) => colorize(colors.red, text),
  context: (text: string) => colorize(colors.green, text),
  method: (text: string) => colorize(colors.magenta, text),
  url: (text: string) => colorize(colors.blue, text),
  statusCode: {
    success: (text: string) => colorize(colors.green, text),
    warning: (text: string) => colorize(colors.yellow, text),
    error: (text: string) => colorize(colors.red, text),
  },
  responseTime: (text: string) => colorize(colors.cyan, text),
  separator: (text: string) => dim(text),
  bracket: (text: string) => dim(text),
  arrow: (text: string) => dim(text),
};

const getStatusCodeColor = (code: number) => {
  if (code >= 200 && code < 300) return logColors.statusCode.success;
  if (code >= 400 && code < 500) return logColors.statusCode.warning;
  if (code >= 500) return logColors.statusCode.error;
  return logColors.statusCode.success;
};

// Custom formatter for development console output with enhanced colors and formatting
const developmentFormat = winston.format.printf(
  (info: {
    level: string;
    message: string;
    timestamp: string;
    context?: string;
    stack?: string;
    method?: string;
    url?: string;
    statusCode?: number;
    responseTime?: string;
    requestId?: string;
    [key: string]: unknown;
  }) => {
    const {
      level,
      message,
      timestamp,
      context,
      stack,
      method,
      url,
      statusCode,
      responseTime,
      requestId,
      ...meta
    } = info;
    const formattedTimestamp = logColors.timestamp(`[${timestamp}]`);

    // Format the log level with appropriate colors
    let levelStr = '';
    switch (level.toLowerCase()) {
      case 'debug':
        levelStr = logColors.debug('DEBUG');
        break;
      case 'info':
        levelStr = logColors.info('INFO ');
        break;
      case 'warn':
        levelStr = logColors.warn('WARN ');
        break;
      case 'error':
        levelStr = logColors.error('ERROR');
        break;
      default:
        levelStr = level.toUpperCase();
    }

    // Format context with colors
    const contextStr = context ? logColors.context(`[${String(context)}]`) : '';

    // Format request information if available
    let requestInfo = '';
    if (
      method &&
      url &&
      typeof method === 'string' &&
      typeof url === 'string'
    ) {
      const methodStr = logColors.method(String(method).padEnd(4));
      const urlStr = logColors.url(String(url));
      const statusStr =
        statusCode && typeof statusCode === 'number'
          ? getStatusCodeColor(statusCode)(`${statusCode}`)
          : '';
      const timeStr = responseTime
        ? logColors.responseTime(String(responseTime))
        : '';
      const reqIdStr =
        requestId && typeof requestId === 'string'
          ? logColors.separator(`req:${requestId.slice(0, 8)}`)
          : '';

      requestInfo = `${logColors.separator('│')} ${methodStr} ${urlStr}`;
      if (statusStr) requestInfo += ` ${logColors.separator('→')} ${statusStr}`;
      if (timeStr)
        requestInfo += ` ${logColors.bracket('(')}${timeStr}${logColors.bracket(')')}`;
      if (reqIdStr)
        requestInfo += ` ${logColors.bracket('[')}${reqIdStr}${logColors.bracket(']')}`;
    }

    // Format metadata if present
    const metaStr =
      Object.keys(meta).length > 0
        ? `\n${logColors.separator('└─')} ${dim(JSON.stringify(meta, null, 2))}`
        : '';

    // Format stack trace if present
    const stackStr = stack ? `\n${logColors.error(String(stack))}` : '';

    // Construct the final log message
    let logLine = `${formattedTimestamp} ${levelStr} ${contextStr} ${String(message)}`;
    if (requestInfo) logLine += `\n${requestInfo}`;

    return `${logLine}${metaStr}${stackStr}`;
  },
);

const logFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  winston.format.errors({ stack: true }),
  isDevelopment
    ? developmentFormat
    : winston.format.combine(
        winston.format.colorize({ all: true }),
        winston.format.printf(
          (info: {
            level: string;
            message: string;
            timestamp: string;
            context?: string;
            stack?: string;
            [key: string]: unknown;
          }) => {
            const { level, message, timestamp, context, stack, ...meta } = info;
            const contextStr = context ? `[${String(context)}]` : '';
            const metaStr =
              Object.keys(meta).length > 0 ? ` ${JSON.stringify(meta)}` : '';
            const stackStr = stack ? `\n${String(stack)}` : '';

            return `${timestamp} ${level} ${contextStr} ${String(message)}${metaStr}${stackStr}`;
          },
        ),
      ),
);

const consoleTransport = new winston.transports.Console({
  level: logLevel,
  format: logFormat,
  handleExceptions: true,
  handleRejections: true,
});

const fileTransports = [
  new winston.transports.File({
    filename: 'logs/error.log',
    level: 'error',
    format: winston.format.combine(
      winston.format.timestamp(),
      winston.format.errors({ stack: true }),
      winston.format.json(),
    ),
    maxsize: 5242880, // 5MB
    maxFiles: 5,
  }),
  new winston.transports.File({
    filename: 'logs/combined.log',
    format: winston.format.combine(
      winston.format.timestamp(),
      winston.format.errors({ stack: true }),
      winston.format.json(),
    ),
    maxsize: 5242880, // 5MB
    maxFiles: 5,
  }),
];

export const winstonConfig: WinstonModuleOptions = {
  transports: isDevelopment
    ? [consoleTransport]
    : [consoleTransport, ...fileTransports],
  level: logLevel,
  handleExceptions: true,
  handleRejections: true,
  exitOnError: false,
};
