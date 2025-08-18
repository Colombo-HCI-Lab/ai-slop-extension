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