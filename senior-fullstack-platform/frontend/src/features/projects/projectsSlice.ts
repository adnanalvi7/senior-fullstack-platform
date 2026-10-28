import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import {
  ApprovalUpdateEvent,
  NewProjectPayload,
  PaginatedResponse,
  Project,
  ProjectStatus,
  Property,
} from '../../types';
import { apiClient, apiErrorMessage, apiErrorStatus } from '../../app/api';
import { TRANSITIONS, WorkflowAction } from './workflow';

interface RealtimeNotification {
  id: string;
  projectId: number;
  title: string;
  oldStatus: string;
  newStatus: string;
  actorEmail: string;
  timestamp: string;
}

export interface ProjectQuery {
  page?: number;
  propertyId?: number | null;
  status?: string;
  category?: string;
  fiscalPeriod?: string;
  search?: string;
}

interface FetchProjectsArg extends ProjectQuery {
  /** Refresh in place (real-time sync): keep current rows visible instead of a loading state. */
  background?: boolean;
}

interface ProjectsState {
  items: Project[];
  totalCount: number;
  currentPage: number;
  totalPages: number;
  loading: boolean;
  error: string | null;
  properties: Property[];
  propertiesLoading: boolean;
  /** Last list query, so background refreshes keep the user's page and filters. */
  lastQuery: ProjectQuery;
  // Optimistic rollback tracking
  previousStateBackup: Record<number, ProjectStatus>;
  realtimeNotifications: RealtimeNotification[];
  /** Highest approval event id applied per project: older/duplicate events are ignored. */
  lastEventId: Record<number, number>;
}

const initialState: ProjectsState = {
  items: [],
  totalCount: 0,
  currentPage: 1,
  totalPages: 1,
  loading: false,
  error: null,
  properties: [],
  propertiesLoading: false,
  lastQuery: { page: 1 },
  previousStateBackup: {},
  realtimeNotifications: [],
  lastEventId: {},
};

export const fetchProjects = createAsyncThunk<PaginatedResponse<Project>, FetchProjectsArg, { rejectValue: string }>(
  'projects/fetchProjects',
  async (filters, { rejectWithValue }) => {
    try {
      const params: Record<string, string | number> = { page: filters.page || 1 };
      if (filters.propertyId) params.property_id = filters.propertyId;
      if (filters.status) params.status = filters.status;
      if (filters.category) params.category = filters.category;
      if (filters.fiscalPeriod && filters.fiscalPeriod !== 'ALL') params.fiscal_period = filters.fiscalPeriod;
      if (filters.search) params.search = filters.search;

      const response = await apiClient.get<PaginatedResponse<Project>>('/projects/', { params });
      return response.data;
    } catch (err: unknown) {
      return rejectWithValue(apiErrorMessage(err, 'Failed to fetch projects'));
    }
  }
);

export const fetchProject = createAsyncThunk<Project, number, { rejectValue: string }>(
  'projects/fetchProject',
  async (projectId, { rejectWithValue }) => {
    try {
      return (await apiClient.get<Project>(`/projects/${projectId}/`)).data;
    } catch (err: unknown) {
      return rejectWithValue(apiErrorMessage(err, 'Failed to refresh project'));
    }
  }
);

export const fetchProperties = createAsyncThunk<Property[], void, { rejectValue: string }>(
  'projects/fetchProperties',
  async (_, { rejectWithValue }) => {
    try {
      // Follow pagination: large orgs have more properties than one page.
      const all: Property[] = [];
      let page = 1;
      for (;;) {
        const { data } = await apiClient.get<PaginatedResponse<Property>>('/properties/', {
          params: { page, page_size: 200 },
        });
        all.push(...data.results);
        if (!data.next) return all;
        page += 1;
      }
    } catch (err: unknown) {
      return rejectWithValue(apiErrorMessage(err, 'Failed to fetch properties'));
    }
  }
);

export const createProject = createAsyncThunk<Project, NewProjectPayload, { rejectValue: string }>(
  'projects/createProject',
  async (payload, { rejectWithValue }) => {
    try {
      const response = await apiClient.post<Project>('/projects/', payload);
      return response.data;
    } catch (err: unknown) {
      return rejectWithValue(apiErrorMessage(err, 'Failed to create project'));
    }
  }
);

export const executeApproval = createAsyncThunk<
  { project: Project },
  { projectId: number; action: WorkflowAction; notes?: string },
  { rejectValue: { projectId: number; error: string; conflict: boolean } }
>('projects/executeApproval', async ({ projectId, action, notes }, { rejectWithValue, dispatch }) => {
  try {
    const response = await apiClient.post<{ project: Project }>(`/projects/${projectId}/approve/`, {
      action,
      notes,
    });
    return response.data;
  } catch (err: unknown) {
    const conflict = apiErrorStatus(err) === 409;
    if (conflict) {
      // Someone else changed the project: show the authoritative state, not our stale copy.
      dispatch(fetchProject(projectId));
    }
    return rejectWithValue({ projectId, error: apiErrorMessage(err, 'Approval action failed'), conflict });
  }
});

const isNewerEvent = (state: ProjectsState, event: ApprovalUpdateEvent) =>
  event.event_id > (state.lastEventId[event.project_id] ?? 0);

export const projectsSlice = createSlice({
  name: 'projects',
  initialState,
  reducers: {
    // Optimistic status update before API returns
    optimisticApprovalStart: (state, action: PayloadAction<{ projectId: number; approvalAction: WorkflowAction }>) => {
      const { projectId, approvalAction } = action.payload;
      const targetProj = state.items.find((p) => p.id === projectId);
      if (targetProj) {
        state.previousStateBackup[projectId] = targetProj.status;
        targetProj.status = TRANSITIONS[approvalAction].to;
      }
    },
    // Real-time WebSocket event received
    receiveWebSocketApproval: (state, action: PayloadAction<ApprovalUpdateEvent>) => {
      const event = action.payload;
      if (!isNewerEvent(state, event)) return; // duplicate or out-of-order delivery
      state.lastEventId[event.project_id] = event.event_id;
      const target = state.items.find((p) => p.id === event.project_id);
      if (target) {
        target.status = event.new_status;
      }
      state.realtimeNotifications.unshift({
        id: `${event.project_id}-${event.event_id}`,
        projectId: event.project_id,
        title: event.title,
        oldStatus: event.old_status,
        newStatus: event.new_status,
        actorEmail: event.actor_email,
        timestamp: event.timestamp,
      });
      if (state.realtimeNotifications.length > 10) {
        state.realtimeNotifications.pop();
      }
    },
    dismissRealtimeNotification: (state, action: PayloadAction<string>) => {
      state.realtimeNotifications = state.realtimeNotifications.filter((n) => n.id !== action.payload);
    },
    clearProjectsError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch Projects
      .addCase(fetchProjects.pending, (state, action) => {
        const { background, ...query } = action.meta.arg;
        state.loading = !background;
        state.error = null;
        state.lastQuery = query;
      })
      .addCase(fetchProjects.fulfilled, (state, action) => {
        state.loading = false;
        state.items = action.payload.results;
        state.totalCount = action.payload.count;
        state.currentPage = action.payload.current_page;
        state.totalPages = action.payload.total_pages;
      })
      .addCase(fetchProjects.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload || 'Failed to load projects';
      })
      .addCase(fetchProject.fulfilled, (state, action) => {
        const idx = state.items.findIndex((p) => p.id === action.payload.id);
        if (idx !== -1) state.items[idx] = action.payload;
      })
      // Fetch Properties
      .addCase(fetchProperties.pending, (state) => {
        state.propertiesLoading = true;
      })
      .addCase(fetchProperties.fulfilled, (state, action) => {
        state.propertiesLoading = false;
        state.properties = action.payload;
      })
      .addCase(fetchProperties.rejected, (state) => {
        state.propertiesLoading = false;
      })
      // Create Project
      .addCase(createProject.fulfilled, (state, action) => {
        state.items.unshift(action.payload);
        state.totalCount += 1;
      })
      .addCase(createProject.rejected, (state, action) => {
        state.error = action.payload || 'Failed to create project';
      })
      // Approval Success
      .addCase(executeApproval.fulfilled, (state, action) => {
        const updated = action.payload.project;
        delete state.previousStateBackup[updated.id];
        const idx = state.items.findIndex((p) => p.id === updated.id);
        if (idx !== -1) {
          state.items[idx] = updated;
        }
      })
      // Approval Failure: undo the optimistic change (a 409 additionally refetches the row)
      .addCase(executeApproval.rejected, (state, action) => {
        if (action.payload) {
          const { projectId, error } = action.payload;
          state.error = error;
          const prev = state.previousStateBackup[projectId];
          if (prev) {
            const target = state.items.find((p) => p.id === projectId);
            if (target) {
              target.status = prev;
            }
            delete state.previousStateBackup[projectId];
          }
        }
      });
  },
});

export const {
  optimisticApprovalStart,
  receiveWebSocketApproval,
  dismissRealtimeNotification,
  clearProjectsError,
} = projectsSlice.actions;

export default projectsSlice.reducer;
