"""Domain vocabularies shared by models, serializers, analytics, workers and the seeder."""

FISCAL_PERIODS = ('FY2024', 'FY2025', 'FY2026')
FISCAL_PERIOD_CHOICES = tuple((fp, fp) for fp in FISCAL_PERIODS)

# Dashboard-only pseudo period: the sum of every fiscal period. It is derived at read time
# from the per-period rollups and is never stored.
ALL_PERIODS = 'ALL'

CATEGORIES = (
    'HVAC', 'Roofing', 'Electrical', 'Plumbing', 'IT/Network',
    'Furniture/FF&E', 'Elevators', 'Life Safety', 'Landscaping', 'Renovation',
)
CATEGORY_CHOICES = tuple((c, c) for c in CATEGORIES)

PENDING_STATUSES = ('submitted', 'manager_review', 'finance_review')
TERMINAL_STATUSES = ('approved', 'rejected')
