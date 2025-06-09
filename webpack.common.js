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
    // Copy static assets from public to dist
    new CopyPlugin({
      patterns: [
        {
          from: path.resolve('public'),
          to: path.resolve('dist')
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
