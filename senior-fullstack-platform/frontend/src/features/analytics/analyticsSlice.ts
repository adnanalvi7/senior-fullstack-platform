import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { DashboardData } from '../../types';
import { apiClient, apiErrorMessage } from '../../app/api';
import { ALL_PERIODS } from '../../constants';

interface AnalyticsState {
  data: DashboardData | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  fiscalPeriod: string;
  selectedPropertyId: number | null;
}

const initialState: AnalyticsState = {
  data: null,
  loading: false,
  refreshing: false,
  error: null,
  fiscalPeriod: ALL_PERIODS,
  selectedPropertyId: null,
};

interface DashboardQuery {
  fiscalPeriod?: string;
  propertyId?: number | null;
}

export const fetchDashboardData = createAsyncThunk<DashboardData, DashboardQuery, { rejectValue: string }>(
  'analytics/fetchDashboard',
  async ({ fiscalPeriod = ALL_PERIODS, propertyId = null }, { rejectWithValue }) => {
    try {
      const params: Record<string, string | number> = { fiscal_period: fiscalPeriod };
      if (propertyId) {
        params.property_id = propertyId;
      }
      const response = await apiClient.get<DashboardData>('/analytics/dashboard/', { params });
      return response.data;
    } catch (err: unknown) {
      return rejectWithValue(apiErrorMessage(err, 'Failed to fetch analytics data'));
    }
  }
);

export const triggerAggregateRefresh = createAsyncThunk<void, void, { rejectValue: string }>(
  'analytics/triggerRefresh',
  async (_, { rejectWithValue }) => {
    try {
      // The rebuild is asynchronous; dashboards refetch on the resulting analytics_update events.
      await apiClient.post('/analytics/refresh/');
    } catch (err: unknown) {
      return rejectWithValue(apiErrorMessage(err, 'Failed to trigger aggregate refresh'));
    }
  }
);

export const analyticsSlice = createSlice({
  name: 'analytics',
  initialState,
  reducers: {
    setFiscalPeriod: (state, action: PayloadAction<string>) => {
      state.fiscalPeriod = action.payload;
    },
    setSelectedPropertyId: (state, action: PayloadAction<number | null>) => {
      state.selectedPropertyId = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchDashboardData.pending, (state) => {
        // Skeletons only on first load; background refreshes keep the current numbers visible.
        state.loading = state.data === null;
        state.error = null;
      })
      .addCase(fetchDashboardData.fulfilled, (state, action: PayloadAction<DashboardData>) => {
        state.loading = false;
        state.data = action.payload;
      })
      .addCase(fetchDashboardData.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload || 'Failed to load analytics';
      })
      .addCase(triggerAggregateRefresh.pending, (state) => {
        state.refreshing = true;
      })
      .addCase(triggerAggregateRefresh.fulfilled, (state) => {
        state.refreshing = false;
      })
      .addCase(triggerAggregateRefresh.rejected, (state) => {
        state.refreshing = false;
      });
  },
});

export const { setFiscalPeriod, setSelectedPropertyId } = analyticsSlice.actions;
export default analyticsSlice.reducer;
