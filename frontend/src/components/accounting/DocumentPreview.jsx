import { useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { formatCurrency, formatDate } from '../../utils/helpers';
import { getBusinessSettings, getTaxSettings } from '../../services/api';
import './Accounting.css';

function DocumentPreview({ type = 'invoice', docNumber, date, dueDate, customer, supplier,
  lineItems = [], subtotal, taxRate: propTaxRate, taxAmount: propTaxAmount, total,
  notes, status, onClose, inline = false }) {

  const paperRef = useRef(null);

  const { data: biz } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => (await getBusinessSettings()).data,
    staleTime: 60000,
  });

  const { data: tax } = useQuery({
    queryKey: ['tax-settings'],
    queryFn: async () => (await getTaxSettings()).data,
    staleTime: 60000,
  });

  const companyName = biz?.business_name || '';
  const companyAddress = biz?.address || '';
  const companyPhone = biz?.phone || '';
  const companyEmail = biz?.email || '';
  const logoUrl = biz?.logo_url || '';
  const taxIdLabel = tax?.tax_id_label || 'VAT';
  const taxIdNumber = tax?.tax_id_number || '';
  const taxRate = propTaxRate ?? (tax?.tax_rate || 0);
  const footerNote = tax?.invoice_footer_note || '';
  const paymentTerms = parseInt(tax?.invoice_payment_terms_days || 14);

  const calcSubtotal = subtotal ?? lineItems.reduce((s, i) => s + (parseFloat(i.amount) || 0) * (parseFloat(i.quantity) || 1), 0);
  const calcTaxAmount = propTaxAmount ?? Math.round(calcSubtotal * parseFloat(taxRate) / 100 * 100) / 100;
  const calcTotal = total ?? (calcSubtotal + calcTaxAmount);

  const typeLabels = { 'invoice': 'INVOICE', 'quote': 'QUOTE', 'purchase-order': 'PURCHASE ORDER', 'credit-note': 'CREDIT NOTE' };
  const typeColors = { 'invoice': '#6366f1', 'quote': '#3b82f6', 'purchase-order': '#f59e0b', 'credit-note': '#ef4444' };
  const color = typeColors[type] || '#6366f1';

  const handleDownloadPDF = () => {
    const el = paperRef.current;
    if (!el) return;
    const printWindow = window.open('', '_blank');
    if (!printWindow) return;
    printWindow.document.write(`<!DOCTYPE html><html><head><title>${typeLabels[type] || 'Document'} ${docNumber || ''}</title>
<style>
  @page { size: A4; margin: 0; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Georgia', 'Times New Roman', 'Garamond', serif; color: #1e293b; }
  .a4-page { width: 210mm; min-height: 297mm; padding: 20mm 18mm; }
  .doc-hdr { display: flex; justify-content: space-between; align-items: flex-start; padding-bottom: 16px; margin-bottom: 20px; border-bottom: 3px solid ${color}; }
  .doc-logo { width: 56px; height: 56px; border-radius: 8px; object-fit: contain; margin-right: 12px; }
  .doc-co { display: flex; align-items: flex-start; }
  .doc-co-name { font-size: 16px; font-weight: 700; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
  .doc-co-detail { font-size: 10px; color: #64748b; margin-top: 2px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
  .doc-title-block { text-align: right; }
  .doc-type { font-size: 24px; font-weight: 800; letter-spacing: 0.12em; color: ${color}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
  .doc-num { font-size: 12px; font-weight: 600; color: #475569; margin-top: 2px; }
  .doc-date { font-size: 10px; color: #94a3b8; margin-top: 1px; }
  .doc-status { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 9px; font-weight: 600; text-transform: uppercase; background: ${color}18; color: ${color}; margin-top: 6px; }
  .doc-parties { display: flex; gap: 40px; margin-bottom: 20px; }
  .doc-party-label { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; margin-bottom: 3px; }
  .doc-party-name { font-size: 13px; font-weight: 600; }
  .doc-party-detail { font-size: 10px; color: #64748b; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
  th { padding: 8px 10px; text-align: left; font-size: 9px; font-weight: 700; text-transform: uppercase; color: #64748b; border-bottom: 2px solid #e2e8f0; background: #f8fafc; }
  td { padding: 9px 10px; font-size: 11px; color: #374151; border-bottom: 1px solid #f1f5f9; }
  .txt-r { text-align: right; }
  .txt-c { text-align: center; }
  .totals { display: flex; flex-direction: column; align-items: flex-end; margin-bottom: 16px; }
  .total-row { display: flex; justify-content: space-between; width: 200px; font-size: 11px; color: #64748b; padding: 3px 0; }
  .grand-total { font-size: 14px; font-weight: 700; color: #1e293b; padding-top: 8px; border-top: 2px solid ${color}; margin-top: 4px; }
  .grand-total span:last-child { color: ${color}; }
  .terms { font-size: 9px; color: #94a3b8; margin-bottom: 8px; }
  .notes { font-size: 10px; color: #475569; padding: 8px; background: #f8fafc; border-radius: 4px; margin-bottom: 12px; }
  .footer { font-size: 9px; color: #64748b; font-style: italic; padding-top: 12px; border-top: 1px dashed #e2e8f0; }
</style></head><body>`);
    printWindow.document.write(`<div class="a4-page">`);
    // Header
    printWindow.document.write(`<div class="doc-hdr"><div class="doc-co">`);
    if (logoUrl) printWindow.document.write(`<img class="doc-logo" src="${logoUrl}" />`);
    printWindow.document.write(`<div><div class="doc-co-name">${companyName || 'Your Company'}</div>`);
    if (companyAddress) printWindow.document.write(`<div class="doc-co-detail">${companyAddress}</div>`);
    if (companyPhone) printWindow.document.write(`<div class="doc-co-detail">${companyPhone}</div>`);
    if (companyEmail) printWindow.document.write(`<div class="doc-co-detail">${companyEmail}</div>`);
    if (taxIdNumber) printWindow.document.write(`<div class="doc-co-detail">${taxIdLabel}: ${taxIdNumber}</div>`);
    printWindow.document.write(`</div></div><div class="doc-title-block">`);
    printWindow.document.write(`<div class="doc-type">${typeLabels[type] || 'DOCUMENT'}</div>`);
    if (docNumber) printWindow.document.write(`<div class="doc-num">${docNumber}</div>`);
    printWindow.document.write(`<div class="doc-date">Date: ${formatDate(date || new Date().toISOString())}</div>`);
    if (dueDate) printWindow.document.write(`<div class="doc-date">Due: ${formatDate(dueDate)}</div>`);
    if (status) printWindow.document.write(`<div class="doc-status">${status}</div>`);
    printWindow.document.write(`</div></div>`);
    // Parties
    if (customer || supplier) {
      printWindow.document.write(`<div class="doc-parties">`);
      if (customer) {
        printWindow.document.write(`<div><div class="doc-party-label">${type === 'credit-note' ? 'Credit To' : 'Bill To'}</div>`);
        printWindow.document.write(`<div class="doc-party-name">${customer.name || ''}</div>`);
        if (customer.address) printWindow.document.write(`<div class="doc-party-detail">${customer.address}</div>`);
        if (customer.phone) printWindow.document.write(`<div class="doc-party-detail">${customer.phone}</div>`);
        if (customer.email) printWindow.document.write(`<div class="doc-party-detail">${customer.email}</div>`);
        printWindow.document.write(`</div>`);
      }
      if (supplier) printWindow.document.write(`<div><div class="doc-party-label">Supplier</div><div class="doc-party-name">${supplier}</div></div>`);
      printWindow.document.write(`</div>`);
    }
    // Table
    if (lineItems.length > 0) {
      printWindow.document.write(`<table><thead><tr><th>Description</th><th class="txt-c" style="width:60px">Qty</th><th class="txt-r" style="width:90px">Price</th><th class="txt-r" style="width:90px">Total</th></tr></thead><tbody>`);
      lineItems.forEach(item => {
        const qty = parseFloat(item.quantity) || 1;
        const price = parseFloat(item.amount || item.unit_price) || 0;
        printWindow.document.write(`<tr><td>${item.description || item.name || ''}</td><td class="txt-c">${qty}</td><td class="txt-r">${formatCurrency(price)}</td><td class="txt-r">${formatCurrency(price * qty)}</td></tr>`);
      });
      printWindow.document.write(`</tbody></table>`);
    }
    // Totals
    printWindow.document.write(`<div class="totals"><div class="total-row"><span>Subtotal</span><span>${formatCurrency(calcSubtotal)}</span></div>`);
    if (parseFloat(taxRate) > 0) printWindow.document.write(`<div class="total-row"><span>${taxIdLabel} (${taxRate}%)</span><span>${formatCurrency(calcTaxAmount)}</span></div>`);
    printWindow.document.write(`<div class="total-row grand-total"><span>${type === 'credit-note' ? 'Credit Total' : 'Total Due'}</span><span>${formatCurrency(calcTotal)}</span></div></div>`);
    // Footer
    if (type !== 'credit-note' && type !== 'purchase-order') printWindow.document.write(`<div class="terms">Payment Terms: ${paymentTerms === 0 ? 'Due on Receipt' : `Net ${paymentTerms} days`}</div>`);
    if (notes) printWindow.document.write(`<div class="notes">${notes}</div>`);
    if (footerNote && type !== 'purchase-order') printWindow.document.write(`<div class="footer">${footerNote}</div>`);
    printWindow.document.write(`</div></body></html>`);
    printWindow.document.close();
    setTimeout(() => { printWindow.print(); }, 300);
  };

  // Inline mode: render just the paper without overlay
  if (inline) {
    return (
      <div className="doc-preview-inline-wrap">
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.5rem' }}>
          <button className="doc-action-btn" onClick={handleDownloadPDF} title="Download / Print PDF">
            <i className="fas fa-download"></i> Download PDF
          </button>
        </div>
        <div className="doc-preview-paper" ref={paperRef} style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
          <div className="doc-preview-header" style={{ borderBottomColor: color }}>
            <div className="doc-preview-company">
              {logoUrl && <img src={logoUrl} alt="Logo" className="doc-preview-logo" />}
              <div>
                <div className="doc-preview-company-name">{companyName || 'Your Company'}</div>
                {companyAddress && <div className="doc-preview-company-detail">{companyAddress}</div>}
                {companyPhone && <div className="doc-preview-company-detail">{companyPhone}</div>}
                {companyEmail && <div className="doc-preview-company-detail">{companyEmail}</div>}
                {taxIdNumber && <div className="doc-preview-company-detail">{taxIdLabel}: {taxIdNumber}</div>}
              </div>
            </div>
            <div className="doc-preview-title-block">
              <div className="doc-preview-type" style={{ color }}>{typeLabels[type] || 'DOCUMENT'}</div>
              {docNumber && <div className="doc-preview-number">{docNumber}</div>}
              <div className="doc-preview-date">Date: {formatDate(date || new Date().toISOString())}</div>
              {dueDate && <div className="doc-preview-date">Due: {formatDate(dueDate)}</div>}
              {status && <div className="doc-preview-status" style={{ background: `${color}15`, color }}>{status}</div>}
            </div>
          </div>
          {(customer || supplier) && (
            <div className="doc-preview-parties">
              {customer && (
                <div className="doc-preview-party">
                  <div className="doc-preview-party-label">{type === 'credit-note' ? 'Credit To' : 'Bill To'}</div>
                  <div className="doc-preview-party-name">{customer.name || ''}</div>
                  {customer.address && <div className="doc-preview-party-detail">{customer.address}</div>}
                  {customer.phone && <div className="doc-preview-party-detail">{customer.phone}</div>}
                  {customer.email && <div className="doc-preview-party-detail">{customer.email}</div>}
                </div>
              )}
              {supplier && (
                <div className="doc-preview-party">
                  <div className="doc-preview-party-label">Supplier</div>
                  <div className="doc-preview-party-name">{supplier}</div>
                </div>
              )}
            </div>
          )}
          {lineItems.length > 0 && (
            <table className="doc-preview-table">
              <thead><tr><th>Description</th><th style={{ textAlign: 'center', width: 60 }}>Qty</th><th style={{ textAlign: 'right', width: 100 }}>Price</th><th style={{ textAlign: 'right', width: 100 }}>Total</th></tr></thead>
              <tbody>
                {lineItems.map((item, i) => {
                  const qty = parseFloat(item.quantity) || 1;
                  const price = parseFloat(item.amount || item.unit_price) || 0;
                  return (<tr key={i}><td>{item.description || item.name || ''}</td><td style={{ textAlign: 'center' }}>{qty}</td><td style={{ textAlign: 'right' }}>{formatCurrency(price)}</td><td style={{ textAlign: 'right' }}>{formatCurrency(price * qty)}</td></tr>);
                })}
              </tbody>
            </table>
          )}
          <div className="doc-preview-totals">
            <div className="doc-preview-total-row"><span>Subtotal</span><span>{formatCurrency(calcSubtotal)}</span></div>
            {parseFloat(taxRate) > 0 && (<div className="doc-preview-total-row"><span>{taxIdLabel} ({taxRate}%)</span><span>{formatCurrency(calcTaxAmount)}</span></div>)}
            <div className="doc-preview-total-row doc-preview-grand-total" style={{ borderTopColor: color }}>
              <span>{type === 'credit-note' ? 'Credit Total' : 'Total Due'}</span>
              <span style={{ color }}>{formatCurrency(calcTotal)}</span>
            </div>
          </div>
          {type !== 'credit-note' && type !== 'purchase-order' && (<div className="doc-preview-terms">Payment Terms: {paymentTerms === 0 ? 'Due on Receipt' : `Net ${paymentTerms} days`}</div>)}
          {notes && <div className="doc-preview-notes">{notes}</div>}
          {footerNote && type !== 'purchase-order' && (<div className="doc-preview-footer">{footerNote}</div>)}
        </div>
      </div>
    );
  }

  return (
    <div className="doc-preview-overlay" onClick={onClose}>
      <div className="doc-preview-modal" onClick={e => e.stopPropagation()}>
        <div className="doc-preview-actions">
          <button className="doc-action-btn" onClick={handleDownloadPDF} title="Download / Print PDF">
            <i className="fas fa-download"></i> Download PDF
          </button>
          <button className="doc-preview-close" onClick={onClose}>
            <i className="fas fa-times"></i>
          </button>
        </div>

        <div className="doc-preview-paper" ref={paperRef}>
          {/* Header */}
          <div className="doc-preview-header" style={{ borderBottomColor: color }}>
            <div className="doc-preview-company">
              {logoUrl && <img src={logoUrl} alt="Logo" className="doc-preview-logo" />}
              <div>
                <div className="doc-preview-company-name">{companyName || 'Your Company'}</div>
                {companyAddress && <div className="doc-preview-company-detail">{companyAddress}</div>}
                {companyPhone && <div className="doc-preview-company-detail">{companyPhone}</div>}
                {companyEmail && <div className="doc-preview-company-detail">{companyEmail}</div>}
                {taxIdNumber && <div className="doc-preview-company-detail">{taxIdLabel}: {taxIdNumber}</div>}
              </div>
            </div>
            <div className="doc-preview-title-block">
              <div className="doc-preview-type" style={{ color }}>{typeLabels[type] || 'DOCUMENT'}</div>
              {docNumber && <div className="doc-preview-number">{docNumber}</div>}
              <div className="doc-preview-date">Date: {formatDate(date || new Date().toISOString())}</div>
              {dueDate && <div className="doc-preview-date">Due: {formatDate(dueDate)}</div>}
              {status && <div className="doc-preview-status" style={{ background: `${color}15`, color }}>{status}</div>}
            </div>
          </div>

          {/* Parties */}
          {(customer || supplier) && (
            <div className="doc-preview-parties">
              {customer && (
                <div className="doc-preview-party">
                  <div className="doc-preview-party-label">{type === 'credit-note' ? 'Credit To' : 'Bill To'}</div>
                  <div className="doc-preview-party-name">{customer.name || ''}</div>
                  {customer.address && <div className="doc-preview-party-detail">{customer.address}</div>}
                  {customer.phone && <div className="doc-preview-party-detail">{customer.phone}</div>}
                  {customer.email && <div className="doc-preview-party-detail">{customer.email}</div>}
                </div>
              )}
              {supplier && (
                <div className="doc-preview-party">
                  <div className="doc-preview-party-label">Supplier</div>
                  <div className="doc-preview-party-name">{supplier}</div>
                </div>
              )}
            </div>
          )}

          {/* Line Items */}
          {lineItems.length > 0 && (
            <table className="doc-preview-table">
              <thead>
                <tr>
                  <th>Description</th>
                  <th style={{ textAlign: 'center', width: 60 }}>Qty</th>
                  <th style={{ textAlign: 'right', width: 100 }}>Price</th>
                  <th style={{ textAlign: 'right', width: 100 }}>Total</th>
                </tr>
              </thead>
              <tbody>
                {lineItems.map((item, i) => {
                  const qty = parseFloat(item.quantity) || 1;
                  const price = parseFloat(item.amount || item.unit_price) || 0;
                  return (
                    <tr key={i}>
                      <td>{item.description || item.name || ''}</td>
                      <td style={{ textAlign: 'center' }}>{qty}</td>
                      <td style={{ textAlign: 'right' }}>{formatCurrency(price)}</td>
                      <td style={{ textAlign: 'right' }}>{formatCurrency(price * qty)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          {/* Totals */}
          <div className="doc-preview-totals">
            <div className="doc-preview-total-row">
              <span>Subtotal</span><span>{formatCurrency(calcSubtotal)}</span>
            </div>
            {parseFloat(taxRate) > 0 && (
              <div className="doc-preview-total-row">
                <span>{taxIdLabel} ({taxRate}%)</span><span>{formatCurrency(calcTaxAmount)}</span>
              </div>
            )}
            <div className="doc-preview-total-row doc-preview-grand-total" style={{ borderTopColor: color }}>
              <span>{type === 'credit-note' ? 'Credit Total' : 'Total Due'}</span>
              <span style={{ color }}>{formatCurrency(calcTotal)}</span>
            </div>
          </div>

          {type !== 'credit-note' && type !== 'purchase-order' && (
            <div className="doc-preview-terms">
              Payment Terms: {paymentTerms === 0 ? 'Due on Receipt' : `Net ${paymentTerms} days`}
            </div>
          )}
          {notes && <div className="doc-preview-notes">{notes}</div>}
          {footerNote && type !== 'purchase-order' && (
            <div className="doc-preview-footer">{footerNote}</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default DocumentPreview;
