import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Alert,
  Chip,
  Stack,
  Divider,
  CircularProgress,
  Container,
} from '@mui/material';
import BusinessIcon from '@mui/icons-material/Business';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { useAppDispatch, useAppSelector } from '../../app/store';
import { loginUser, clearAuthError } from './authSlice';

export const LoginPage: React.FC = () => {
  const dispatch = useAppDispatch();
  const { loading, error } = useAppSelector((state) => state.auth);

  const [email, setEmail] = useState('admin1@org1.example.com');
  const [password, setPassword] = useState('Passw0rd!');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    dispatch(loginUser({ email, password }));
  };

  const handlePresetSelect = (presetEmail: string) => {
    setEmail(presetEmail);
    setPassword('Passw0rd!');
    dispatch(clearAuthError());
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)',
        p: 2,
      }}
    >
      <Container maxWidth="sm">
        <Card
          sx={{
            borderRadius: 3,
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.4)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            backdropFilter: 'blur(10px)',
            background: '#1E293B',
            color: '#F8FAFC',
          }}
        >
          <CardContent sx={{ p: 4 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
              <BusinessIcon sx={{ color: '#38BDF8', fontSize: 32 }} />
              <Typography variant="h5" component="h1" fontWeight={700} sx={{ color: '#F8FAFC' }}>
                Blue Ocean CapEx
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ color: '#94A3B8', mb: 3 }}>
              Multi-Tenant Capital Expenditure & Workflow Approval Platform
            </Typography>

            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            <form onSubmit={handleSubmit}>
              <TextField
                fullWidth
                label="Corporate Email"
                variant="outlined"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                margin="normal"
                required
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#FFF',
                    '& fieldset': { borderColor: '#475569' },
                    '&:hover fieldset': { borderColor: '#38BDF8' },
                  },
                  '& .MuiInputLabel-root': { color: '#94A3B8' },
                }}
              />
              <TextField
                fullWidth
                label="Password"
                type="password"
                variant="outlined"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                margin="normal"
                required
                sx={{
                  '& .MuiOutlinedInput-root': {
                    color: '#FFF',
                    '& fieldset': { borderColor: '#475569' },
                    '&:hover fieldset': { borderColor: '#38BDF8' },
                  },
                  '& .MuiInputLabel-root': { color: '#94A3B8' },
                }}
              />

              <Button
                type="submit"
                fullWidth
                variant="contained"
                disabled={loading}
                startIcon={!loading && <LockOutlinedIcon />}
                sx={{
                  mt: 3,
                  mb: 2,
                  py: 1.3,
                  backgroundColor: '#0284C7',
                  '&:hover': { backgroundColor: '#0369A1' },
                  fontWeight: 600,
                  fontSize: '0.95rem',
                }}
              >
                {loading ? <CircularProgress size={24} color="inherit" /> : 'Sign In to Portal'}
              </Button>
            </form>

            <Divider sx={{ my: 3, borderColor: '#334155' }}>
              <Typography variant="caption" sx={{ color: '#64748B' }}>
                QUICK DEMO ROLES (CLICK TO POPULATE)
              </Typography>
            </Divider>

            <Stack spacing={1}>
              <Box
                onClick={() => handlePresetSelect('admin1@org1.example.com')}
                sx={{
                  p: 1.5,
                  borderRadius: 1.5,
                  bgcolor: '#0F172A',
                  cursor: 'pointer',
                  border: '1px solid #334155',
                  '&:hover': { borderColor: '#38BDF8', bgcolor: '#1E293B' },
                }}
              >
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Box>
                    <Typography variant="subtitle2" sx={{ color: '#F1F5F9' }}>
                      Organization Admin (Org 1)
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#94A3B8' }}>
                      admin1@org1.example.com • Full org portfolio view & approvals
                    </Typography>
                  </Box>
                  <Chip size="small" label="org_admin" color="primary" />
                </Stack>
              </Box>

              <Box
                onClick={() => handlePresetSelect('pm2@org1.example.com')}
                sx={{
                  p: 1.5,
                  borderRadius: 1.5,
                  bgcolor: '#0F172A',
                  cursor: 'pointer',
                  border: '1px solid #334155',
                  '&:hover': { borderColor: '#38BDF8', bgcolor: '#1E293B' },
                }}
              >
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Box>
                    <Typography variant="subtitle2" sx={{ color: '#F1F5F9' }}>
                      Property Manager (Scoped Properties)
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#94A3B8' }}>
                      pm2@org1.example.com • Scoped only to assigned properties
                    </Typography>
                  </Box>
                  <Chip size="small" label="property_manager" color="success" />
                </Stack>
              </Box>

              <Box
                onClick={() => handlePresetSelect('appr4@org1.example.com')}
                sx={{
                  p: 1.5,
                  borderRadius: 1.5,
                  bgcolor: '#0F172A',
                  cursor: 'pointer',
                  border: '1px solid #334155',
                  '&:hover': { borderColor: '#38BDF8', bgcolor: '#1E293B' },
                }}
              >
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Box>
                    <Typography variant="subtitle2" sx={{ color: '#F1F5F9' }}>
                      Workflow Approver
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#94A3B8' }}>
                      appr4@org1.example.com • Authorized for multi-level sign-offs
                    </Typography>
                  </Box>
                  <Chip size="small" label="approver" color="warning" />
                </Stack>
              </Box>

              <Box
                onClick={() => handlePresetSelect('view6@org1.example.com')}
                sx={{
                  p: 1.5,
                  borderRadius: 1.5,
                  bgcolor: '#0F172A',
                  cursor: 'pointer',
                  border: '1px solid #334155',
                  '&:hover': { borderColor: '#38BDF8', bgcolor: '#1E293B' },
                }}
              >
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Box>
                    <Typography variant="subtitle2" sx={{ color: '#F1F5F9' }}>
                      Viewer (Read-Only)
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#94A3B8' }}>
                      view6@org1.example.com • Read-only visibility
                    </Typography>
                  </Box>
                  <Chip size="small" label="viewer" sx={{ bgcolor: '#475569', color: '#FFF' }} />
                </Stack>
              </Box>
            </Stack>
          </CardContent>
        </Card>
      </Container>
    </Box>
  );
};
