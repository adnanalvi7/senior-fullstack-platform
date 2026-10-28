import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  Button,
  Chip,
  IconButton,
  Tooltip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Snackbar,
  Alert,
} from '@mui/material';
import BusinessIcon from '@mui/icons-material/Business';
import LogoutIcon from '@mui/icons-material/Logout';
import RefreshIcon from '@mui/icons-material/Refresh';
import WifiIcon from '@mui/icons-material/Wifi';
import WifiOffIcon from '@mui/icons-material/WifiOff';
import { useAppDispatch, useAppSelector } from '../app/store';
import { logout } from '../features/auth/authSlice';
import {
  setFiscalPeriod,
  setSelectedPropertyId,
  fetchDashboardData,
  triggerAggregateRefresh,
} from '../features/analytics/analyticsSlice';
import { fetchProjects, dismissRealtimeNotification } from '../features/projects/projectsSlice';
import { useWebSocket } from '../hooks/useWebSocket';
import { ALL_PERIODS, FISCAL_PERIODS } from '../constants';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const dispatch = useAppDispatch();
  const user = useAppSelector((state) => state.auth.user);
  const { fiscalPeriod, selectedPropertyId, refreshing } = useAppSelector((state) => state.analytics);
  const { properties, realtimeNotifications, lastQuery } = useAppSelector((state) => state.projects);
  const isOrgAdmin = user?.role === 'org_admin';

  const { connected } = useWebSocket();

  const handleFiscalChange = (newPeriod: string) => {
    dispatch(setFiscalPeriod(newPeriod));
    dispatch(fetchDashboardData({ fiscalPeriod: newPeriod, propertyId: selectedPropertyId }));
    dispatch(fetchProjects({ ...lastQuery, page: 1, fiscalPeriod: newPeriod, propertyId: selectedPropertyId }));
  };

  const handlePropertyChange = (newPropId: number | null) => {
    dispatch(setSelectedPropertyId(newPropId));
    dispatch(fetchDashboardData({ fiscalPeriod, propertyId: newPropId }));
    dispatch(fetchProjects({ ...lastQuery, page: 1, fiscalPeriod, propertyId: newPropId }));
  };

  const handleRefresh = () => {
    dispatch(triggerAggregateRefresh());
  };

  const roleColorMap: Record<string, 'primary' | 'success' | 'warning' | 'default'> = {
    org_admin: 'primary',
    property_manager: 'success',
    approver: 'warning',
    viewer: 'default',
  };

  const latestNotification = realtimeNotifications[0];

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#0B0F17', color: '#F1F5F9' }}>
      <AppBar
        position="sticky"
        elevation={0}
        sx={{
          bgcolor: '#131B2A',
          borderBottom: '1px solid #1E293B',
        }}
      >
        <Toolbar sx={{ justifyContent: 'space-between', gap: 2, flexWrap: 'wrap', py: 1 }}>
          {/* Brand & Organization */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <BusinessIcon sx={{ color: '#38BDF8', fontSize: 28 }} />
            <Box>
              <Typography variant="h6" fontWeight={700} sx={{ lineHeight: 1.2, color: '#F8FAFC' }}>
                Blue Ocean CapEx
              </Typography>
              <Typography variant="caption" sx={{ color: '#38BDF8', fontWeight: 600 }}>
                {user?.org_name || 'Organization'}
              </Typography>
            </Box>
          </Box>

          {/* Controls: Fiscal Period, Property Scope, Refresh */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel id="fiscal-period-label" sx={{ color: '#94A3B8' }}>Fiscal Period</InputLabel>
              <Select
                labelId="fiscal-period-label"
                value={fiscalPeriod}
                label="Fiscal Period"
                onChange={(e) => handleFiscalChange(e.target.value)}
                sx={{
                  color: '#FFF',
                  bgcolor: '#0F172A',
                  '& .MuiOutlinedInput-notchedOutline': { borderColor: '#334155' },
                }}
              >
                <MenuItem value={ALL_PERIODS}>ALL PERIODS</MenuItem>
                {FISCAL_PERIODS.map((fp) => (
                  <MenuItem key={fp} value={fp}>
                    {fp}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel id="property-scope-label" sx={{ color: '#94A3B8' }}>Property Scope</InputLabel>
              <Select
                labelId="property-scope-label"
                value={selectedPropertyId === null ? '' : selectedPropertyId}
                label="Property Scope"
                onChange={(e) => handlePropertyChange(e.target.value === '' ? null : Number(e.target.value))}
                sx={{
                  color: '#FFF',
                  bgcolor: '#0F172A',
                  '& .MuiOutlinedInput-notchedOutline': { borderColor: '#334155' },
                }}
              >
                <MenuItem value="">
                  <em>{user?.role === 'org_admin' ? 'All Org Properties' : 'All Entitled Properties'}</em>
                </MenuItem>
                {properties.map((prop) => (
                  <MenuItem key={prop.id} value={prop.id}>
                    {prop.code} - {prop.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {isOrgAdmin && (
            <Tooltip title="Rebuild all aggregates for the organization (background job)">
              <span>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={handleRefresh}
                  disabled={refreshing}
                  startIcon={<RefreshIcon />}
                  sx={{
                    color: '#38BDF8',
                    borderColor: '#0284C7',
                    '&:hover': { borderColor: '#38BDF8', bgcolor: 'rgba(56, 189, 248, 0.1)' },
                  }}
                >
                  {refreshing ? 'Refreshing...' : 'Rollup'}
                </Button>
              </span>
            </Tooltip>
            )}
          </Box>

          {/* User Status, WebSocket Indicator, Logout */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Tooltip title={connected ? 'Real-time stream healthy (heartbeat answered)' : 'Real-time stream offline — reconnecting'}>
              <Chip
                icon={connected ? <WifiIcon sx={{ fontSize: '1rem !important' }} /> : <WifiOffIcon sx={{ fontSize: '1rem !important' }} />}
                label={connected ? 'LIVE' : 'OFFLINE'}
                size="small"
                sx={{
                  bgcolor: connected ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: connected ? '#4ADE80' : '#F87171',
                  border: `1px solid ${connected ? '#22C55E' : '#EF4444'}`,
                  fontWeight: 700,
                  fontSize: '0.75rem',
                }}
              />
            </Tooltip>

            <Box sx={{ textAlign: 'right', display: { xs: 'none', sm: 'block' } }}>
              <Typography variant="body2" sx={{ color: '#F1F5F9', fontWeight: 500 }}>
                {user?.email}
              </Typography>
              <Chip
                label={user?.role}
                size="small"
                color={user ? roleColorMap[user.role] : 'default'}
                sx={{ height: 20, fontSize: '0.7rem', fontWeight: 600 }}
              />
            </Box>

            <Tooltip title="Sign Out">
              <IconButton aria-label="Sign out" onClick={() => dispatch(logout())} sx={{ color: '#94A3B8', '&:hover': { color: '#F87171' } }}>
                <LogoutIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Main Content */}
      <Box sx={{ p: { xs: 2, md: 3 }, maxWidth: 1400, mx: 'auto' }}>
        {children}
      </Box>

      {/* Real-time Notification Banner */}
      {latestNotification && (
        <Snackbar
          open={true}
          autoHideDuration={6000}
          onClose={() => dispatch(dismissRealtimeNotification(latestNotification.id))}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <Alert
            severity="info"
            onClose={() => dispatch(dismissRealtimeNotification(latestNotification.id))}
            sx={{ bgcolor: '#1E293B', color: '#38BDF8', border: '1px solid #0284C7' }}
          >
            <strong>Real-time Update:</strong> Project #{latestNotification.projectId} ({latestNotification.title}) moved to{' '}
            <strong>{latestNotification.newStatus}</strong> by {latestNotification.actorEmail}
          </Alert>
        </Snackbar>
      )}
    </Box>
  );
};
