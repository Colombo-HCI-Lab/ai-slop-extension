import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
  Logger,
  Inject,
} from '@nestjs/common';
import { Request, Response } from 'express';
import { Observable } from 'rxjs';
import { tap, catchError } from 'rxjs/operators';
import { LoggerService } from './logger.service';
import { WINSTON_MODULE_PROVIDER } from 'nest-winston';

@Injectable()
export class LoggingInterceptor implements NestInterceptor {
  constructor(
    @Inject(WINSTON_MODULE_PROVIDER) private readonly logger: Logger,
    private readonly loggerService: LoggerService,
  ) {}

  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const request = context.switchToHttp().getRequest<Request>();
    const response = context.switchToHttp().getResponse<Response>();
    const method = request.method;
    const url = request.url;
    const headers = request.headers;
    const body = request.body as unknown;
    const userAgent = request.get('User-Agent') || '';
    const ip =
      request.ip ||
      (request.connection as { remoteAddress?: string }).remoteAddress;

    const requestId = this.generateRequestId();
    (request as Request & { requestId: string }).requestId = requestId;

    const startTime = Date.now();

    // Log incoming request with enhanced formatting
    this.loggerService.logApiRequest(method, url, {
      requestId,
      metadata: {
        userAgent:
          userAgent.slice(0, 50) + (userAgent.length > 50 ? '...' : ''),
        ip,
        contentType: headers['content-type'],
        contentLength: headers['content-length'],
        body: this.sanitizeBody(body),
      },
    });

    return next.handle().pipe(
      tap((data: unknown) => {
        const endTime = Date.now();
        const responseTime = endTime - startTime;

        // Log successful response with enhanced formatting
        this.loggerService.logApiResponse(
          method,
          url,
          response.statusCode,
          responseTime,
          {
            requestId,
            metadata: {
              responseSize: JSON.stringify(data ?? {}).length,
            },
          },
        );
      }),
      catchError((error: Error & { status?: number }) => {
        const endTime = Date.now();
        const responseTime = endTime - startTime;

        // Log error response with enhanced formatting
        this.loggerService.error(`Request failed: ${method} ${url}`, error, {
          requestId,
          method,
          url,
          statusCode: error.status ?? 500,
          responseTime: `${responseTime}ms`,
          metadata: {
            errorType: error.constructor.name,
          },
        });

        throw error;
      }),
    );
  }

  private generateRequestId(): string {
    return (
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15)
    );
  }

  private sanitizeBody(body: unknown): unknown {
    if (!body || typeof body !== 'object' || body === null) {
      return body;
    }

    const sensitiveFields = [
      'password',
      'token',
      'authorization',
      'secret',
      'key',
    ];
    const sanitized = { ...(body as Record<string, unknown>) };

    for (const field of sensitiveFields) {
      if (field in sanitized) {
        sanitized[field] = '[REDACTED]';
      }
    }

    return sanitized;
  }
}
