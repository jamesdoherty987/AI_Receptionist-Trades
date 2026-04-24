/**
 * MenuDesigner — Restaurant-only visual menu builder with PDF export.
 *
 * Reads services from the ServicesTab and lets the owner:
 *   1. Pick which categories/items to include
 *   2. Choose a visual theme (fonts, colours)
 *   3. Add header (restaurant name, tagline, logo) and footer (address, allergen notice)
 *   4. Preview the menu live
 *   5. Download as PDF (uses browser print-to-PDF)
 *
 * Entirely config-driven via serviceConfig.menuDesigner in industryProfiles.
 */
import { useState, useMemo, useRef, useCallback } from 'react';
import { useIndustry } from '../../context/IndustryContext';
import './MenuDesigner.css';

// ─── Helpers ─────────────────────────────────────────────────────────────────
function groupByCategory(services) {
  const groups = {};
  for (const svc of services) {
    const cat = svc.category || 'Other';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(svc);
  }
  return groups;
}

function parseTags(tags) {
  if (!tags) return [];
  if (Array.isArray(tags)) return tags;
  try { return JSON.parse(tags); } catch { return []; }
}

const DIETARY_ICONS = {
  'Vegetarian': '🌿',
  'Vegan': '🌱',
  'Gluten-Free': '🚫🌾',
  'Nut-Free': '🚫🥜',
  'Halal': '☪️',
  'Kosher': '✡️',
  'Dairy-Free': '🚫🥛',
  'Spicy': '🌶️',
};

function MenuDesigner({ services, svc, onClose }) {
  const { terminology } = useIndustry();
  const menuRef = useRef(null);
  const designerCfg = svc?.menuDesigner || {};
  const themes = designerCfg.themes || [];
  const defaultTheme = themes.find(t => t.id === designerCfg.defaultTheme) || themes[0] || { id: 'classic', label: 'Classic', fontFamily: 'Georgia, serif', accentColor: '#2c2c2c' };

  // ─── State ───────────────────────────────────────────────────────────────
  const [theme, setTheme] = useState(defaultTheme);
  const [showPrices, setShowPrices] = useState(designerCfg.showPrices !== false);
  const [showDescriptions, setShowDescriptions] = useState(designerCfg.showDescriptions !== false);
  const [showDietaryTags, setShowDietaryTags] = useState(designerCfg.showDietaryTags !== false);
  const [header, setHeader] = useState({
    restaurantName: '',
    tagline: '',
  });
  const [footer, setFooter] = useState({
    allergenNotice: designerCfg.defaultAllergenNotice || '',
    address: '',
    phone: '',
    website: '',
  });
  // Track which categories are included (all by default)
  const grouped = useMemo(() => groupByCategory(services), [services]);
  const allCategories = useMemo(() => Object.keys(grouped), [grouped]);
  const [includedCategories, setIncludedCategories] = useState(() => new Set(Object.keys(groupByCategory(services))));
  // Track individually excluded items
  const [excludedItems, setExcludedItems] = useState(new Set());

  const toggleCategory = (cat) => {
    setIncludedCategories(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat); else next.add(cat);
      return next;
    });
  };

  const toggleItem = (id) => {
    setExcludedItems(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  // ─── Filtered menu data ──────────────────────────────────────────────────
  const menuData = useMemo(() => {
    const result = {};
    for (const [cat, items] of Object.entries(grouped)) {
      if (!includedCategories.has(cat)) continue;
      const filtered = items.filter(i => !excludedItems.has(i.id));
      if (filtered.length > 0) result[cat] = filtered;
    }
    return result;
  }, [grouped, includedCategories, excludedItems]);

  // ─── PDF Export (browser print) ──────────────────────────────────────────
  const handleDownloadPDF = useCallback(() => {
    const printWindow = window.open('', '_blank');
    if (!printWindow) return;

    const menuHTML = menuRef.current?.innerHTML || '';
    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Menu - ${header.restaurantName || 'Restaurant'}</title>
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Inter:wght@400;500;600&display=swap');
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body { font-family: ${theme.fontFamily}; color: ${theme.accentColor}; padding: 2rem; }
          .menu-preview { max-width: 800px; margin: 0 auto; }
          .menu-header { text-align: center; margin-bottom: 2rem; padding-bottom: 1.5rem; border-bottom: 2px solid ${theme.accentColor}20; }
          .menu-header h1 { font-size: 2.2rem; margin-bottom: 0.3rem; letter-spacing: 0.05em; }
          .menu-header .tagline { font-style: italic; opacity: 0.7; font-size: 1.1rem; }
          .menu-category { margin-bottom: 1.8rem; }
          .menu-category h2 { font-size: 1.3rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.8rem; padding-bottom: 0.4rem; border-bottom: 1px solid ${theme.accentColor}30; }
          .menu-item { display: flex; justify-content: space-between; align-items: baseline; padding: 0.4rem 0; }
          .menu-item-left { flex: 1; }
          .menu-item-name { font-weight: 600; font-size: 1rem; }
          .menu-item-desc { font-size: 0.85rem; opacity: 0.65; margin-top: 0.15rem; }
          .menu-item-tags { display: flex; gap: 0.3rem; margin-top: 0.15rem; flex-wrap: wrap; }
          .menu-item-tag { font-size: 0.75rem; opacity: 0.6; }
          .menu-item-price { font-weight: 600; white-space: nowrap; margin-left: 1rem; }
          .menu-item-dots { flex: 1; border-bottom: 1px dotted ${theme.accentColor}25; margin: 0 0.5rem; min-width: 2rem; align-self: end; margin-bottom: 0.3rem; }
          .menu-footer { margin-top: 2rem; padding-top: 1rem; border-top: 2px solid ${theme.accentColor}20; text-align: center; font-size: 0.85rem; opacity: 0.6; }
          .menu-footer p { margin-bottom: 0.3rem; }
          @media print { body { padding: 1cm; } }
        </style>
      </head>
      <body>${menuHTML}</body>
      </html>
    `);
    printWindow.document.close();
    setTimeout(() => { printWindow.print(); }, 500);
  }, [header, theme, menuRef]);

  return (
    <div className="menu-designer-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="menu-designer-modal">
        <div className="menu-designer-header">
          <h2><i className="fas fa-utensils"></i> Menu Designer</h2>
          <button className="btn-close" onClick={onClose}><i className="fas fa-times"></i></button>
        </div>

        <div className="menu-designer-body">
          {/* ─── Left: Controls ─────────────────────────────────────── */}
          <div className="menu-designer-controls">
            {/* Theme */}
            <div className="md-section">
              <h3>Theme</h3>
              <div className="md-theme-grid">
                {themes.map(t => (
                  <button
                    key={t.id}
                    className={`md-theme-btn ${theme.id === t.id ? 'active' : ''}`}
                    onClick={() => setTheme(t)}
                    style={{ fontFamily: t.fontFamily, borderColor: t.accentColor }}
                  >
                    <span className="md-theme-swatch" style={{ background: t.accentColor }}></span>
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Header fields */}
            <div className="md-section">
              <h3>Header</h3>
              <input type="text" placeholder="Restaurant Name" value={header.restaurantName} onChange={e => setHeader({ ...header, restaurantName: e.target.value })} className="md-input" />
              <input type="text" placeholder="Tagline (e.g., Est. 2010 · Italian Cuisine)" value={header.tagline} onChange={e => setHeader({ ...header, tagline: e.target.value })} className="md-input" />
            </div>

            {/* Display options */}
            <div className="md-section">
              <h3>Display</h3>
              <label className="md-toggle"><input type="checkbox" checked={showPrices} onChange={() => setShowPrices(!showPrices)} /> Show prices</label>
              <label className="md-toggle"><input type="checkbox" checked={showDescriptions} onChange={() => setShowDescriptions(!showDescriptions)} /> Show descriptions</label>
              <label className="md-toggle"><input type="checkbox" checked={showDietaryTags} onChange={() => setShowDietaryTags(!showDietaryTags)} /> Show dietary tags</label>
            </div>

            {/* Categories */}
            <div className="md-section">
              <h3>Categories</h3>
              <div className="md-cat-list">
                {allCategories.map(cat => (
                  <label key={cat} className="md-toggle">
                    <input type="checkbox" checked={includedCategories.has(cat)} onChange={() => toggleCategory(cat)} />
                    {cat} <span className="md-cat-count">({grouped[cat].length})</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Footer */}
            <div className="md-section">
              <h3>Footer</h3>
              <input type="text" placeholder="Address" value={footer.address} onChange={e => setFooter({ ...footer, address: e.target.value })} className="md-input" />
              <input type="text" placeholder="Phone" value={footer.phone} onChange={e => setFooter({ ...footer, phone: e.target.value })} className="md-input" />
              <input type="text" placeholder="Website" value={footer.website} onChange={e => setFooter({ ...footer, website: e.target.value })} className="md-input" />
              <textarea placeholder="Allergen notice" value={footer.allergenNotice} onChange={e => setFooter({ ...footer, allergenNotice: e.target.value })} className="md-input" rows={2} />
            </div>

            <button className="btn btn-primary md-download-btn" onClick={handleDownloadPDF}>
              <i className="fas fa-file-pdf"></i> Download PDF
            </button>
          </div>

          {/* ─── Right: Live Preview ────────────────────────────────── */}
          <div className="menu-designer-preview" style={{ fontFamily: theme.fontFamily, color: theme.accentColor }}>
            <div className="menu-preview" ref={menuRef}>
              {/* Header */}
              {(header.restaurantName || header.tagline) && (
                <div className="menu-header">
                  {header.restaurantName && <h1>{header.restaurantName}</h1>}
                  {header.tagline && <p className="tagline">{header.tagline}</p>}
                </div>
              )}

              {/* Categories & Items */}
              {Object.entries(menuData).map(([cat, items]) => (
                <div key={cat} className="menu-category">
                  <h2>{cat}</h2>
                  {items.map(item => {
                    const tags = parseTags(item.tags);
                    const dietaryTags = tags.filter(t => DIETARY_ICONS[t]);
                    return (
                      <div key={item.id} className="menu-item">
                        <div className="menu-item-left">
                          <div className="menu-item-name">
                            {item.name}
                            {showDietaryTags && dietaryTags.length > 0 && (
                              <span className="menu-item-tags">
                                {dietaryTags.map(t => (
                                  <span key={t} className="menu-item-tag" title={t}>{DIETARY_ICONS[t]}</span>
                                ))}
                              </span>
                            )}
                          </div>
                          {showDescriptions && item.description && (
                            <div className="menu-item-desc">{item.description}</div>
                          )}
                        </div>
                        {showPrices && <div className="menu-item-dots"></div>}
                        {showPrices && item.price > 0 && (
                          <div className="menu-item-price">
                            €{parseFloat(item.price).toFixed(2)}
                            {item.price_max && parseFloat(item.price_max) > parseFloat(item.price) && (
                              <> – €{parseFloat(item.price_max).toFixed(2)}</>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ))}

              {Object.keys(menuData).length === 0 && (
                <div className="menu-empty">
                  <p>No menu items to display. Add {(terminology.services || 'services').toLowerCase()} with categories to build your menu.</p>
                </div>
              )}

              {/* Footer */}
              {(footer.address || footer.phone || footer.website || footer.allergenNotice) && (
                <div className="menu-footer">
                  {footer.allergenNotice && <p><em>{footer.allergenNotice}</em></p>}
                  {footer.address && <p>{footer.address}</p>}
                  {[footer.phone, footer.website].filter(Boolean).join(' · ') && (
                    <p>{[footer.phone, footer.website].filter(Boolean).join(' · ')}</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MenuDesigner;
