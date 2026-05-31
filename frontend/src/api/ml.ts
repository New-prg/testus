import { apiFetch } from './client';

export type MlMetricSummary = {
  name: string;
  value: number | null;
};

export type MlModelRun = {
  id: string;
  run_type: string;
  model_name: string;
  model: string;
  display_name: string;
  status: string;
  row_count: number;
  feature_names: string[];
  metrics: Record<string, unknown>;
  metrics_summary: MlMetricSummary[];
  parameters: Record<string, unknown>;
  created_at: string;
};

export type MlFeatureRow = {
  vehicle_id: string;
  period_start: string;
  period_end: string;
  features: Record<string, number | null>;
  target_final_rating: number | null;
  baseline: {
    final_rating: number | null;
  };
  interpretation: {
    warnings: string[];
    positive_factors: string[];
    negative_factors: string[];
  };
};

export type MlAnomalyFactor = {
  feature: string;
  feature_label_ru: string;
  value: number;
  fleet_median: number;
  fleet_mean: number;
  difference_from_median: number;
  message_ru: string;
};

export type MlAnomalyExplanation = {
  top_factors: MlAnomalyFactor[];
  summary_ru: string;
  baseline_final_rating: number | null;
  negative_factors: string[];
};

export type MlAnomalyResult = MlFeatureRow & {
  model_name: string;
  score: number;
  label: 'anomaly' | 'normal' | string;
  explanation: MlAnomalyExplanation;
};

export type MlClusterProfile = {
  code: string;
  description_ru: string;
  feature_averages: Record<string, number>;
};

export type MlClusterResult = MlFeatureRow & {
  model_name: string;
  cluster_id: number;
  cluster: string;
  profile: MlClusterProfile;
  profile_description_ru: string;
};

export type MlForecastResult = {
  vehicle_id: string;
  period_start: string;
  period_end: string;
  model_name: string;
  moving_average_forecast: number;
  random_forest_forecast: number;
  baseline_final_rating: number | null;
  history_points: number;
};

export type MlResultsResponse<T> = {
  message?: string;
  model_name?: string;
  feature_names?: string[];
  preprocessing?: Record<string, unknown>;
  metrics?: Record<string, unknown>;
  profiles?: Record<string, MlClusterProfile>;
  results: T[];
};

export type MlModelComparisonResponse = {
  results: MlModelRun[];
};

export type MlRecalculateResponse = {
  anomalies: MlResultsResponse<MlAnomalyResult>;
  clusters: MlResultsResponse<MlClusterResult>;
  forecasts: MlResultsResponse<MlForecastResult>;
};

export type MlVehicleExplanations = {
  vehicle_id: string;
  results: Partial<{
    anomaly: MlAnomalyResult[];
    cluster: MlClusterResult[];
    forecast: MlForecastResult[];
  }>;
};

export function recalculateMl(limit = 500): Promise<MlRecalculateResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  return apiFetch<MlRecalculateResponse>(`/ml/recalculate?${params.toString()}`, { method: 'POST' });
}

export function getMlModelComparison(limit = 20): Promise<MlModelComparisonResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  return apiFetch<MlModelComparisonResponse>(`/ml/model-comparison?${params.toString()}`);
}

export function getMlAnomalies(): Promise<MlResultsResponse<MlAnomalyResult>> {
  return apiFetch<MlResultsResponse<MlAnomalyResult>>('/ml/anomalies');
}

export function getMlClusters(): Promise<MlResultsResponse<MlClusterResult>> {
  return apiFetch<MlResultsResponse<MlClusterResult>>('/ml/clusters');
}

export function getMlForecasts(): Promise<MlResultsResponse<MlForecastResult>> {
  return apiFetch<MlResultsResponse<MlForecastResult>>('/ml/forecasts');
}

export function getMlVehicleExplanations(vehicleId: string): Promise<MlVehicleExplanations> {
  return apiFetch<MlVehicleExplanations>(`/ml/explanations/${encodeURIComponent(vehicleId)}`);
}
