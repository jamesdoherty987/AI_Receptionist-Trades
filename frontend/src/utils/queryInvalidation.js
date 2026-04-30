/**
 * Centralized query invalidation helper.
 *
 * Instead of each mutation manually listing every queryKey it might affect,
 * mutations call `invalidateRelated(queryClient, ...domains)` with one or more
 * domain names. Each domain maps to a set of query keys that should be
 * refreshed together.
 *
 * This eliminates the class of bugs where a mutation in one component forgets
 * to invalidate a cache that another component depends on.
 */

// Domain → query keys that should be invalidated together.
// A domain can also reference other domains via the `also` array to create
// cascading invalidations (e.g. changing a job also affects finances).
const DOMAINS = {
  // Core business data shown on the main dashboard
  dashboard: {
    keys: ['dashboard'],
  },

  // Customer / client data — CRM tab, customer health, client lists
  customers: {
    keys: ['clients', 'crm-stats', 'dashboard'],
  },

  // Jobs / bookings
  jobs: {
    keys: ['dashboard', 'bookings', 'crm-stats'],
  },

  // Employee data
  employees: {
    keys: ['dashboard', 'employees'],
  },

  // Employee dashboard (separate app for employees)
  employeeDashboard: {
    keys: ['employee-dashboard', 'employee-notifications'],
  },

  // Leads / pipeline in CRM
  leads: {
    keys: ['leads', 'crm-stats', 'dashboard'],
  },

  // Finances — invoices, payments, revenue
  finances: {
    keys: ['finances', 'dashboard', 'bookings', 'invoice-aging', 'revenue-entries', 'pnl-report'],
  },

  // Quotes / proposals
  quotes: {
    keys: ['quotes', 'quote-pipeline', 'dashboard'],
  },

  // Services menu
  services: {
    keys: ['services-menu', 'dashboard'],
  },

  // Packages
  packages: {
    keys: ['packages'],
  },

  // Materials / inventory
  materials: {
    keys: ['materials'],
  },

  // Expenses
  expenses: {
    keys: ['expenses', 'pnl-report', 'finances'],
  },

  // Credit notes / refunds
  creditNotes: {
    keys: ['credit-notes', 'finances', 'bookings', 'invoice-aging', 'pnl-report', 'dashboard'],
  },

  // Reviews
  reviews: {
    keys: ['reviews', 'crm-stats'],
  },

  // Employee messages
  messages: {
    keys: ['unread-message-counts'],
  },

  // Waitlist (restaurant / salon)
  waitlist: {
    keys: ['waitlist'],
  },

  // Business settings
  settings: {
    keys: ['business-settings'],
  },

  // Calendar / scheduling
  calendar: {
    keys: ['availability', 'monthly-availability'],
  },
};

/**
 * Invalidate all query keys associated with the given domains.
 *
 * @param {import('@tanstack/react-query').QueryClient} queryClient
 * @param {...string} domains - One or more domain names from DOMAINS above.
 *
 * @example
 *   // After deleting a customer:
 *   invalidateRelated(queryClient, 'customers');
 *
 *   // After creating a job (affects jobs, calendar, finances):
 *   invalidateRelated(queryClient, 'jobs', 'calendar', 'finances');
 */
export function invalidateRelated(queryClient, ...domains) {
  const seen = new Set();
  for (const domain of domains) {
    const entry = DOMAINS[domain];
    if (!entry) {
      console.warn(`[invalidateRelated] Unknown domain: "${domain}"`);
      continue;
    }
    for (const key of entry.keys) {
      if (!seen.has(key)) {
        seen.add(key);
        queryClient.invalidateQueries({ queryKey: [key] });
      }
    }
  }
}

export default invalidateRelated;
