import { apiFetch } from './client';

export type Vehicle = {
  id: string;
  plate_number: string;
  name: string;
  vehicle_type: string;
  imei: string;
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
  last_sync_at: string | null;
};

export function getVehicles(): Promise<Vehicle[]> {
  return apiFetch<Vehicle[]>('/vehicles');
}

export function getVehicle(vehicleId: string): Promise<Vehicle> {
  return apiFetch<Vehicle>(`/vehicles/${vehicleId}`);
}
