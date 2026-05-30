import { apiFetch, apiFetchBlob } from './client';
import type { DashboardPeriod, DashboardSummary, DashboardTimeseriesPoint, VehicleComparisonRow } from './dashboard';
import type { Vehicle } from './vehicles';

export type ReportObjectType = 'fleet' | 'vehicle';

export type ReportConclusion = {
  title: string;
  text: string;
  severity: 'positive' | 'warning' | 'critical' | 'neutral';
};

export type FleetReport = {
  period: DashboardPeriod | string;
  generated_at: string;
  summary: DashboardSummary;
  comparison: VehicleComparisonRow[];
  conclusions: ReportConclusion[];
};

export type VehicleReport = {
  period: DashboardPeriod | string;
  generated_at: string;
  vehicle: Vehicle;
  summary: VehicleComparisonRow;
  timeseries: DashboardTimeseriesPoint[];
  conclusions: ReportConclusion[];
};

function reportParams(period: DashboardPeriod): string {
  return new URLSearchParams({ period }).toString();
}

export function getFleetReport(period: DashboardPeriod = 'week'): Promise<FleetReport> {
  return apiFetch<FleetReport>(`/reports/fleet?${reportParams(period)}`);
}

export function getVehicleReport(vehicleId: string, period: DashboardPeriod = 'week'): Promise<VehicleReport> {
  return apiFetch<VehicleReport>(`/reports/vehicle/${vehicleId}?${reportParams(period)}`);
}

export function exportReportCsv(objectType: ReportObjectType, period: DashboardPeriod = 'week', vehicleId?: string): Promise<Blob> {
  const params = new URLSearchParams({ period, object_type: objectType });
  if (vehicleId) {
    params.set('vehicle_id', vehicleId);
  }
  return apiFetchBlob(`/reports/export/csv?${params.toString()}`);
}
