# Browser Extension

Chrome extension for real-time AI content detection on Facebook.

## Quick Setup

```bash
# Install dependencies
npm install

# Start development build
npm start

# Load extension in Chrome
# Go to chrome://extensions/
# Enable "Developer mode"
# Click "Load unpacked" and select the 'dist' directory
```

## Development

```bash
npm start        # Development build with watch mode
npm run build    # Production build
npm test         # Run tests
```

## Documentation

- **[Extension Guide](../docs/extension-guide.md)** - Complete development guide, architecture, and features
- **[Post ID Flow](../docs/post-id-flow.md)** - How Facebook post IDs are tracked throughout the system

## Structure

- `src/background/`
  - `index.ts`: entry only
  - `messaging.ts`: message routing and action click
  - `api.ts`: API endpoints and normalization
  - `state.ts`: in-flight request de-dupe
- `src/content/`
  - `index.ts`: content bootstrap (imports styles)
  - `messaging.ts`: typed wrappers over `chrome.runtime.sendMessage`
- `src/shared/`
  - `messages.ts`: message enums and payload types
  - `env.ts`: backend URL helpers (Webpack DefinePlugin)
  - `constants.ts`, `storage.ts`, `logger.ts`
  - `net/retry.ts`: fetch with retry/timeout
- `src/styles/`
  - `index.scss`: central stylesheet import
  - `_theme.scss`: tokens and mixins

This layout separates concerns by layer (background/content/shared) and keeps the entry files slim and focused on wiring.
