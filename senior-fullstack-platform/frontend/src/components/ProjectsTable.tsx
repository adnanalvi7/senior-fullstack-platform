import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Pagination,
  IconButton,
  Tooltip,
  InputAdornment,
  Stack,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import AddIcon from '@mui/icons-material/Add';
import HistoryIcon from '@mui/icons-material/History';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import SendIcon from '@mui/icons-material/Send';
import CancelIcon from '@mui/icons-material/Cancel';
import { Project, ProjectStatus, User } from '../types';
import { CATEGORIES } from '../constants';
import { availableActions, WorkflowAction } from '../features/projects/workflow';

interface ProjectsTableProps {
  projects: Project[];
  totalCount: number;
  currentPage: number;
  totalPages: number;
  loading: boolean;
  user: User | null;
  onPageChange: (page: number) => void;
  onFilterChange: (filters: { search?: string; status?: string; category?: string }) => void;
  onActionClick: (project: Project, action: WorkflowAction) => void;
  onHistoryClick: (project: Project) => void;
  onNewProjectClick: () => void;
}

const STATUS_CONFIG: Record<
  ProjectStatus,
  { label: string; color: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' }
> = {
  draft: { label: 'Draft', color: 'default' },
  submitted: { label: 'Submitted', color: 'info' },
  manager_review: { label: 'Manager Review', color: 'warning' },
  finance_review: { label: 'Finance Review', color: 'secondary' },
  approved: { label: 'Approved', color: 'success' },
  rejected: { label: 'Rejected', color: 'error' },
};

export const ProjectsTable: React.FC<ProjectsTableProps> = ({
  projects,
  totalCount,
  currentPage,
  totalPages,
  loading,
  user,
  onPageChange,
  onFilterChange,
  onActionClick,
  onHistoryClick,
  onNewProjectClick,
}) => {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  const handleSearchChange = (val: string) => {
    setSearch(val);
    onFilterChange({ search: val, status: statusFilter, category: categoryFilter });
  };

  const handleStatusFilter = (val: string) => {
    setStatusFilter(val);
    onFilterChange({ search, status: val, category: categoryFilter });
  };

  const handleCategoryFilter = (val: string) => {
    setCategoryFilter(val);
    onFilterChange({ search, status: statusFilter, category: val });
  };

  const formatCurrency = (val: string | number) => {
    const num = typeof val === 'string' ? parseFloat(val) : val;
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(num || 0);
  };

  const canCreate = user?.role === 'org_admin' || user?.role === 'property_manager';
  // Row actions come from the shared transition map (mirrors the backend state machine).
  const PRIMARY_ACTION_UI: Record<
    Exclude<WorkflowAction, 'reject'>,
    { label: string; tooltip: string; color: 'info' | 'warning' | 'secondary' | 'success'; icon: React.ReactElement }
  > = {
    submit: { label: 'Submit', tooltip: 'Submit for Approval', color: 'info', icon: <SendIcon sx={{ fontSize: '1rem !important' }} /> },
    manager_approve: {
      label: 'Sign-Off',
      tooltip: 'Approve & Advance to Manager Review',
      color: 'warning',
      icon: <CheckCircleIcon sx={{ fontSize: '1rem !important' }} />,
    },
    finance_approve: {
      label: 'Finance OK',
      tooltip: 'Advance to Finance Review',
      color: 'secondary',
      icon: <CheckCircleIcon sx={{ fontSize: '1rem !important' }} />,
    },
    final_approve: {
      label: 'Approve',
      tooltip: 'Final Executive Approval',
      color: 'success',
      icon: <CheckCircleIcon sx={{ fontSize: '1rem !important' }} />,
    },
  };

  const renderWorkflowActions = (proj: Project) => {
    const actions = availableActions(proj, user);
    if (actions.length === 0) return null;
    return (
      <Stack direction="row" spacing={0.5}>
        {actions.map((action) => {
          if (action === 'reject') {
            return (
              <Tooltip key={action} title="Reject Request">
                <IconButton size="small" color="error" aria-label="Reject" onClick={() => onActionClick(proj, action)} sx={{ p: 0.5 }}>
                  <CancelIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            );
          }
          const ui = PRIMARY_ACTION_UI[action];
          return (
            <Tooltip key={action} title={ui.tooltip}>
              <Button
                size="small"
                variant="contained"
                color={ui.color}
                startIcon={ui.icon}
                onClick={() => onActionClick(proj, action)}
                sx={{ fontSize: '0.75rem', py: 0.3 }}
              >
                {ui.label}
              </Button>
            </Tooltip>
          );
        })}
      </Stack>
    );
  };

  return (
    <Card sx={{ bgcolor: '#131B2A', border: '1px solid #1E293B', borderRadius: 2 }}>
      <CardContent sx={{ p: 3 }}>
        {/* Table Header Controls */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2.5, flexWrap: 'wrap', gap: 2 }}>
          <Box>
            <Typography variant="h6" fontWeight={700} sx={{ color: '#F8FAFC' }}>
              Capital Projects Portfolio
            </Typography>
            <Typography variant="caption" sx={{ color: '#94A3B8' }}>
              Showing {projects.length} of {totalCount} projects scoped to your entitlements
            </Typography>
          </Box>

          {canCreate && (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={onNewProjectClick}
              sx={{
                bgcolor: '#0284C7',
                '&:hover': { bgcolor: '#0369A1' },
                fontWeight: 600,
                textTransform: 'none',
              }}
            >
              New Spending Request
            </Button>
          )}
        </Box>

        {/* Filters */}
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 2.5 }}>
          <TextField
            size="small"
            placeholder="Search projects or property..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ color: '#64748B' }} />
                </InputAdornment>
              ),
            }}
            sx={{
              flex: 1,
              '& .MuiOutlinedInput-root': {
                color: '#FFF',
                bgcolor: '#0F172A',
                '& fieldset': { borderColor: '#334155' },
              },
            }}
          />

          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel id="filter-status-label" sx={{ color: '#94A3B8' }}>Filter Status</InputLabel>
            <Select
              labelId="filter-status-label"
              value={statusFilter}
              label="Filter Status"
              onChange={(e) => handleStatusFilter(e.target.value)}
              sx={{
                color: '#FFF',
                bgcolor: '#0F172A',
                '& .MuiOutlinedInput-notchedOutline': { borderColor: '#334155' },
              }}
            >
              <MenuItem value="">All Statuses</MenuItem>
              <MenuItem value="draft">Draft</MenuItem>
              <MenuItem value="submitted">Submitted</MenuItem>
              <MenuItem value="manager_review">Manager Review</MenuItem>
              <MenuItem value="finance_review">Finance Review</MenuItem>
              <MenuItem value="approved">Approved</MenuItem>
              <MenuItem value="rejected">Rejected</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel id="filter-category-label" sx={{ color: '#94A3B8' }}>Category</InputLabel>
            <Select
              labelId="filter-category-label"
              value={categoryFilter}
              label="Category"
              onChange={(e) => handleCategoryFilter(e.target.value)}
              sx={{
                color: '#FFF',
                bgcolor: '#0F172A',
                '& .MuiOutlinedInput-notchedOutline': { borderColor: '#334155' },
              }}
            >
              <MenuItem value="">All Categories</MenuItem>
              {CATEGORIES.map((c) => (
                <MenuItem key={c} value={c}>
                  {c}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>

        {/* Data Table */}
        <TableContainer sx={{ border: '1px solid #1E293B', borderRadius: 1.5, overflowX: 'auto' }}>
          <Table size="small">
            <TableHead sx={{ bgcolor: '#0F172A' }}>
              <TableRow>
                <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Project</TableCell>
                <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Property</TableCell>
                <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Category</TableCell>
                <TableCell sx={{ color: '#94A3B8', fontWeight: 600 }}>Period</TableCell>
                <TableCell align="right" sx={{ color: '#94A3B8', fontWeight: 600 }}>Budget</TableCell>
                <TableCell align="right" sx={{ color: '#94A3B8', fontWeight: 600 }}>Actuals</TableCell>
                <TableCell align="right" sx={{ color: '#94A3B8', fontWeight: 600 }}>Variance</TableCell>
                <TableCell align="center" sx={{ color: '#94A3B8', fontWeight: 600 }}>Status</TableCell>
                <TableCell align="center" sx={{ color: '#94A3B8', fontWeight: 600 }}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={9} align="center" sx={{ py: 4, color: '#94A3B8' }}>
                    Loading projects...
                  </TableCell>
                </TableRow>
              ) : projects.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} align="center" sx={{ py: 4, color: '#94A3B8' }}>
                    No projects found matching the current filters and entitlements.
                  </TableCell>
                </TableRow>
              ) : (
                projects.map((proj) => {
                  const varianceNum = parseFloat(proj.variance_amount || '0');
                  const isOver = varianceNum > 0;
                  const cfg = STATUS_CONFIG[proj.status] || { label: proj.status, color: 'default' };

                  return (
                    <TableRow
                      key={proj.id}
                      hover
                      sx={{
                        '&:hover': { bgcolor: 'rgba(30, 41, 59, 0.5) !important' },
                        borderColor: '#1E293B',
                      }}
                    >
                      <TableCell sx={{ color: '#F8FAFC', fontWeight: 500, borderColor: '#1E293B' }}>
                        #{proj.id} {proj.title}
                      </TableCell>
                      <TableCell sx={{ color: '#CBD5E1', borderColor: '#1E293B' }}>
                        <Typography variant="body2" fontWeight={500}>
                          {proj.property_code}
                        </Typography>
                        <Typography variant="caption" sx={{ color: '#64748B' }}>
                          {proj.property_name}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ color: '#CBD5E1', borderColor: '#1E293B' }}>
                        {proj.category}
                      </TableCell>
                      <TableCell sx={{ color: '#94A3B8', borderColor: '#1E293B' }}>
                        {proj.fiscal_period}
                      </TableCell>
                      <TableCell align="right" sx={{ color: '#F8FAFC', fontWeight: 500, borderColor: '#1E293B' }}>
                        {formatCurrency(proj.budget_amount)}
                      </TableCell>
                      <TableCell align="right" sx={{ color: '#CBD5E1', borderColor: '#1E293B' }}>
                        {formatCurrency(proj.actual_cost)}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          color: isOver ? '#F87171' : '#4ADE80',
                          fontWeight: 600,
                          borderColor: '#1E293B',
                        }}
                      >
                        {isOver ? '+' : ''}
                        {formatCurrency(proj.variance_amount)}
                        <Typography variant="caption" sx={{ display: 'block', fontSize: '0.7rem' }}>
                          ({proj.variance_percentage}%)
                        </Typography>
                      </TableCell>
                      <TableCell align="center" sx={{ borderColor: '#1E293B' }}>
                        <Chip
                          size="small"
                          label={cfg.label}
                          color={cfg.color}
                          sx={{ fontWeight: 600, fontSize: '0.75rem', height: 22 }}
                        />
                      </TableCell>
                      <TableCell align="center" sx={{ borderColor: '#1E293B' }}>
                        <Stack direction="row" spacing={0.5} justifyContent="center" alignItems="center">
                          {renderWorkflowActions(proj)}
                          <Tooltip title="View Approval Audit Trail">
                            <IconButton
                              size="small"
                              onClick={() => onHistoryClick(proj)}
                              sx={{ color: '#94A3B8', '&:hover': { color: '#38BDF8' } }}
                            >
                              <HistoryIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Stack>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Pagination */}
        {totalPages > 1 && (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
            <Pagination
              count={totalPages}
              page={currentPage}
              onChange={(_, p) => onPageChange(p)}
              color="primary"
              sx={{
                '& .MuiPaginationItem-root': { color: '#94A3B8' },
                '& .Mui-selected': { bgcolor: '#0284C7 !important', color: '#FFF' },
              }}
            />
          </Box>
        )}
      </CardContent>
    </Card>
  );
};
