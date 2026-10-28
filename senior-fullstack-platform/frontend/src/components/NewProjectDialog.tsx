import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Alert,
} from '@mui/material';
import { NewProjectPayload, Property } from '../types';
import { CATEGORIES, FISCAL_PERIODS } from '../constants';

interface NewProjectDialogProps {
  open: boolean;
  properties: Property[];
  onClose: () => void;
  onSubmit: (data: NewProjectPayload) => void;
}

export const NewProjectDialog: React.FC<NewProjectDialogProps> = ({
  open,
  properties,
  onClose,
  onSubmit,
}) => {
  const [title, setTitle] = useState('');
  const [propertyId, setPropertyId] = useState<number | ''>('');
  const [category, setCategory] = useState('HVAC');
  const [fiscalPeriod, setFiscalPeriod] = useState('FY2025');
  const [budgetAmount, setBudgetAmount] = useState('');
  const [actualCost, setActualCost] = useState('0.00');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError('Project title is required.');
      return;
    }
    if (!propertyId) {
      setError('Please select an authorized property.');
      return;
    }
    const budgetNum = parseFloat(budgetAmount);
    if (isNaN(budgetNum) || budgetNum <= 0) {
      setError('Budget amount must be strictly greater than $0.');
      return;
    }

    onSubmit({
      title: title.trim(),
      property: Number(propertyId),
      category,
      fiscal_period: fiscalPeriod,
      budget_amount: budgetAmount,
      actual_cost: actualCost || '0.00',
    });

    // Reset
    setTitle('');
    setPropertyId('');
    setBudgetAmount('');
    setActualCost('0.00');
    setError(null);
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
      <form onSubmit={handleSubmit}>
        <DialogTitle sx={{ fontWeight: 700 }}>Submit New Capital Spending Request</DialogTitle>
        <DialogContent>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Project Title"
                placeholder="e.g., Roof Replacement Phase 2"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
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
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth required>
                <InputLabel id="new-project-property-label" sx={{ color: '#94A3B8' }}>Target Property</InputLabel>
                <Select
                  labelId="new-project-property-label"
                  value={propertyId}
                  label="Target Property"
                  onChange={(e) => setPropertyId(Number(e.target.value))}
                  sx={{
                    color: '#FFF',
                    bgcolor: '#0F172A',
                    '& .MuiOutlinedInput-notchedOutline': { borderColor: '#334155' },
                  }}
                >
                  {properties.map((p) => (
                    <MenuItem key={p.id} value={p.id}>
                      {p.code} - {p.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth required>
                <InputLabel id="new-project-category-label" sx={{ color: '#94A3B8' }}>Asset Category</InputLabel>
                <Select
                  labelId="new-project-category-label"
                  value={category}
                  label="Asset Category"
                  onChange={(e) => setCategory(e.target.value)}
                  sx={{
                    color: '#FFF',
                    bgcolor: '#0F172A',
                    '& .MuiOutlinedInput-notchedOutline': { borderColor: '#334155' },
                  }}
                >
                  {CATEGORIES.map((c) => (
                    <MenuItem key={c} value={c}>
                      {c}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={4}>
              <FormControl fullWidth required>
                <InputLabel id="new-project-fiscal-label" sx={{ color: '#94A3B8' }}>Fiscal Period</InputLabel>
                <Select
                  labelId="new-project-fiscal-label"
                  value={fiscalPeriod}
                  label="Fiscal Period"
                  onChange={(e) => setFiscalPeriod(e.target.value)}
                  sx={{
                    color: '#FFF',
                    bgcolor: '#0F172A',
                    '& .MuiOutlinedInput-notchedOutline': { borderColor: '#334155' },
                  }}
                >
                  {FISCAL_PERIODS.map((fp) => (
                    <MenuItem key={fp} value={fp}>
                      {fp}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Budget Amount ($)"
                type="number"
                placeholder="125000"
                value={budgetAmount}
                onChange={(e) => setBudgetAmount(e.target.value)}
                required
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
            </Grid>

            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Actual Cost ($)"
                type="number"
                placeholder="0.00"
                value={actualCost}
                onChange={(e) => setActualCost(e.target.value)}
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
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={onClose} sx={{ color: '#94A3B8' }}>
            Cancel
          </Button>
          <Button type="submit" variant="contained" sx={{ bgcolor: '#0284C7', fontWeight: 600 }}>
            Create Project
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};
