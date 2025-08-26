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
  watch: true
});
