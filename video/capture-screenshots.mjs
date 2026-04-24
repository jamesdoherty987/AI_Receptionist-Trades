/**
 * Screenshot Capture Script
 * 
 * Captures screenshots of your actual running app for the 3D walkthrough video.
 * 
 * USAGE:
 *   1. Start your frontend dev server: cd frontend && npm run dev
 *   2. Run this script: node capture-screenshots.mjs [BASE_URL]
 *      Default BASE_URL is http://localhost:5173
 * 
 * This will save screenshots to video/public/screenshots/
 * Then the 3DWalkthrough Remotion composition will use them.
 * 
 * NOTE: You need to be logged in. The script will wait for you to log in
 * manually, then capture each tab.
 */

import puppeteer from 'puppeteer';
import { mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = resolve(__dirname, 'public/screenshots');
const BASE_URL = process.argv[2] || 'http://localhost:3000';

mkdirSync(SCREENSHOT_DIR, { recursive: true });

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function main() {
  console.log('🚀 Launching browser...');
  const browser = await puppeteer.launch({
    headless: false, // Show browser so you can log in
    defaultViewport: { width: 1920, height: 1080 },
    args: ['--window-size=1920,1080'],
  });

  const page = await browser.newPage();

  console.log(`📍 Navigating to ${BASE_URL}/login`);
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle2' });

  console.log('\n⏳ Please log in to your app in the browser window.');
  console.log('   The script will wait until you reach the dashboard...\n');

  // Wait for dashboard to load (user logs in manually)
  await page.waitForSelector('.dashboard', { timeout: 300000 }); // 5 min timeout
  await sleep(2000); // Let everything render

  console.log('✅ Dashboard detected! Starting screenshot capture...\n');

  // Tab indices based on Dashboard.jsx tab order:
  // 0=Jobs, 1=Calls, 2=Calendar, 3=Employees, 4=Customers, 5=Services, 6=Materials, 7=Finances, 8=Insights
  const tabs = [
    { index: 0, name: 'jobs', label: 'Jobs' },
    { index: 1, name: 'calls', label: 'Calls' },
    { index: 2, name: 'calendar', label: 'Calendar' },
    { index: 3, name: 'employees', label: 'Employees' },
    { index: 4, name: 'customers', label: 'Customers' },
    { index: 5, name: 'services', label: 'Services' },
    { index: 6, name: 'materials', label: 'Materials' },
  ];

  for (const tab of tabs) {
    console.log(`📸 Capturing: ${tab.label} tab...`);

    // Click the tab button
    const tabButtons = await page.$$('.tab-button');
    if (tabButtons[tab.index]) {
      await tabButtons[tab.index].click();
      await sleep(1500); // Wait for tab content to render
    }

    // Take screenshot
    await page.screenshot({
      path: resolve(SCREENSHOT_DIR, `${tab.name}.png`),
      fullPage: false,
    });

    console.log(`   ✅ Saved: screenshots/${tab.name}.png`);
  }

  // Also capture the Settings page
  console.log('📸 Capturing: Settings page...');
  await page.goto(`${BASE_URL}/settings`, { waitUntil: 'networkidle2' });
  await sleep(2000);
  await page.screenshot({
    path: resolve(SCREENSHOT_DIR, 'settings.png'),
    fullPage: false,
  });
  console.log('   ✅ Saved: screenshots/settings.png');

  console.log('\n🎉 All screenshots captured!');
  console.log(`   Location: ${SCREENSHOT_DIR}/`);
  console.log('\n   Now render the 3D walkthrough:');
  console.log('   npx remotion render 3DWalkthrough out/3d-walkthrough.mp4\n');

  await browser.close();
}

main().catch(console.error);
