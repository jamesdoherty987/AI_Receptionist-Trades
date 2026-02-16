/**
 * Comprehensive duration options for services and jobs
 * Ranges from 30 minutes to 4 weeks
 */

// Duration options in minutes with human-readable labels
export const DURATION_OPTIONS = [
  // 30 min increments up to 8 hours
  { value: 30, label: '30 mins' },
  { value: 60, label: '1 hour' },
  { value: 90, label: '1.5 hours' },
  { value: 120, label: '2 hours' },
  { value: 150, label: '2.5 hours' },
  { value: 180, label: '3 hours' },
  { value: 210, label: '3.5 hours' },
  { value: 240, label: '4 hours' },
  { value: 270, label: '4.5 hours' },
  { value: 300, label: '5 hours' },
  { value: 330, label: '5.5 hours' },
  { value: 360, label: '6 hours' },
  { value: 390, label: '6.5 hours' },
  { value: 420, label: '7 hours' },
  { value: 450, label: '7.5 hours' },
  { value: 480, label: '8 hours' },
  // Days (1-7 days)
  { value: 1440, label: '1 day' },
  { value: 2880, label: '2 days' },
  { value: 4320, label: '3 days' },
  { value: 5760, label: '4 days' },
  { value: 7200, label: '5 days' },
  { value: 8640, label: '6 days' },
  { value: 10080, label: '1 week' },
  // Weeks (2-4 weeks)
  { value: 20160, label: '2 weeks' },
  { value: 30240, label: '3 weeks' },
  { value: 40320, label: '4 weeks (1 month)' },
];

/**
 * Format duration in minutes to human-readable string
 * @param {number} minutes - Duration in minutes
 * @returns {string} Human-readable duration
 */
export const formatDuration = (minutes) => {
  if (!minutes || minutes <= 0) return '';
  
  // Find exact match in options
  const option = DURATION_OPTIONS.find(opt => opt.value === minutes);
  if (option) return option.label;
  
  // Calculate for non-standard durations
  const weeks = Math.floor(minutes / 10080);
  const days = Math.floor((minutes % 10080) / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const mins = minutes % 60;
  
  const parts = [];
  if (weeks > 0) parts.push(`${weeks} week${weeks > 1 ? 's' : ''}`);
  if (days > 0) parts.push(`${days} day${days > 1 ? 's' : ''}`);
  if (hours > 0) parts.push(`${hours} hour${hours > 1 ? 's' : ''}`);
  if (mins > 0) parts.push(`${mins} min${mins > 1 ? 's' : ''}`);
  
  return parts.join(' ') || '0 mins';
};

/**
 * Get short duration label for display in compact spaces
 * @param {number} minutes - Duration in minutes
 * @returns {string} Short duration label
 */
export const formatDurationShort = (minutes) => {
  if (!minutes || minutes <= 0) return '';
  
  if (minutes >= 10080) {
    const weeks = Math.round(minutes / 10080);
    return `${weeks}w`;
  }
  if (minutes >= 1440) {
    const days = Math.round(minutes / 1440);
    return `${days}d`;
  }
  if (minutes >= 60) {
    const hours = minutes / 60;
    return hours % 1 === 0 ? `${hours}h` : `${hours.toFixed(1)}h`;
  }
  return `${minutes}m`;
};

/**
 * Check if duration is a multi-day job
 * @param {number} minutes - Duration in minutes
 * @returns {boolean} True if duration is 1 day or more
 */
export const isMultiDayDuration = (minutes) => {
  return minutes >= 1440; // 24 hours = 1440 minutes
};

/**
 * Get duration category for grouping in select dropdowns
 * @param {number} minutes - Duration in minutes
 * @returns {string} Category name
 */
export const getDurationCategory = (minutes) => {
  if (minutes < 1440) return 'Hours';
  if (minutes < 10080) return 'Days';
  return 'Weeks';
};

// Grouped options for better UX in select dropdowns
export const DURATION_OPTIONS_GROUPED = {
  'Hours': DURATION_OPTIONS.filter(opt => opt.value < 1440),
  'Days': DURATION_OPTIONS.filter(opt => opt.value >= 1440 && opt.value < 10080),
  'Weeks': DURATION_OPTIONS.filter(opt => opt.value >= 10080),
};

export default DURATION_OPTIONS;
