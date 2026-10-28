import React from 'react';
import { Grid, Card, CardContent, Typography, Box, Skeleton } from '@mui/material';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import MonetizationOnIcon from '@mui/icons-material/MonetizationOn';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import PendingActionsIcon from '@mui/icons-material/PendingActions';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import { DashboardKPIs } from '../types';

interface KPICardsProps {
  kpis?: DashboardKPIs;
  loading: boolean;
  /** Oldest rollup timestamp behind these numbers. */
  asOf?: string | null;
}

export const KPICards: React.FC<KPICardsProps> = ({ kpis, loading, asOf }) => {
  const formatCurrency = (val?: number) => {
    if (val === undefined || isNaN(val)) return '$0.00';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(val);
  };

  const isOverBudget = (kpis?.total_variance || 0) > 0;

  return (
    <Grid container spacing={2} sx={{ mb: 3 }}>
      {/* 1. Total Budget */}
      <Grid item xs={12} sm={6} md={2.4}>
        <Card
          sx={{
            bgcolor: '#131B2A',
            border: '1px solid #1E293B',
            borderRadius: 2,
            transition: 'all 0.2s',
            '&:hover': { transform: 'translateY(-2px)', borderColor: '#38BDF8' },
          }}
        >
          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="caption" sx={{ color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase' }}>
                Allocated Budget
              </Typography>
              <AccountBalanceWalletIcon sx={{ color: '#38BDF8', fontSize: 20 }} />
            </Box>
            {loading ? (
              <Skeleton width="80%" height={32} sx={{ bgcolor: '#1E293B' }} />
            ) : (
              <Typography variant="h5" fontWeight={700} sx={{ color: '#F8FAFC' }}>
                {formatCurrency(kpis?.total_budget)}
              </Typography>
            )}
            <Typography variant="caption" sx={{ color: '#64748B' }}>
              {kpis?.project_count || 0} scoped projects
              {asOf ? ` · as of ${new Date(asOf).toLocaleTimeString()}` : ''}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* 2. Total Actual Spend */}
      <Grid item xs={12} sm={6} md={2.4}>
        <Card
          sx={{
            bgcolor: '#131B2A',
            border: '1px solid #1E293B',
            borderRadius: 2,
            transition: 'all 0.2s',
            '&:hover': { transform: 'translateY(-2px)', borderColor: '#818CF8' },
          }}
        >
          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="caption" sx={{ color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase' }}>
                Actual Spend
              </Typography>
              <MonetizationOnIcon sx={{ color: '#818CF8', fontSize: 20 }} />
            </Box>
            {loading ? (
              <Skeleton width="80%" height={32} sx={{ bgcolor: '#1E293B' }} />
            ) : (
              <Typography variant="h5" fontWeight={700} sx={{ color: '#F8FAFC' }}>
                {formatCurrency(kpis?.total_actual)}
              </Typography>
            )}
            <Typography variant="caption" sx={{ color: '#64748B' }}>
              Realized expenditures
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* 3. Budget Variance */}
      <Grid item xs={12} sm={6} md={2.4}>
        <Card
          sx={{
            bgcolor: '#131B2A',
            border: '1px solid #1E293B',
            borderRadius: 2,
            transition: 'all 0.2s',
            '&:hover': { transform: 'translateY(-2px)', borderColor: isOverBudget ? '#F87171' : '#4ADE80' },
          }}
        >
          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="caption" sx={{ color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase' }}>
                Net Variance
              </Typography>
              {isOverBudget ? (
                <TrendingUpIcon sx={{ color: '#F87171', fontSize: 20 }} />
              ) : (
                <TrendingDownIcon sx={{ color: '#4ADE80', fontSize: 20 }} />
              )}
            </Box>
            {loading ? (
              <Skeleton width="80%" height={32} sx={{ bgcolor: '#1E293B' }} />
            ) : (
              <Typography
                variant="h5"
                fontWeight={700}
                sx={{ color: isOverBudget ? '#F87171' : '#4ADE80' }}
              >
                {formatCurrency(kpis?.total_variance)}
              </Typography>
            )}
            <Typography variant="caption" sx={{ color: isOverBudget ? '#FCA5A5' : '#86EFAC', fontWeight: 600 }}>
              {isOverBudget ? '+' : ''}
              {kpis?.variance_percentage || 0}% vs planned
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* 4. Pending Approvals */}
      <Grid item xs={12} sm={6} md={2.4}>
        <Card
          sx={{
            bgcolor: '#131B2A',
            border: '1px solid #1E293B',
            borderRadius: 2,
            transition: 'all 0.2s',
            '&:hover': { transform: 'translateY(-2px)', borderColor: '#FBBF24' },
          }}
        >
          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="caption" sx={{ color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase' }}>
                Pending Review
              </Typography>
              <PendingActionsIcon sx={{ color: '#FBBF24', fontSize: 20 }} />
            </Box>
            {loading ? (
              <Skeleton width="80%" height={32} sx={{ bgcolor: '#1E293B' }} />
            ) : (
              <Typography variant="h5" fontWeight={700} sx={{ color: '#FBBF24' }}>
                {kpis?.pending_approval_count || 0}
              </Typography>
            )}
            <Typography variant="caption" sx={{ color: '#64748B' }}>
              Actionable backlog
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* 5. Avg Approval Cycle Time */}
      <Grid item xs={12} sm={6} md={2.4}>
        <Card
          sx={{
            bgcolor: '#131B2A',
            border: '1px solid #1E293B',
            borderRadius: 2,
            transition: 'all 0.2s',
            '&:hover': { transform: 'translateY(-2px)', borderColor: '#34D399' },
          }}
        >
          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="caption" sx={{ color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase' }}>
                Cycle Time
              </Typography>
              <AccessTimeIcon sx={{ color: '#34D399', fontSize: 20 }} />
            </Box>
            {loading ? (
              <Skeleton width="80%" height={32} sx={{ bgcolor: '#1E293B' }} />
            ) : (
              <Typography variant="h5" fontWeight={700} sx={{ color: '#F8FAFC' }}>
                {kpis?.avg_cycle_time_hours || 0} hrs
              </Typography>
            )}
            <Typography variant="caption" sx={{ color: '#64748B' }}>
              Submission to decision
            </Typography>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
};
