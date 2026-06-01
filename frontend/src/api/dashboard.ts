import { apiFetch } from './client';

export type DashboardPeriod = 'day' | 'week' | 'month' | 'quarter';

export type DashboardMetricScores = {
  fleet_rating: number;
  fuel_per_100km: number;
  idle_ratio: number;
  coasting_ratio: number;
  optimal_rpm_ratio: number;
  brakes_per_100km: number;
  overspeed_ratio: number;
  analytics_readiness_percent: number;
};

export type DashboardSummary = {
  period: DashboardPeriod | string;
  vehicles_count: number;
  fleet_rating: number;
  fuel_per_100km: number;
  idle_ratio: number;
  coasting_ratio: number;
  optimal_rpm_ratio: number;
  brakes_per_100km: number;
  high_speed_brakes_per_100km: number;
  cruise_control_ratio: number;
  overspeed_ratio: number;
  analytics_readiness_percent: number;
  anomaly_vehicles_count: number;
  metric_scores?: DashboardMetricScores;
  metric_score_changes?: DashboardMetricScores;
};

export type DashboardTimeseriesPoint = {
  date: string;
  rating: number;
  fuel_per_100km: number;
  idle_ratio: number;
  coasting_ratio: number;
  optimal_rpm_ratio: number;
  brakes_per_100km: number;
  high_speed_brakes_per_100km: number;
  cruise_control_ratio: number;
  overspeed_ratio: number;
  analytics_readiness_percent: number;
};

export type VehicleComparisonRow = {
  vehicle_id: string;
  plate_number: string;
  name: string;
  vehicle_type: string;
  rating: number;
  fuel_per_100km: number;
  idle_ratio: number;
  coasting_ratio: number;
  optimal_rpm_ratio: number;
  brakes_per_100km: number;
  high_speed_brakes_per_100km: number;
  cruise_control_ratio: number;
  overspeed_ratio: number;
  analytics_readiness_percent: number;
};

function periodParams(period: DashboardPeriod): string {
  return new URLSearchParams({ period }).toString();
}

export function getDashboardSummary(period: DashboardPeriod = 'week'): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>(`/dashboard/summary?${periodParams(period)}`);
}

export function getDashboardTimeseries(period: DashboardPeriod = 'week'): Promise<DashboardTimeseriesPoint[]> {
  return apiFetch<DashboardTimeseriesPoint[]>(`/dashboard/timeseries?${periodParams(period)}`);
}

export function getVehicleComparison(period: DashboardPeriod = 'week'): Promise<VehicleComparisonRow[]> {
  return apiFetch<VehicleComparisonRow[]>(`/dashboard/comparison?${periodParams(period)}`);
}
