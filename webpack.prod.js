/**
 * Production Webpack Configuration
 * Extends the common configuration with production-specific settings
 * 
 * Features:
 * - Production mode for optimizations
 * - Disabled source maps for smaller bundle size
 * - Enhanced security and performance
 */

const { merge } = require('webpack-merge');
const common = require('./webpack.common.js');

module.exports = merge(common, {
  // Enable production mode for maximum optimization
  mode: 'production',
  // Disable source maps in production for better performance
  devtool: false
});
