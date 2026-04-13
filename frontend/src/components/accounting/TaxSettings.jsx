import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTaxSettings, updateTaxSettings, getBusinessSettings } from '../../services/api';
import { useToast } from '../Toast';
import LoadingSpinner from '../LoadingSpinner';

function TaxSettings() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [formData, setFormData] = useState({
    tax_rate: 0, tax_id_number: '', tax_id_label: 'VAT',
    invoice_prefix: 'INV', invoice_next_number: 1,
    invoice_payment_terms_days: 14, invoice_footer_note: '',
    default_expense_categories: '',
  });

  const { data: settings, isLoading } = useQuery({
    queryKey: ['tax-settings'],
    queryFn: async () => (await getTaxSettings()).data,
    staleTime: 60000,
  });

  const { data: bizSettings } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => (await getBusinessSettings()).data,
    staleTime: 60000,
  });

  useEffect(() => {
    if (settings) setFormData(prev => ({ ...prev, ...settings }));
  }, [settings]);

  const saveMut = useMutation({
    mutationFn: updateTaxSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tax-settings'] });
      addToast('Tax settings saved', 'success');
    },
    onError: (e) => addToast(e.response?.data?.error || 'Failed to save', 'error'),
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    saveMut.mutate(formData);
  };

  if (isLoading) return <LoadingSpinner message="Loading settings..." />;

  return (
    <div className="acct-panel">
      {/* Panel Header */}
      <div className="acct-panel-header">
        <h2 className="acct-panel-title"><i className="fas fa-cog"></i> Invoice & Tax Settings</h2>
      </div>

      <form className="tax-settings-form" onSubmit={handleSubmit}>
        {/* Business Info on Invoices */}
        {bizSettings && (
          <div className="acct-section">
            <div className="acct-section-header">
              <h3><i className="fas fa-building"></i> Business Info on Invoices</h3>
              <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Edit in Settings → Business tab</span>
            </div>
            <div className="tax-biz-info">
              {bizSettings.logo_url && <img src={bizSettings.logo_url} alt="Logo" className="tax-biz-logo" />}
              <div className="tax-biz-details">
                <div className="tax-biz-name">{bizSettings.company_name || 'Your Business'}</div>
                {bizSettings.address && <div className="tax-biz-line"><i className="fas fa-map-marker-alt"></i> {bizSettings.address}</div>}
                {bizSettings.phone && <div className="tax-biz-line"><i className="fas fa-phone"></i> {bizSettings.phone}</div>}
                {bizSettings.email && <div className="tax-biz-line"><i className="fas fa-envelope"></i> {bizSettings.email}</div>}
                {formData.tax_id_number && <div className="tax-biz-line"><i className="fas fa-id-card"></i> {formData.tax_id_label}: {formData.tax_id_number}</div>}
              </div>
            </div>
          </div>
        )}

        {/* Tax Configuration */}
        <div className="acct-section">
          <div className="acct-section-header">
            <h3><i className="fas fa-percentage"></i> Tax Configuration</h3>
          </div>
          <div className="tax-form-grid">
            <div className="acct-field">
              <label>Tax Rate (%)</label>
              <div className="acct-input-icon">
                <input type="number" step="0.01" min="0" max="100" placeholder="0"
                  value={formData.tax_rate} onChange={e => setFormData({ ...formData, tax_rate: e.target.value })} />
                <span className="acct-input-suffix">%</span>
              </div>
              <span className="acct-field-hint">Applied to invoices and quotes. Set to 0 if not VAT registered.</span>
            </div>
            <div className="acct-field">
              <label>Tax ID Label</label>
              <select value={formData.tax_id_label} onChange={e => setFormData({ ...formData, tax_id_label: e.target.value })}>
                <option value="VAT">VAT</option>
                <option value="GST">GST</option>
                <option value="Tax ID">Tax ID</option>
                <option value="EIN">EIN</option>
                <option value="ABN">ABN</option>
              </select>
            </div>
            <div className="acct-field">
              <label>{formData.tax_id_label} Number</label>
              <input type="text" placeholder={`e.g. IE1234567T`}
                value={formData.tax_id_number} onChange={e => setFormData({ ...formData, tax_id_number: e.target.value })} />
              <span className="acct-field-hint">Displayed on invoices and quotes.</span>
            </div>
          </div>
        </div>

        {/* Invoice Configuration */}
        <div className="acct-section">
          <div className="acct-section-header">
            <h3><i className="fas fa-file-invoice"></i> Invoice Configuration</h3>
          </div>
          <div className="tax-form-grid">
            <div className="acct-field">
              <label>Invoice Prefix</label>
              <input type="text" maxLength={10} placeholder="INV"
                value={formData.invoice_prefix} onChange={e => setFormData({ ...formData, invoice_prefix: e.target.value })} />
              <span className="acct-field-hint">e.g. INV-0001, BILL-0001</span>
            </div>
            <div className="acct-field">
              <label>Next Invoice Number</label>
              <input type="number" min="1" step="1"
                value={formData.invoice_next_number} onChange={e => setFormData({ ...formData, invoice_next_number: e.target.value })} />
            </div>
            <div className="acct-field">
              <label>Payment Terms (days)</label>
              <select value={formData.invoice_payment_terms_days}
                onChange={e => setFormData({ ...formData, invoice_payment_terms_days: e.target.value })}>
                <option value="0">Due on Receipt</option>
                <option value="7">Net 7</option>
                <option value="14">Net 14</option>
                <option value="30">Net 30</option>
                <option value="60">Net 60</option>
              </select>
              <span className="acct-field-hint">Default due date for new invoices.</span>
            </div>
            <div className="acct-field acct-field-wide">
              <label>Invoice Footer Note</label>
              <textarea rows={2} placeholder="e.g. Thank you for your business. Payment is due within 14 days."
                value={formData.invoice_footer_note} onChange={e => setFormData({ ...formData, invoice_footer_note: e.target.value })} />
              <span className="acct-field-hint">Appears at the bottom of every invoice.</span>
            </div>
          </div>
        </div>

        {/* Preview */}
        <div className="acct-section">
          <div className="acct-section-header">
            <h3><i className="fas fa-eye"></i> Invoice Preview</h3>
          </div>
          <div className="tax-invoice-preview">
            <div className="tax-preview-header">
              <div className="tax-preview-title">INVOICE</div>
              <div className="tax-preview-number">{formData.invoice_prefix}-{String(formData.invoice_next_number).padStart(4, '0')}</div>
            </div>
            <div className="tax-preview-body">
              <div className="tax-preview-row">
                <span>Subtotal</span><span>€100.00</span>
              </div>
              {parseFloat(formData.tax_rate) > 0 && (
                <div className="tax-preview-row">
                  <span>{formData.tax_id_label} ({formData.tax_rate}%)</span>
                  <span>€{(100 * parseFloat(formData.tax_rate) / 100).toFixed(2)}</span>
                </div>
              )}
              <div className="tax-preview-row tax-preview-total">
                <span>Total</span>
                <span>€{(100 + 100 * parseFloat(formData.tax_rate || 0) / 100).toFixed(2)}</span>
              </div>
              {formData.tax_id_number && (
                <div className="tax-preview-meta">{formData.tax_id_label}: {formData.tax_id_number}</div>
              )}
              <div className="tax-preview-meta">
                Payment Terms: {formData.invoice_payment_terms_days == 0 ? 'Due on Receipt' : `Net ${formData.invoice_payment_terms_days}`}
              </div>
              {formData.invoice_footer_note && (
                <div className="tax-preview-footer">{formData.invoice_footer_note}</div>
              )}
            </div>
          </div>
        </div>

        <div className="acct-form-actions">
          <button type="submit" className="acct-btn-primary" disabled={saveMut.isPending}>
            <i className={`fas ${saveMut.isPending ? 'fa-spinner fa-spin' : 'fa-save'}`}></i>
            Save Settings
          </button>
        </div>
      </form>
    </div>
  );
}

export default TaxSettings;
