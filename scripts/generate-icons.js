/**
 * Icon Generation Script
 * Generates PNG icons in multiple sizes from a single SVG source
 * 
 * This script:
 * - Takes SVG source from public/assets/icon16.svg
 * - Generates PNG icons in various sizes required by Chrome extension
 * - Saves generated icons to public/assets directory
 * 
 * Required sizes for Chrome extension:
 * - 16x16: Favicon, extension list
 * - 32x32: Windows computers
 * - 48x48: Display in extension management
 * - 128x128: Chrome Web Store and installation
 */

const sharp = require('sharp');
const path = require('path');
const fs = require('fs').promises;

// Icon sizes required by Chrome extension
const sizes = [16, 32, 48, 128];

/**
 * Generates PNG icons in multiple sizes from SVG source
 * Uses Sharp for high-quality image processing
 * 
 * @throws {Error} If file operations or image processing fails
 */
async function generateIcons() {
  const inputSvg = path.join(__dirname, '../public/assets/icon16.svg');
  const outputDir = path.join(__dirname, '../public/assets');

  try {
    // Create output directory if it doesn't exist
    await fs.mkdir(outputDir, { recursive: true });

    // Process each size and generate corresponding PNG
    for (const size of sizes) {
      await sharp(inputSvg)
        .resize(size, size)
        .png()
        .toFile(path.join(outputDir, `icon${size}.png`));
      
      console.log(`Generated ${size}x${size} icon`);
    }

    console.log('Icon generation complete!');
  } catch (error) {
    console.error('Error generating icons:', error);
    process.exit(1);
  }
}

// Execute the icon generation process
generateIcons();
