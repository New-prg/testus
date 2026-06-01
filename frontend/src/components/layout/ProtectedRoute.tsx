import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { LoadingState } from '../cards/StateViews';
import { useAuth } from './AuthProvider';

export function ProtectedRoute() {
  const { isAuthenticated, isBootstrapping } = useAuth();
  const location = useLocation();

  if (isBootstrapping) {
    return <LoadingState message="Проверяем авторизацию..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
