import { combineReducers, configureStore, UnknownAction } from '@reduxjs/toolkit';
import { TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux';
import authReducer, { logout } from '../features/auth/authSlice';
import analyticsReducer from '../features/analytics/analyticsSlice';
import projectsReducer from '../features/projects/projectsSlice';
import { setUnauthorizedHandler } from './api';

const appReducer = combineReducers({
  auth: authReducer,
  analytics: analyticsReducer,
  projects: projectsReducer,
});

// Logging out wipes *all* client state (filters, cached rows, notifications) so nothing from
// the previous user — or another tenant — survives into the next session.
const rootReducer = (state: ReturnType<typeof appReducer> | undefined, action: UnknownAction) =>
  appReducer(logout.match(action) ? undefined : state, action);

export const store = configureStore({ reducer: rootReducer });

setUnauthorizedHandler(() => {
  if (store.getState().auth.isAuthenticated) {
    store.dispatch(logout());
  }
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

export const useAppDispatch: () => AppDispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
