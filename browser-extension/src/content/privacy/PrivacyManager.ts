/**
 * PrivacyManager - Handles privacy controls and GDPR compliance
 */

import { log, error } from '../../shared/logger';

export interface PrivacySettings {
  privacyMode: 'strict' | 'balanced' | 'full';
  dataCollection: boolean;
  errorReporting: boolean;
  performanceTracking: boolean;
  chatHistory: boolean;
}

export interface ConsentStatus {
  hasConsent: boolean;
  consentDate?: Date;
  consentVersion?: string;
  gdprApplies: boolean;
}

export interface UserDataExport {
  userData: unknown;
  events: unknown[];
  interactions: unknown[];
  exportedAt: string;
}

export class PrivacyManager {
  private settings: PrivacySettings;
  private consentStatus: ConsentStatus;

  private readonly defaultSettings: PrivacySettings = {
    privacyMode: 'full',
    dataCollection: true,
    errorReporting: true,
    performanceTracking: true,
    chatHistory: true,
  };

  constructor() {
    this.settings = this.defaultSettings;
    this.consentStatus = {
      hasConsent: true, // Pre-consented research users
      gdprApplies: false,
    };
  }

  public async initialize(): Promise<void> {
    try {
      // Load saved privacy settings
      await this.loadSettings();

      // Research mode: All users have pre-consented to full data collection
      this.consentStatus.hasConsent = true;
      this.consentStatus.consentDate = new Date();
      this.consentStatus.consentVersion = 'research-v1.0';
      this.consentStatus.gdprApplies = false; // Research exemption

      log('PrivacyManager initialized', {
        gdprApplies: this.consentStatus.gdprApplies,
        hasConsent: this.consentStatus.hasConsent,
        privacyMode: this.settings.privacyMode,
      });
    } catch (err) {
      error('Failed to initialize PrivacyManager:', err);
      // Even on error, maintain research mode settings
      this.settings.privacyMode = 'full';
      this.consentStatus.hasConsent = true;
    }
  }

  public shouldCollectMetric(metricType: string): boolean {
    // Research mode: Always collect all metrics
    return true;
  }

  public shouldCollectEvent(eventType: string): boolean {
    // Research mode: Always collect all events
    return true;
  }

  public async updateSettings(newSettings: Partial<PrivacySettings>): Promise<void> {
    this.settings = { ...this.settings, ...newSettings };
    await this.saveSettings();
    log('Privacy settings updated', this.settings);
  }

  public getSettings(): PrivacySettings {
    return { ...this.settings };
  }

  public async exportUserData(userId: string): Promise<UserDataExport> {
    try {
      // In a real implementation, this would call the backend
      log('Exporting user data for GDPR request', { userId });

      return {
        userData: { userId, settings: this.settings },
        events: [], // Would be populated from backend
        interactions: [], // Would be populated from backend
        exportedAt: new Date().toISOString(),
      };
    } catch (err) {
      error('Failed to export user data:', err);
      throw error;
    }
  }

  public async deleteUserData(userId: string): Promise<void> {
    try {
      log('Deleting user data for GDPR request', { userId });

      // Clear local storage
      await chrome.storage.local.remove([
        'ai-slop-user-id',
        'ai-slop-privacy-settings',
        'ai-slop-consent-status',
        'ai-slop-metrics',
      ]);

      // In a real implementation, this would also call backend
      // await this.callBackendDeleteUser(userId);

      // Reset privacy manager
      this.settings = this.defaultSettings;
      this.consentStatus = {
        hasConsent: false,
        gdprApplies: this.isGDPRRegion(),
      };

      log('User data deletion completed');
    } catch (err) {
      error('Failed to delete user data:', err);
      throw error;
    }
  }

  public async revokeConsent(): Promise<void> {
    this.consentStatus.hasConsent = false;
    this.consentStatus.consentDate = undefined;
    await this.saveConsentStatus();
    log('User consent revoked');
  }

  private async loadSettings(): Promise<void> {
    try {
      const result = await chrome.storage.local.get(['ai-slop-privacy-settings']);
      if (result['ai-slop-privacy-settings']) {
        this.settings = { ...this.defaultSettings, ...result['ai-slop-privacy-settings'] };
      }
    } catch (error) {
      log('No saved privacy settings found, using defaults');
    }
  }

  private async saveSettings(): Promise<void> {
    try {
      await chrome.storage.local.set({
        'ai-slop-privacy-settings': this.settings,
      });
    } catch (err) {
      error('Failed to save privacy settings:', err);
    }
  }

  private async checkConsentStatus(): Promise<void> {
    try {
      const result = await chrome.storage.local.get(['ai-slop-consent-status']);
      if (result['ai-slop-consent-status']) {
        const saved = result['ai-slop-consent-status'];
        this.consentStatus = {
          hasConsent: saved.hasConsent,
          consentDate: saved.consentDate ? new Date(saved.consentDate) : undefined,
          consentVersion: saved.consentVersion,
          gdprApplies: true,
        };

        // Check if consent is still valid (12 months)
        if (this.consentStatus.consentDate) {
          const consentAge = Date.now() - this.consentStatus.consentDate.getTime();
          const maxAge = 365 * 24 * 60 * 60 * 1000; // 1 year in milliseconds

          if (consentAge > maxAge) {
            log('Consent has expired, requesting new consent');
            this.consentStatus.hasConsent = false;
          }
        }
      }
    } catch (error) {
      log('No saved consent status found');
    }
  }

  private async saveConsentStatus(): Promise<void> {
    try {
      await chrome.storage.local.set({
        'ai-slop-consent-status': {
          hasConsent: this.consentStatus.hasConsent,
          consentDate: this.consentStatus.consentDate?.toISOString(),
          consentVersion: this.consentStatus.consentVersion,
          gdprApplies: this.consentStatus.gdprApplies,
        },
      });
    } catch (err) {
      error('Failed to save consent status:', err);
    }
  }

  private async requestConsent(): Promise<void> {
    // In a real implementation, this would show a consent banner/modal
    // For now, we'll log and assume consent for development
    log('GDPR consent required - showing consent banner');

    // Simulate user giving consent for development
    if (process.env.NODE_ENV === 'development') {
      await this.giveConsent();
    }
  }

  private async giveConsent(): Promise<void> {
    this.consentStatus.hasConsent = true;
    this.consentStatus.consentDate = new Date();
    this.consentStatus.consentVersion = '1.0';
    await this.saveConsentStatus();
    log('User consent granted');
  }

  private isGDPRRegion(): boolean {
    try {
      const gdprCountries = [
        'AT',
        'BE',
        'BG',
        'CY',
        'CZ',
        'DE',
        'DK',
        'EE',
        'ES',
        'FI',
        'FR',
        'GR',
        'HR',
        'HU',
        'IE',
        'IT',
        'LT',
        'LU',
        'LV',
        'MT',
        'NL',
        'PL',
        'PT',
        'RO',
        'SE',
        'SI',
        'SK',
      ];

      // Check timezone for rough location estimation
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const language = navigator.language;

      // Simple heuristics - in production you'd use proper geolocation
      return gdprCountries.some(
        country =>
          timezone.includes(country) ||
          language.toUpperCase().includes(country) ||
          timezone.includes('Europe')
      );
    } catch (error) {
      log('Could not determine GDPR region:', error);
      return false; // Default to non-GDPR to avoid blocking users
    }
  }
}

// Singleton instance
export const privacyManager = new PrivacyManager();
