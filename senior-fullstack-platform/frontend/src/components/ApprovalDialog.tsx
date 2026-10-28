import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Typography,
  Box,
  Alert,
} from '@mui/material';
import { Project } from '../types';
import { WorkflowAction } from '../features/projects/workflow';

interface ApprovalDialogProps {
  open: boolean;
  project: Project | null;
  action: WorkflowAction;
  onClose: () => void;
  onConfirm: (projectId: number, action: WorkflowAction, notes: string) => void;
}

const ACTION_DESCRIPTIONS: Record<WorkflowAction, { title: string; desc: string; color: 'primary' | 'warning' | 'error' | 'success' | 'info' }> = {
  submit: {
    title: 'Submit Project for Manager Review',
    desc: 'This will lock project parameters and move the request into the manager review queue.',
    color: 'info',
  },
  manager_approve: {
    title: 'Manager Approval Sign-Off',
    desc: 'Verify that this CapEx spending request aligns with property operational priorities and advance to finance review.',
    color: 'warning',
  },
  finance_approve: {
    title: 'Finance Review Sign-Off',
    desc: 'Verify fiscal period allocation, capital limits, and advance to final authorization.',
    color: 'primary',
  },
  final_approve: {
    title: 'Final Executive Approval',
    desc: 'Grant definitive capital authorization for project execution.',
    color: 'success',
  },
  reject: {
    title: 'Reject CapEx Spending Request',
    desc: 'Reject this project. It will be returned with your rejection notes.',
    color: 'error',
  },
};

export const ApprovalDialog: React.FC<ApprovalDialogProps> = ({
  open,
  project,
  action,
  onClose,
  onConfirm,
}) => {
  const [notes, setNotes] = useState('');

  if (!project) return null;

  const config = ACTION_DESCRIPTIONS[action] || {
    title: 'Confirm Workflow Action',
    desc: 'Confirm status transition.',
    color: 'primary',
  };

  const handleConfirm = () => {
    onConfirm(project.id, action, notes);
    setNotes('');
    onClose();
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
      <DialogTitle sx={{ fontWeight: 700, pb: 1 }}>{config.title}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ color: '#94A3B8', mb: 2 }}>
          {config.desc}
        </Typography>

        <Box sx={{ p: 2, bgcolor: '#0F172A', borderRadius: 1.5, mb: 2, border: '1px solid #334155' }}>
          <Typography variant="subtitle2" sx={{ color: '#F1F5F9' }}>
            #{project.id} - {project.title}
          </Typography>
          <Typography variant="caption" sx={{ color: '#94A3B8', display: 'block' }}>
            Property: {project.property_code} • Current Status: <strong>{project.status}</strong>
          </Typography>
          <Typography variant="caption" sx={{ color: '#38BDF8', display: 'block' }}>
            Budget: ${parseFloat(project.budget_amount).toLocaleString()}
          </Typography>
        </Box>

        {action === 'reject' && (
          <Alert severity="warning" sx={{ mb: 2, bgcolor: 'rgba(245, 158, 11, 0.1)', color: '#FCD34D' }}>
            Please provide a justification for this rejection below.
          </Alert>
        )}

        <TextField
          fullWidth
          multiline
          rows={3}
          label="Notes / Comments (Optional)"
          placeholder="Add review notes, budget justification, or audit comments..."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          sx={{
            '& .MuiOutlinedInput-root': {
              color: '#FFF',
              bgcolor: '#0F172A',
              '& fieldset': { borderColor: '#334155' },
              '&:hover fieldset': { borderColor: '#38BDF8' },
            },
            '& .MuiInputLabel-root': { color: '#94A3B8' },
          }}
        />
      </DialogContent>
      <DialogActions sx={{ p: 2.5, pt: 0 }}>
        <Button onClick={onClose} sx={{ color: '#94A3B8' }}>
          Cancel
        </Button>
        <Button
          variant="contained"
          color={config.color}
          onClick={handleConfirm}
          sx={{ fontWeight: 600, px: 3 }}
        >
          Confirm Action
        </Button>
      </DialogActions>
    </Dialog>
  );
};
