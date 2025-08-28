/**
 * Development Webpack Configuration
 * Extends the common configuration with development-specific settings
 * 
 * Features:
 * - Source maps for debugging
 * - Watch mode for automatic rebuilds
 * - Development mode for better debugging experience
 */

const { merge } = require('webpack-merge');
const common = require('./webpack.common.js');

module.exports = merge(common, {
  // Set webpack to development mode for better debugging
  mode: 'development',
  // Use external source maps to keep background SW small (MV3 4MB limit)
  devtool: 'source-map',
  // Enable watch mode for automatic rebuilds during development
  watch: true,
  optimization: {
    minimize: true, // Enable minimize to ensure Terser runs for UTF-8 compatibility
    minimizer: [
      new (require('terser-webpack-plugin'))({
        terserOptions: {
          mangle: false, // Don't mangle variable names in development
          compress: false, // Don't compress code in development
          format: {
            // Ensure proper line endings for Chrome extension compatibility
            ascii_only: true,
            semicolons: true,
            // Add line breaks to avoid the "no line terminators" issue
            max_line_len: 1000,
            beautify: true, // Keep code readable in development
            indent_level: 2
          }
        }
      })
    ]
  }
});
