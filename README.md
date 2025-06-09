# FactCheck Eye 👁️

A Chrome extension for real-time fact-checking of Facebook posts.

## Development Setup

### Prerequisites

- Node.js (v14 or higher)
- npm (v6 or higher)
- Google Chrome browser

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/fact-check-extension.git
   cd fact-check-extension
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start development build with watch mode:
   ```bash
   npm start
   ```

4. Load the extension in Chrome:
   - Open Chrome and navigate to `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked" and select the `dist` directory

### Development Commands

- `npm start` - Start development build with watch mode
- `npm run build` - Create production build
- `npm test` - Run tests
- `npm run lint` - Run linting
- `npm run format` - Format code

## Building for Production

Create a production build:
```bash
npm run build
```

The build output will be in the `dist` directory, ready for submission to the Chrome Web Store.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
