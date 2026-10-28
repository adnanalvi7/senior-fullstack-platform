import React, { useEffect, useState } from 'react';
import { Box, Alert, Snackbar } from '@mui/material';
import { useAppDispatch, useAppSelector } from './app/store';
import { LoginPage } from './features/auth/LoginPage';
import { Layout } from './components/Layout';
import { KPICards } from './components/KPICards';
import { AnalyticsCharts } from './components/AnalyticsCharts';
import { ProjectsTable } from './components/ProjectsTable';
import { ApprovalDialog } from './components/ApprovalDialog';
import { HistoryDialog } from './components/HistoryDialog';
import { NewProjectDialog } from './components/NewProjectDialog';
import { fetchDashboardData } from './features/analytics/analyticsSlice';
import {
  fetchProjects,
  fetchProperties,
  createProject,
  executeApproval,
  optimisticApprovalStart,
  clearProjectsError,
} from './features/projects/projectsSlice';
import { NewProjectPayload, Project } from './types';
import { WorkflowAction } from './features/projects/workflow';

// Rollups are recomputed asynchronously; dashboards normally refresh on the analytics_update
// WebSocket event. This delayed refetch is the fallback when the stream is down.
const DASHBOARD_FALLBACK_REFRESH_MS = 2000;

export const App: React.FC = () => {
  const dispatch = useAppDispatch();
  const { isAuthenticated, user } = useAppSelector((state) => state.auth);
  const { data: analyticsData, loading: analyticsLoading, fiscalPeriod, selectedPropertyId } =
    useAppSelector((state) => state.analytics);
  const {
    items: projects,
    totalCount,
    currentPage,
    totalPages,
    lastQuery,
    loading: projectsLoading,
    properties,
    error: projectError,
  } = useAppSelector((state) => state.projects);

  // Dialog states
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [approvalAction, setApprovalAction] = useState<WorkflowAction>('submit');
  const [approvalOpen, setApprovalOpen] = useState<boolean>(false);
  const [historyOpen, setHistoryOpen] = useState<boolean>(false);
  const [newProjectOpen, setNewProjectOpen] = useState<boolean>(false);

  // Initial data loading on authentication
  useEffect(() => {
    if (isAuthenticated) {
      dispatch(fetchDashboardData({ fiscalPeriod, propertyId: selectedPropertyId }));
      dispatch(fetchProperties());
      dispatch(fetchProjects({ page: 1, fiscalPeriod, propertyId: selectedPropertyId }));
    }
  }, [isAuthenticated, dispatch]);

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const refreshDashboardLater = () =>
    window.setTimeout(
      () => dispatch(fetchDashboardData({ fiscalPeriod, propertyId: selectedPropertyId })),
      DASHBOARD_FALLBACK_REFRESH_MS
    );

  const handleActionClick = (project: Project, action: WorkflowAction) => {
    setSelectedProject(project);
    setApprovalAction(action);
    setApprovalOpen(true);
  };

  const handleHistoryClick = (project: Project) => {
    setSelectedProject(project);
    setHistoryOpen(true);
  };

  const handleConfirmApproval = (projectId: number, action: WorkflowAction, notes: string) => {
    // 1. Controlled optimistic status update
    dispatch(optimisticApprovalStart({ projectId, approvalAction: action }));
    // 2. Authoritative server mutation (a 409 rolls back and refetches the row)
    dispatch(executeApproval({ projectId, action, notes })).then((result) => {
      if (executeApproval.fulfilled.match(result)) refreshDashboardLater();
    });
  };

  const handleCreateProject = (data: NewProjectPayload) => {
    dispatch(createProject(data)).then((result) => {
      if (!createProject.fulfilled.match(result)) return;
      dispatch(fetchProjects({ ...lastQuery, page: 1 }));
      refreshDashboardLater();
    });
  };

  const handlePageChange = (page: number) => {
    dispatch(fetchProjects({ ...lastQuery, page }));
  };

  const handleFilterChange = (filters: { search?: string; status?: string; category?: string }) => {
    dispatch(
      fetchProjects({
        page: 1,
        fiscalPeriod,
        propertyId: selectedPropertyId,
        ...filters,
      })
    );
  };

  return (
    <Layout>
      <Box sx={{ py: 1 }}>
        {/* Executive KPI Summary Cards */}
        <KPICards kpis={analyticsData?.kpis} loading={analyticsLoading} asOf={analyticsData?.as_of} />

        {/* Analytics Charts: Spend by Category & Status Pipeline */}
        <AnalyticsCharts
          categorySpend={analyticsData?.category_spend}
          statusDistribution={analyticsData?.status_distribution}
          loading={analyticsLoading}
        />

        {/* Scoped Projects Table with Role-Aware Workflow Actions */}
        <ProjectsTable
          projects={projects}
          totalCount={totalCount}
          currentPage={currentPage}
          totalPages={totalPages}
          loading={projectsLoading}
          user={user}
          onPageChange={handlePageChange}
          onFilterChange={handleFilterChange}
          onActionClick={handleActionClick}
          onHistoryClick={handleHistoryClick}
          onNewProjectClick={() => setNewProjectOpen(true)}
        />
      </Box>

      {/* Approval Confirmation Dialog */}
      <ApprovalDialog
        open={approvalOpen}
        project={selectedProject}
        action={approvalAction}
        onClose={() => setApprovalOpen(false)}
        onConfirm={handleConfirmApproval}
      />

      {/* Approval Audit Trail History Dialog */}
      <HistoryDialog
        open={historyOpen}
        project={selectedProject}
        onClose={() => setHistoryOpen(false)}
      />

      {/* Create New Project Dialog */}
      <NewProjectDialog
        open={newProjectOpen}
        properties={properties}
        onClose={() => setNewProjectOpen(false)}
        onSubmit={handleCreateProject}
      />

      {/* Error Toast */}
      {projectError && (
        <Snackbar
          open={true}
          autoHideDuration={6000}
          onClose={() => dispatch(clearProjectsError())}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          <Alert severity="error" onClose={() => dispatch(clearProjectsError())} sx={{ bgcolor: '#7F1D1D', color: '#FFF' }}>
            {projectError}
          </Alert>
        </Snackbar>
      )}
    </Layout>
  );
};

export default App;
