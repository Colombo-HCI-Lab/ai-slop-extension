/**
 * InitializationGate - Prevents extension activities until user/session are validated
 * Provides blocking mechanisms and protection wrappers for all extension functionality
 */

import { log, error } from './logger';
import { SessionManager, UserSessionData } from './SessionManager';

export interface InitializationGateConfig {
  enableLogging: boolean;
  timeoutMs: number;
}

export interface InitializationStatus {
  isInitialized: boolean;
  sessionData: UserSessionData | null;
  initializationTime: number | null;
  error: string | null;
}

/**
 * Singleton service that blocks all extension activities until proper initialization
 */
export class InitializationGate {
  private static instance: InitializationGate | null = null;
  
  private isInitialized: boolean = false;
  private initializationPromise: Promise<void> | null = null;
  private sessionManager: SessionManager | null = null;
  private config: InitializationGateConfig;
  private initializationTime: number | null = null;
  private lastError: string | null = null;

  private constructor(config: InitializationGateConfig = { enableLogging: true, timeoutMs: 30000 }) {
    this.config = config;
    
    if (this.config.enableLogging) {
      log('InitializationGate created');
    }
  }

  /**
   * Get singleton instance
   */
  static getInstance(config?: InitializationGateConfig): InitializationGate {
    if (!InitializationGate.instance) {
      InitializationGate.instance = new InitializationGate(config);
    }
    return InitializationGate.instance;
  }

  /**
   * Initialize with SessionManager and wait for session validation
   */
  async initialize(sessionManager: SessionManager): Promise<void> {
    if (this.isInitialized) {
      return;
    }

    // If initialization is already in progress, wait for it
    if (this.initializationPromise) {
      return this.initializationPromise;
    }

    this.sessionManager = sessionManager;
    
    this.initializationPromise = this.performInitialization();
    
    try {
      await this.initializationPromise;
      this.isInitialized = true;
      this.initializationTime = Date.now();
      this.lastError = null;
      
      if (this.config.enableLogging) {
        log('InitializationGate initialization complete');
      }
    } catch (err) {
      this.lastError = String(err);
      this.initializationPromise = null;
      error('InitializationGate initialization failed', err);
      throw err;
    }
  }

  /**
   * Wait for initialization to complete - blocks until ready
   */
  async waitForInitialization(): Promise<void> {
    if (this.isInitialized) {
      return;
    }

    if (!this.initializationPromise) {
      throw new Error('InitializationGate not initialized. Call initialize() first.');
    }

    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => {
        reject(new Error(`InitializationGate timeout after ${this.config.timeoutMs}ms`));
      }, this.config.timeoutMs);
    });

    try {
      await Promise.race([this.initializationPromise, timeoutPromise]);
    } catch (err) {
      error('InitializationGate wait timeout or error', err);
      throw err;
    }
  }

  /**
   * Check if initialization is complete
   */
  isReady(): boolean {
    return this.isInitialized;
  }

  /**
   * Get current initialization status
   */
  getStatus(): InitializationStatus {
    return {
      isInitialized: this.isInitialized,
      sessionData: this.sessionManager?.getCurrentSession() || null,
      initializationTime: this.initializationTime,
      error: this.lastError
    };
  }

  /**
   * Require initialization - throws if not ready
   */
  requireInitialized(): UserSessionData {
    if (!this.isInitialized || !this.sessionManager) {
      throw new Error('Extension not initialized. User session validation required.');
    }

    return this.sessionManager.requireValidSession();
  }

  /**
   * Wrapper for protected activities - ensures initialization before execution
   */
  async protectedExecution<T>(
    operation: () => T | Promise<T>,
    operationName?: string
  ): Promise<T> {
    const opName = operationName || 'protected operation';
    
    try {
      await this.waitForInitialization();
      
      if (this.config.enableLogging) {
        log(`Executing protected operation: ${opName}`);
      }
      
      return await operation();
    } catch (err) {
      error(`Protected operation failed: ${opName}`, err);
      throw err;
    }
  }

  /**
   * Wrapper for protected activities - synchronous version
   */
  protectedExecutionSync<T>(
    operation: () => T,
    operationName?: string
  ): T {
    const opName = operationName || 'protected operation';
    
    if (!this.isInitialized) {
      throw new Error(`Cannot execute ${opName}: Extension not initialized`);
    }

    try {
      if (this.config.enableLogging) {
        log(`Executing protected sync operation: ${opName}`);
      }
      
      return operation();
    } catch (err) {
      error(`Protected sync operation failed: ${opName}`, err);
      throw err;
    }
  }

  /**
   * Create a protected wrapper function
   */
  createProtectedWrapper<T extends (...args: any[]) => any>(
    fn: T,
    operationName?: string
  ): (...args: Parameters<T>) => Promise<ReturnType<T>> {
    return async (...args: Parameters<T>): Promise<ReturnType<T>> => {
      return this.protectedExecution(() => fn(...args), operationName);
    };
  }

  /**
   * Create a protected wrapper function - synchronous version
   */
  createProtectedWrapperSync<T extends (...args: any[]) => any>(
    fn: T,
    operationName?: string
  ): (...args: Parameters<T>) => ReturnType<T> {
    return (...args: Parameters<T>): ReturnType<T> => {
      return this.protectedExecutionSync(() => fn(...args), operationName);
    };
  }

  /**
   * Reset initialization state - useful for testing or error recovery
   */
  reset(): void {
    this.isInitialized = false;
    this.initializationPromise = null;
    this.sessionManager = null;
    this.initializationTime = null;
    this.lastError = null;
    
    if (this.config.enableLogging) {
      log('InitializationGate reset');
    }
  }

  /**
   * Reset singleton instance - for testing only
   */
  static resetInstance(): void {
    InitializationGate.instance = null;
  }

  /**
   * Perform the actual initialization
   */
  private async performInitialization(): Promise<void> {
    if (!this.sessionManager) {
      throw new Error('SessionManager not provided');
    }

    if (this.config.enableLogging) {
      log('InitializationGate starting session validation');
    }

    // Wait for SessionManager to validate/initialize user session
    await this.sessionManager.initializeUserSession();

    if (this.config.enableLogging) {
      log('InitializationGate session validation complete');
    }
  }
}

/**
 * Convenience functions for common usage patterns
 */

// Global gate instance
let globalGate: InitializationGate | null = null;

/**
 * Get the global InitializationGate instance
 */
export function getGlobalGate(): InitializationGate {
  if (!globalGate) {
    globalGate = InitializationGate.getInstance();
  }
  return globalGate;
}

/**
 * Initialize the global gate
 */
export async function initializeGlobalGate(sessionManager: SessionManager): Promise<void> {
  const gate = getGlobalGate();
  await gate.initialize(sessionManager);
}

/**
 * Wait for global gate initialization
 */
export async function waitForGlobalInitialization(): Promise<void> {
  const gate = getGlobalGate();
  await gate.waitForInitialization();
}

/**
 * Require global initialization
 */
export function requireGlobalInitialization(): UserSessionData {
  const gate = getGlobalGate();
  return gate.requireInitialized();
}

/**
 * Execute protected operation using global gate
 */
export async function protectedExecute<T>(
  operation: () => T | Promise<T>,
  operationName?: string
): Promise<T> {
  const gate = getGlobalGate();
  return gate.protectedExecution(operation, operationName);
}

/**
 * Execute protected synchronous operation using global gate
 */
export function protectedExecuteSync<T>(
  operation: () => T,
  operationName?: string
): T {
  const gate = getGlobalGate();
  return gate.protectedExecutionSync(operation, operationName);
}