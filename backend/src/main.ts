import { NestFactory } from '@nestjs/core';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { ValidationPipe } from '@nestjs/common';
import { WINSTON_MODULE_NEST_PROVIDER } from 'nest-winston';
import { AppModule } from './app.module';
import { LoggingInterceptor } from './logger/logging.interceptor';
import { LoggerService } from './logger/logger.service';

// ANSI color codes for startup banner
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  blue: '\x1b[34m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
  white: '\x1b[37m',
};

const bold = (text: string) => `${colors.bright}${text}${colors.reset}`;
const colorize = (color: string, text: string) =>
  `${color}${text}${colors.reset}`;

async function bootstrap() {
  const app = await NestFactory.create(AppModule, {
    bufferLogs: true,
  });

  // Configure Winston logger
  app.useLogger(app.get(WINSTON_MODULE_NEST_PROVIDER));
  app.flushLogs();

  // Enable global validation pipes
  app.useGlobalPipes(new ValidationPipe());

  // Enable global logging interceptor
  const loggerService = app.get(LoggerService);
  // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
  const winstonLogger = app.get(WINSTON_MODULE_NEST_PROVIDER);
  app.useGlobalInterceptors(
    // eslint-disable-next-line @typescript-eslint/no-unsafe-argument
    new LoggingInterceptor(winstonLogger, loggerService),
  );

  // Enable CORS for all requests
  app.enableCors({
    origin: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH', 'HEAD'],
    allowedHeaders: [
      'Content-Type',
      'Authorization',
      'X-Requested-With',
      'Accept',
      'Origin',
    ],
    credentials: true,
  });

  // Swagger configuration
  const config = new DocumentBuilder()
    .setTitle('Content Detection API')
    .setDescription(
      'API for detecting AI-generated content in social media posts',
    )
    .setVersion('1.0')
    .addTag('detect', 'Content detection endpoints')
    .addTag('general', 'General application endpoints')
    .addServer('http://localhost:4000', 'Development server')
    .addServer('https://api.detect.example.com', 'Production server')
    .build();

  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('docs', app, document, {
    customSiteTitle: 'Content Detection API Documentation',
    customfavIcon: '/favicon.ico',
    customJs: [
      'https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.15.5/swagger-ui-bundle.min.js',
      'https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.15.5/swagger-ui-standalone-preset.min.js',
    ],
    customCssUrl: [
      'https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.15.5/swagger-ui.min.css',
    ],
  });

  const port = process.env.PORT ?? 4000;
  await app.listen(port);

  const logger = app.get(LoggerService);
  const environment = process.env.NODE_ENV || 'development';
  const logLevel = process.env.LOG_LEVEL || 'debug';

  // Enhanced startup logging with colors and formatting
  console.log('');
  console.log(
    bold(
      colorize(
        colors.blue,
        '┌─────────────────────────────────────────────────────┐',
      ),
    ),
  );
  console.log(
    bold(colorize(colors.blue, '│')) +
      bold(
        colorize(
          colors.white,
          '  🚀 Content Detection API Server Started           ',
        ),
      ) +
      bold(colorize(colors.blue, '│')),
  );
  console.log(
    bold(
      colorize(
        colors.blue,
        '└─────────────────────────────────────────────────────┘',
      ),
    ),
  );
  console.log('');

  logger.log(
    `🌐 ${bold('Server URL:')} ${colorize(colors.cyan, `http://localhost:${port}`)}`,
    {
      action: 'startup',
      metadata: { port, environment },
    },
  );

  logger.log(
    `📚 ${bold('Documentation:')} ${colorize(colors.cyan, `http://localhost:${port}/docs`)}`,
    {
      action: 'startup',
      metadata: { docsPath: '/docs' },
    },
  );

  logger.log(
    `🏗️ ${bold('Environment:')} ${environment === 'development' ? colorize(colors.yellow, environment) : colorize(colors.green, environment)}`,
    {
      action: 'startup',
      metadata: { environment },
    },
  );

  logger.log(`📊 ${bold('Log Level:')} ${colorize(colors.magenta, logLevel)}`, {
    action: 'startup',
    metadata: { logLevel },
  });

  console.log('');
  console.log(
    colorize(
      colors.green,
      '✅ Ready to analyze Facebook posts for AI-generated content!',
    ),
  );
  console.log('');
}

void bootstrap();
