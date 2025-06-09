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
  // Enable source maps for debugging
  devtool: 'inline-source-map',
  // Enable watch mode for automatic rebuilds during development
  watch: true
});
