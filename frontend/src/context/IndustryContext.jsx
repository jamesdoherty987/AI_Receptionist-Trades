/**
 * IndustryContext — Provides industry profile (terminology, features, tabs, icons)
 * to the entire app via React context.
 *
 * Auth-aware: works for admins, employees, and unauthenticated users (falls back safely).
 *
 * Usage in any component:
 *   import { useIndustry } from '../context/IndustryContext';
 *   const { terminology, features, tabs, icons, industryType } = useIndustry();
 *   <h2>{terminology.jobs}</h2>  // "Jobs" or "Appointments" depending on industry
 *
 * Data sources (in priority order):
 *   1. Employee login    → uses industry_profile from AuthContext user object
 *   2. Admin login     → fetches /api/settings/business (cached)
 *   3. Not logged in   → uses default 'trades' profile
 *
 * Customer portal does NOT use this context — it builds its own terminology
 * from the data returned by /api/portal/<token> directly.
 */
import { createContext, useContext, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getBusinessSettings } from '../services/api';
import { useAuth } from './AuthContext';
import industryProfiles from '../config/industryProfiles';

const IndustryContext = createContext(null);

// Normalise a backend industry_profile object (snake_case) into frontend shape (camelCase)
function normaliseBackendProfile(backendProfile, localProfile, availableIndustries = []) {
  if (!backendProfile) return null;
  const features = backendProfile.features || {};
  return {
    label: backendProfile.label || localProfile.label,
    terminology: backendProfile.terminology || localProfile.terminology,
    features: {
      materials: features.materials ?? localProfile.features.materials,
      callouts: features.callouts ?? localProfile.features.callouts,
      quotes: features.quotes ?? localProfile.features.quotes,
      emergencyJobs: features.emergency_jobs ?? localProfile.features.emergencyJobs,
      propertyType: features.property_type ?? localProfile.features.propertyType,
      jobAddress: features.job_address ?? localProfile.features.jobAddress,
      jobPhotos: features.job_photos ?? localProfile.features.jobPhotos,
      multiDayJobs: features.multi_day_jobs ?? localProfile.features.multiDayJobs,
    },
    tabs: localProfile.tabs,   // Tab visibility is frontend-only config (uses 'inventory' key)
    icons: localProfile.icons,
    onboarding: {
      employeeIcon: backendProfile.onboarding?.employee_icon || localProfile.onboarding.employeeIcon,
      employeeLabel: backendProfile.onboarding?.employee_label || localProfile.onboarding.employeeLabel,
      showMaterialsStep: backendProfile.onboarding?.show_materials_step ?? localProfile.onboarding.showMaterialsStep,
      companyContextPlaceholder: backendProfile.onboarding?.company_context_placeholder || localProfile.onboarding.companyContextPlaceholder,
    },
    availableIndustries,
  };
}

// Resolve the active profile based on available data
function resolveProfile({ settings, employeeUser }) {
  // Priority 1: Employee session — use their company's industry from auth endpoint
  if (employeeUser?.role === 'employee' && employeeUser?.industry_profile) {
    const industryType = employeeUser.industry_type || 'trades';
    const localProfile = industryProfiles[industryType] || industryProfiles.trades;
    const normalized = normaliseBackendProfile(employeeUser.industry_profile, localProfile, []);
    return { industryType, ...normalized };
  }

  // Priority 2: Admin session — use settings from /api/settings/business
  const backendProfile = settings?.industry_profile;
  const industryType = settings?.industry_type || 'trades';
  const localProfile = industryProfiles[industryType] || industryProfiles.trades;

  if (backendProfile) {
    const normalized = normaliseBackendProfile(
      backendProfile,
      localProfile,
      settings?.available_industries || []
    );
    return { industryType, ...normalized };
  }

  // Priority 3: Not logged in or no settings yet — use local fallback
  return {
    industryType,
    ...localProfile,
    availableIndustries: [],
  };
}

export function IndustryProvider({ children }) {
  const { user, isAuthenticated, isEmployee } = useAuth();

  // Only fetch admin settings when the user is a logged-in admin.
  // Employees get their industry from the auth response, not from settings.
  const shouldFetchAdminSettings = isAuthenticated && !isEmployee;

  const { data: settings } = useQuery({
    queryKey: ['business-settings'],
    queryFn: async () => {
      const response = await getBusinessSettings();
      return response.data;
    },
    enabled: shouldFetchAdminSettings,
    staleTime: 5 * 60 * 1000, // 5 min — industry rarely changes
  });

  const profile = useMemo(
    () => resolveProfile({ settings, employeeUser: isEmployee ? user : null }),
    [settings, user, isEmployee]
  );

  return (
    <IndustryContext.Provider value={profile}>
      {children}
    </IndustryContext.Provider>
  );
}

export function useIndustry() {
  const ctx = useContext(IndustryContext);
  if (!ctx) {
    // Safety fallback — shouldn't happen if provider is mounted above
    return resolveProfile({ settings: null, employeeUser: null });
  }
  return ctx;
}

export default IndustryContext;
