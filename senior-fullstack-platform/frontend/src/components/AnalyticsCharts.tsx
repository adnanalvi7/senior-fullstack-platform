import React from 'react';
import { Grid, Card, CardContent, Typography, Box, Skeleton } from '@mui/material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { CategorySpend, StatusDistribution } from '../types';

interface AnalyticsChartsProps {
  categorySpend?: CategorySpend[];
  statusDistribution?: StatusDistribution[];
  loading: boolean;
}

const STATUS_COLOR_MAP: Record<string, string> = {
  draft: '#64748B',
  submitted: '#38BDF8',
  manager_review: '#F59E0B',
  finance_review: '#8B5CF6',
  approved: '#10B981',
  rejected: '#EF4444',
};

const formatCurrency = (val: number) => {
  if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
  if (val >= 1000) return `$${(val / 1000).toFixed(0)}k`;
  return `$${val}`;
};

const EmptyChart: React.FC = () => (
  <Box
    sx={{
      height: 260,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      border: '1px dashed #334155',
      borderRadius: 1,
      color: '#64748B',
    }}
  >
    <Typography variant="body2">No projects in this scope yet.</Typography>
  </Box>
);

export const AnalyticsCharts: React.FC<AnalyticsChartsProps> = ({
  categorySpend = [],
  statusDistribution = [],
  loading,
}) => {
  return (
    <Grid container spacing={2} sx={{ mb: 3 }}>
      {/* Chart 1: Spend by Category */}
      <Grid item xs={12} md={7}>
        <Card sx={{ bgcolor: '#131B2A', border: '1px solid #1E293B', borderRadius: 2 }}>
          <CardContent>
            <Typography variant="subtitle1" fontWeight={600} sx={{ color: '#F8FAFC', mb: 0.5 }}>
              Expenditure by Asset Category
            </Typography>
            <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block', mb: 2 }}>
              Aggregated capital allocation across entitled properties
            </Typography>

            {loading ? (
              <Skeleton variant="rectangular" height={260} sx={{ bgcolor: '#1E293B', borderRadius: 1 }} />
            ) : categorySpend.length === 0 ? (
              <EmptyChart />
            ) : (
              <Box sx={{ width: '100%', height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={categorySpend} margin={{ top: 10, right: 10, left: -10, bottom: 25 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
                    <XAxis
                      dataKey="category"
                      stroke="#64748B"
                      fontSize={11}
                      tickLine={false}
                      angle={-25}
                      textAnchor="end"
                    />
                    <YAxis
                      stroke="#64748B"
                      fontSize={11}
                      tickLine={false}
                      tickFormatter={formatCurrency}
                    />
                    <Tooltip
                      formatter={(val: number) => [
                        new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val),
                        'Actual Spend',
                      ]}
                      contentStyle={{
                        backgroundColor: '#0F172A',
                        borderColor: '#334155',
                        borderRadius: 6,
                        color: '#F8FAFC',
                      }}
                    />
                    <Bar dataKey="actual_spend" fill="#0284C7" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            )}
          </CardContent>
        </Card>
      </Grid>

      {/* Chart 2: Status Pipeline Distribution */}
      <Grid item xs={12} md={5}>
        <Card sx={{ bgcolor: '#131B2A', border: '1px solid #1E293B', borderRadius: 2 }}>
          <CardContent>
            <Typography variant="subtitle1" fontWeight={600} sx={{ color: '#F8FAFC', mb: 0.5 }}>
              Approval Pipeline Status
            </Typography>
            <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block', mb: 2 }}>
              Distribution of projects across workflow lifecycle
            </Typography>

            {loading ? (
              <Skeleton variant="rectangular" height={260} sx={{ bgcolor: '#1E293B', borderRadius: 1 }} />
            ) : statusDistribution.length === 0 ? (
              <EmptyChart />
            ) : (
              <Box sx={{ width: '100%', height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    layout="vertical"
                    data={statusDistribution}
                    margin={{ top: 10, right: 20, left: 25, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" horizontal={false} />
                    <XAxis type="number" stroke="#64748B" fontSize={11} tickLine={false} />
                    <YAxis
                      type="category"
                      dataKey="status"
                      stroke="#64748B"
                      fontSize={11}
                      tickLine={false}
                      width={85}
                    />
                    <Tooltip
                      formatter={(val: number) => [val, 'Projects']}
                      contentStyle={{
                        backgroundColor: '#0F172A',
                        borderColor: '#334155',
                        borderRadius: 6,
                        color: '#F8FAFC',
                      }}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                      {statusDistribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={STATUS_COLOR_MAP[entry.status] || '#38BDF8'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            )}
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
};
