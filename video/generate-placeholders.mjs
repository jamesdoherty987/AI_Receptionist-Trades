/**
 * Generates placeholder screenshot PNGs for the 3D walkthrough video.
 * These are temporary — replace with real screenshots using capture-screenshots.mjs
 */
import { writeFileSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const dir = resolve(__dirname, 'public/screenshots');
mkdirSync(dir, { recursive: true });

// Minimal valid 1920x1080 PNG (1x1 pixel scaled won't work, so we create an SVG-based approach)
// We'll create simple HTML files that can be opened, but for Remotion we need actual images.
// Let's create minimal placeholder PNGs using a data approach.

const tabs = ['jobs', 'calls', 'calendar', 'workers', 'customers', 'services', 'materials'];
const colors = ['#3b82f6', '#06d6a0', '#7c3aed', '#ff6b35', '#ff006e', '#ffd60a', '#3a86ff'];
const icons = ['📋', '📞', '📅', '👷', '👥', '🔧', '📦'];

// Create SVG placeholders and convert to simple format
for (let i = 0; i < tabs.length; i++) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#f8fafc"/>
      <stop offset="100%" style="stop-color:#e2e8f0"/>
    </linearGradient>
  </defs>
  <rect width="1920" height="1080" fill="url(#bg)"/>
  <rect x="0" y="0" width="1920" height="64" fill="#ffffff" opacity="0.9"/>
  <text x="80" y="42" font-family="Arial" font-size="24" font-weight="bold" fill="#1e293b">⚡ BookedForYou</text>
  <rect x="0" y="64" width="1920" height="52" fill="#f1f5f9"/>
  <rect x="20" y="72" width="100" height="36" rx="8" fill="${colors[i]}" opacity="0.9"/>
  <text x="40" y="96" font-family="Arial" font-size="14" font-weight="bold" fill="white">${tabs[i].charAt(0).toUpperCase() + tabs[i].slice(1)}</text>
  <text x="960" y="500" font-family="Arial" font-size="120" text-anchor="middle" fill="${colors[i]}" opacity="0.3">${icons[i]}</text>
  <text x="960" y="580" font-family="Arial" font-size="36" text-anchor="middle" fill="#94a3b8" font-weight="bold">PLACEHOLDER — Replace with real screenshot</text>
  <text x="960" y="630" font-family="Arial" font-size="22" text-anchor="middle" fill="#cbd5e1">Run: node capture-screenshots.mjs</text>
  <rect x="40" y="140" width="580" height="200" rx="16" fill="white" stroke="#e2e8f0"/>
  <rect x="40" y="360" width="580" height="200" rx="16" fill="white" stroke="#e2e8f0"/>
  <rect x="640" y="140" width="580" height="420" rx="16" fill="white" stroke="#e2e8f0"/>
  <rect x="1240" y="140" width="640" height="200" rx="16" fill="white" stroke="#e2e8f0"/>
  <rect x="1240" y="360" width="640" height="200" rx="16" fill="white" stroke="#e2e8f0"/>
</svg>`;

  writeFileSync(resolve(dir, `${tabs[i]}.svg`), svg);
  console.log(`✅ Created placeholder: screenshots/${tabs[i]}.svg`);
}

console.log('\n⚠️  These are SVG placeholders.');
console.log('   For the real video, run: node capture-screenshots.mjs');
console.log('   to capture actual PNG screenshots of your app.');
