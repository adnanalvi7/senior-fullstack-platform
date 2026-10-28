// Mirrors backend/common/constants.py (closed vocabularies validated server-side).
export const FISCAL_PERIODS = ['FY2024', 'FY2025', 'FY2026'] as const;
export const ALL_PERIODS = 'ALL';

export const CATEGORIES = [
  'HVAC',
  'Roofing',
  'Electrical',
  'Plumbing',
  'IT/Network',
  'Furniture/FF&E',
  'Elevators',
  'Life Safety',
  'Landscaping',
  'Renovation',
] as const;
