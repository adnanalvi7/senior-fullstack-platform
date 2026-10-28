import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  CircularProgress,
  Chip,
  Stack,
} from '@mui/material';

import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import { Project, ApprovalEvent } from '../types';
import { apiClient } from '../app/api';

interface HistoryDialogProps {
  open: boolean;
  project: Project | null;
  onClose: () => void;
}

export const HistoryDialog: React.FC<HistoryDialogProps> = ({ open, project, onClose }) => {
  const [events, setEvents] = useState<ApprovalEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (open && project) {
      setLoading(true);
      apiClient
        .get<ApprovalEvent[]>(`/projects/${project.id}/history/`)
        .then((res) => {
          setEvents(res.data);
          setLoading(false);
        })
        .catch(() => {
          setEvents([]);
          setLoading(false);
        });
    }
  }, [open, project]);

  if (!project) return null;

  const formatDate = (isoStr: string) => {
    try {
      return new Date(isoStr).toLocaleString();
    } catch {
      return isoStr;
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: '#1E293B',
          color: '#F8FAFC',
          border: '1px solid #334155',
          borderRadius: 2,
        },
      }}
    >
      <DialogTitle sx={{ fontWeight: 700 }}>
        Approval Audit Trail • #{project.id} {project.title}
      </DialogTitle>
      <DialogContent>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={32} sx={{ color: '#38BDF8' }} />
          </Box>
        ) : events.length === 0 ? (
          <Typography variant="body2" sx={{ color: '#94A3B8', py: 3, textAlign: 'center' }}>
            No approval transitions recorded yet (Project in Draft status).
          </Typography>
        ) : (
          <Stack spacing={2} sx={{ py: 1 }}>
            {events.map((evt, idx) => (
              <Box
                key={evt.id || idx}
                sx={{
                  p: 2,
                  bgcolor: '#0F172A',
                  borderRadius: 1.5,
                  border: '1px solid #334155',
                }}
              >
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <CheckCircleOutlineIcon sx={{ color: '#38BDF8', fontSize: 18 }} />
                    <Typography variant="subtitle2" fontWeight={600} sx={{ color: '#F1F5F9' }}>
                      {evt.from_status} → {evt.to_status}
                    </Typography>
                  </Stack>
                  <Chip
                    label={evt.to_status}
                    size="small"
                    color={
                      evt.to_status === 'approved'
                        ? 'success'
                        : evt.to_status === 'rejected'
                        ? 'error'
                        : 'info'
                    }
                    sx={{ height: 20, fontSize: '0.7rem' }}
                  />
                </Stack>

                <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block' }}>
                  Actor: <strong>{evt.actor_email || 'System / Auto'}</strong> • {formatDate(evt.created_at)}
                </Typography>

                {evt.notes && (
                  <Box sx={{ mt: 1, p: 1, bgcolor: '#1E293B', borderRadius: 1, borderLeft: '3px solid #38BDF8' }}>
                    <Typography variant="caption" sx={{ color: '#CBD5E1', fontStyle: 'italic' }}>
                      "{evt.notes}"
                    </Typography>
                  </Box>
                )}
              </Box>
            ))}
          </Stack>
        )}
      </DialogContent>
      <DialogActions sx={{ p: 2 }}>
        <Button onClick={onClose} variant="contained" sx={{ bgcolor: '#0284C7' }}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};
