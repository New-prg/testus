import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';

import type { DashboardPeriod, DashboardSummary, DashboardTimeseriesPoint, VehicleComparisonRow } from '../../api/dashboard';
import { getDashboardSummary, getDashboardTimeseries, getVehicleComparison } from '../../api/dashboard';
import type { FleetReport, ReportObjectType, VehicleReport } from '../../api/reports';
import { getFleetReport, getVehicleReport } from '../../api/reports';
import type { Vehicle } from '../../api/vehicles';
import { getVehicles } from '../../api/vehicles';

type DashboardData = {
  summary: DashboardSummary;
  timeseries: DashboardTimeseriesPoint[];
  comparison: VehicleComparisonRow[];
};

type ActiveReport = FleetReport | VehicleReport;

type AsyncState<T> = {
  data: T | null;
  error: string | null;
  isLoading: boolean;
  loadedAt: number | null;
};

type ReportParams = {
  objectType: ReportObjectType;
  period: DashboardPeriod;
  vehicleId?: string;
};

type RouteDataContextValue = {
  dashboardCache: Record<string, AsyncState<DashboardData>>;
  vehiclesState: AsyncState<Vehicle[]>;
  reportsCache: Record<string, AsyncState<ActiveReport>>;
  ensureDashboard: (period: DashboardPeriod, options?: { force?: boolean }) => Promise<DashboardData | null>;
  ensureVehicles: (options?: { force?: boolean }) => Promise<Vehicle[]>;
  ensureReport: (params: ReportParams, options?: { force?: boolean }) => Promise<ActiveReport | null>;
  getReportKey: (params: ReportParams) => string;
};

const defaultAsyncState = <T,>(): AsyncState<T> => ({
  data: null,
  error: null,
  isLoading: false,
  loadedAt: null,
});

const RouteDataContext = createContext<RouteDataContextValue | undefined>(undefined);

function reportKey({ objectType, period, vehicleId }: ReportParams): string {
  return objectType === 'vehicle' ? `${objectType}:${period}:${vehicleId ?? ''}` : `${objectType}:${period}`;
}

export function RouteDataProvider({ children }: { children: React.ReactNode }) {
  const [dashboardCache, setDashboardCache] = useState<Record<string, AsyncState<DashboardData>>>({});
  const [vehiclesState, setVehiclesState] = useState<AsyncState<Vehicle[]>>(defaultAsyncState<Vehicle[]>());
  const [reportsCache, setReportsCache] = useState<Record<string, AsyncState<ActiveReport>>>({});

  const dashboardCacheRef = useRef(dashboardCache);
  const vehiclesStateRef = useRef(vehiclesState);
  const reportsCacheRef = useRef(reportsCache);

  dashboardCacheRef.current = dashboardCache;
  vehiclesStateRef.current = vehiclesState;
  reportsCacheRef.current = reportsCache;

  const inflightDashboard = useRef(new Map<string, Promise<DashboardData | null>>());
  const inflightReports = useRef(new Map<string, Promise<ActiveReport | null>>());
  const inflightVehicles = useRef<Promise<Vehicle[]> | null>(null);

  const ensureDashboard = useCallback(async (period: DashboardPeriod, options?: { force?: boolean }) => {
    const force = options?.force ?? false;
    const cached = dashboardCacheRef.current[period];
    if (!force && cached?.data) {
      return cached.data;
    }

    const pending = inflightDashboard.current.get(period);
    if (!force && pending) {
      return pending;
    }

    setDashboardCache((current) => ({
      ...current,
      [period]: {
        data: current[period]?.data ?? null,
        error: null,
        isLoading: true,
        loadedAt: current[period]?.loadedAt ?? null,
      },
    }));

    const request = Promise.all([
      getDashboardSummary(period),
      getDashboardTimeseries(period),
      getVehicleComparison(period),
    ])
      .then(([summary, timeseries, comparison]) => {
        if (!timeseries.length && !comparison.length && (summary.vehicles_count ?? 0) === 0) {
          setDashboardCache((current) => ({
            ...current,
            [period]: { data: null, error: null, isLoading: false, loadedAt: null },
          }));
          return null;
        }
        const data = { summary, timeseries, comparison };
        setDashboardCache((current) => ({
          ...current,
          [period]: { data, error: null, isLoading: false, loadedAt: Date.now() },
        }));
        return data;
      })
      .catch((error: unknown) => {
        setDashboardCache((current) => ({
          ...current,
          [period]: {
            data: current[period]?.data ?? null,
            error: error instanceof Error ? error.message : 'Не удалось загрузить данные панели мониторинга.',
            isLoading: false,
            loadedAt: current[period]?.loadedAt ?? null,
          },
        }));
        return null;
      })
      .finally(() => {
        inflightDashboard.current.delete(period);
      });

    inflightDashboard.current.set(period, request);
    return request;
  }, []);

  const ensureVehicles = useCallback(async (options?: { force?: boolean }) => {
    const force = options?.force ?? false;
    if (!force && vehiclesStateRef.current.data) {
      return vehiclesStateRef.current.data;
    }

    if (!force && inflightVehicles.current) {
      return inflightVehicles.current;
    }

    setVehiclesState((current) => ({ ...current, error: null, isLoading: true }));

    const request = getVehicles()
      .then((data) => {
        if (!data.length) {
          setVehiclesState({ data: null, error: null, isLoading: false, loadedAt: null });
          return [];
        }
        setVehiclesState({ data, error: null, isLoading: false, loadedAt: Date.now() });
        return data;
      })
      .catch((error: unknown) => {
        setVehiclesState((current) => ({
          data: current.data,
          error: error instanceof Error ? error.message : 'Не удалось загрузить список машин.',
          isLoading: false,
          loadedAt: current.loadedAt,
        }));
        return vehiclesStateRef.current.data ?? [];
      })
      .finally(() => {
        inflightVehicles.current = null;
      });

    inflightVehicles.current = request;
    return request;
  }, []);

  const ensureReport = useCallback(async (params: ReportParams, options?: { force?: boolean }) => {
    const force = options?.force ?? false;
    let resolvedVehicleId = params.vehicleId;

    if (params.objectType === 'vehicle' && !resolvedVehicleId) {
      const vehicles = await ensureVehicles();
      resolvedVehicleId = vehicles[0]?.id;
      if (!resolvedVehicleId) {
        return null;
      }
    }

    const key = reportKey({ ...params, vehicleId: resolvedVehicleId });
    const cached = reportsCacheRef.current[key];
    if (!force && cached?.data) {
      return cached.data;
    }

    const pending = inflightReports.current.get(key);
    if (!force && pending) {
      return pending;
    }

    setReportsCache((current) => ({
      ...current,
      [key]: {
        data: current[key]?.data ?? null,
        error: null,
        isLoading: true,
        loadedAt: current[key]?.loadedAt ?? null,
      },
    }));

    const request = (params.objectType === 'fleet'
      ? getFleetReport(params.period)
      : getVehicleReport(resolvedVehicleId!, params.period)
    )
      .then((data) => {
        setReportsCache((current) => ({
          ...current,
          [key]: { data, error: null, isLoading: false, loadedAt: Date.now() },
        }));
        return data;
      })
      .catch((error: unknown) => {
        setReportsCache((current) => ({
          ...current,
          [key]: {
            data: current[key]?.data ?? null,
            error: error instanceof Error ? error.message : 'Не удалось загрузить отчёт.',
            isLoading: false,
            loadedAt: current[key]?.loadedAt ?? null,
          },
        }));
        return null;
      })
      .finally(() => {
        inflightReports.current.delete(key);
      });

    inflightReports.current.set(key, request);
    return request;
  }, [ensureVehicles]);

  const value = useMemo<RouteDataContextValue>(
    () => ({
      dashboardCache,
      vehiclesState,
      reportsCache,
      ensureDashboard,
      ensureVehicles,
      ensureReport,
      getReportKey: reportKey,
    }),
    [dashboardCache, ensureDashboard, ensureReport, ensureVehicles, reportsCache, vehiclesState],
  );

  return <RouteDataContext.Provider value={value}>{children}</RouteDataContext.Provider>;
}

export function useRouteData() {
  const context = useContext(RouteDataContext);
  if (!context) {
    throw new Error('useRouteData must be used inside RouteDataProvider');
  }
  return context;
}
