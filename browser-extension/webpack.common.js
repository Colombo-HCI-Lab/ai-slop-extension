/**
 * Common Webpack Configuration
 * Shared configuration used by both development and production builds
 * 
 * This config handles:
 * - TypeScript compilation
 * - CSS processing
 * - Asset management
 * - HTML generation
 * - Output directory cleaning
 */

const path = require('path');
const CopyPlugin = require('copy-webpack-plugin');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const { CleanWebpackPlugin } = require('clean-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const webpack = require('webpack');
require('dotenv').config();

module.exports = {
  // Entry points for the extension's different scripts
  entry: {
    popup: path.resolve('src/popup/index.ts'),
    background: path.resolve('src/background/index.ts'),
    content: path.resolve('src/content/index.ts'),
  },
  // Module rules for processing different file types
  module: {
    rules: [
      // TypeScript compilation
      {
        test: /\.tsx?$/,
        use: 'ts-loader',
        exclude: /node_modules/,
      },
      // CSS processing
      {
        test: /\.css$/,
        use: [MiniCssExtractPlugin.loader, 'css-loader'],
      },
      // SCSS processing
      {
        test: /\.scss$/,
        use: [MiniCssExtractPlugin.loader, 'css-loader', 'sass-loader'],
      },
      // Asset handling (images, fonts, etc.)
      {
        test: /\.(jpg|jpeg|png|woff|woff2|eot|ttf|svg)$/,
        type: 'asset/resource'
      }
    ]
  },
  // Module resolution configuration
  resolve: {
    extensions: ['.tsx', '.ts', '.js'],
    alias: {
      '@': path.resolve(__dirname, 'src/')
    }
  },
  // Webpack plugins configuration
  plugins: [
    // Clean output directory before each build
    new CleanWebpackPlugin({
      cleanStaleWebpackAssets: false
    }),
    // Define environment variables
    new webpack.DefinePlugin({
      'process.env.BACKEND_URL': JSON.stringify(process.env.BACKEND_URL)
    }),
    // Copy static assets from public to dist
    new CopyPlugin({
      patterns: [
        {
          from: path.resolve('public'),
          to: path.resolve('dist'),
          globOptions: {
            ignore: ['**/manifest.json']
          }
        },
        // Handle manifest.json separately to inject BACKEND_URL
        {
          from: path.resolve('public/manifest.json'),
          to: path.resolve('dist/manifest.json'),
          transform: (content) => {
            const manifest = JSON.parse(content);
            const backendUrl = process.env.BACKEND_URL;
            
            // Only add backend URL if it's defined
            if (backendUrl) {
              // Update host_permissions to include the backend URL
              const backendHost = new URL(backendUrl).origin + '/*';
              
              // Remove any existing backend API permissions while preserving Facebook permissions
              manifest.host_permissions = manifest.host_permissions.filter(permission => {
                // Keep Facebook permissions
                if (permission.includes('facebook.com')) return true;
                
                // Remove any backend API URLs (localhost, deployed domains, etc.)
                // This matches patterns like "http://localhost:4000/*", "https://api.example.com/*", etc.
                const isBackendUrl = permission.match(/^https?:\/\/[^\/]+\/?\*$/);
                return !isBackendUrl;
              });
              
              // Add the current backend URL
              if (!manifest.host_permissions.includes(backendHost)) {
                manifest.host_permissions.push(backendHost);
              }
            }

            // Ensure the popup is wired to the toolbar action
            manifest.action = manifest.action || {};
            if (!manifest.action.default_popup) {
              manifest.action.default_popup = 'popup.html';
            }
            
            return JSON.stringify(manifest, null, 2);
          }
        }
      ]
    }),
    // Generate popup.html with required scripts
    new HtmlWebpackPlugin({
      template: path.resolve('src/popup/index.html'),
      filename: 'popup.html',
      chunks: ['popup']
    }),
    // Extract CSS into separate files
    new MiniCssExtractPlugin({
      filename: ({ chunk }) => {
        // Use the chunk name for CSS files
        return chunk.name === 'content' ? 'styles.css' : `${chunk.name}.css`;
      }
    })
  ],
  // Output configuration for compiled files
  output: {
    filename: '[name].js',
    path: path.resolve('dist'),
    clean: true
  },
  // Optimization configuration
  optimization: {
    splitChunks: {
      chunks: 'all',
    },
  }
};
