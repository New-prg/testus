import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type {
  MlAnomalyResult,
  MlClusterResult,
  MlForecastResult,
  MlModelRun,
  MlVehicleExplanations,
} from '../api/ml';
import {
  getMlAnomalies,
  getMlClusters,
  getMlForecasts,
  getMlModelComparison,
  getMlVehicleExplanations,
  recalculateMl,
} from '../api/ml';
import { ApiError } from '../api/client';
import { EmptyState, ErrorState, LoadingState } from '../components/cards/StateViews';
import { useAuth } from '../components/layout/AuthProvider';

type MlPageData = {
  runs: MlModelRun[];
  anomalies: MlAnomalyResult[];
  clusters: MlClusterResult[];
  forecasts: MlForecastResult[];
};

type ClusterSummary = {
  model_name: string;
  cluster_id: number;
  cluster: string;
  description: string;
  count: number;
  averageRating: number | null;
  featureAverages: Record<string, number>;
};

type ExplanationState = {
  data: MlVehicleExplanations | null;
  error: string | null;
  isLoading: boolean;
};

const emptyData: MlPageData = {
  runs: [],
  anomalies: [],
  clusters: [],
  forecasts: [],
};

const runTypeLabels: Record<string, string> = {
  anomaly: 'Аномалии',
  cluster: 'Кластеры',
  forecast: 'Прогноз',
};

const featureLabels: Record<string, string> = {
  distance_km: 'Пробег',
  fuel_consumed_liters: 'Топливо',
  fuel_per_100km: 'Расход / 100 км',
  coasting_ratio: 'Накат',
  optimal_rpm_ratio: 'Оптимальный RPM',
  idle_ratio: 'Простой',
  brakes_per_100km: 'Торможения / 100 км',
  high_speed_brakes_per_100km: 'Резкие торможения',
  cruise_control_ratio: 'Круиз-контроль',
  overspeed_ratio: 'Превышение скорости',
  engine_work_seconds: 'Работа двигателя',
  moving_seconds: 'Движение',
  idle_seconds: 'Холостой ход',
};

function hasData(data: MlPageData): boolean {
  return Boolean(data.runs.length || data.anomalies.length || data.clusters.length || data.forecasts.length);
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'short' }).format(date);
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '—';
  }
  return value.toFixed(digits);
}

function formatMetricValue(name: string, value: number | null): string {
  if (value === null) {
    return '—';
  }
  if (name.includes('ratio') || name.includes('percent')) {
    return `${(value * 100).toFixed(1)}%`;
  }
  return Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(3);
}

function formatFeatureValue(feature: string, value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '—';
  }
  if (feature.endsWith('_ratio')) {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (feature.endsWith('_seconds')) {
    return `${(value / 3600).toFixed(1)} ч`;
  }
  if (feature === 'distance_km') {
    return `${value.toFixed(1)} км`;
  }
  if (feature === 'fuel_consumed_liters') {
    return `${value.toFixed(1)} л`;
  }
  return value.toFixed(2);
}

function vehicleLabel(vehicleId: string): string {
  return `Машина ${vehicleId.slice(0, 8)}`;
}

function runTypeLabel(runType: string): string {
  return runTypeLabels[runType] ?? runType;
}

function statusLabel(status: string): string {
  if (status === 'success') {
    return 'готово';
  }
  if (status === 'skipped') {
    return 'пропущено';
  }
  return status;
}

function statusClasses(status: string): string {
  if (status === 'success') {
    return 'border-success/30 bg-success/10 text-success';
  }
  if (status === 'skipped') {
    return 'border-warning/35 bg-warning/10 text-warning';
  }
  return 'border-line/30 bg-panelStrong/70 text-muted';
}

function scoreWidth(value: number | null | undefined): string {
  const score = typeof value === 'number' && Number.isFinite(value) ? value : 0;
  return `${Math.max(0, Math.min(10, score)) * 10}%`;
}

function topClusterFeatures(features: Record<string, number>): Array<[string, number]> {
  return Object.entries(features)
    .filter(([, value]) => Number.isFinite(value))
    .sort(([leftKey], [rightKey]) => leftKey.localeCompare(rightKey))
    .slice(0, 4);
}

function buildClusterSummaries(clusters: MlClusterResult[]): ClusterSummary[] {
  const grouped = new Map<string, MlClusterResult[]>();
  clusters.forEach((cluster) => {
    const groupKey = `${cluster.model_name}:${cluster.cluster_id}`;
    const rows = grouped.get(groupKey) ?? [];
    rows.push(cluster);
    grouped.set(groupKey, rows);
  });

  return Array.from(grouped.entries())
    .map(([groupKey, rows]) => {
      const ratings = rows
        .map((row) => row.target_final_rating)
        .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
      const [modelName, clusterIdValue] = groupKey.split(':');
      const clusterId = Number(clusterIdValue);
      return {
        model_name: modelName,
        cluster_id: clusterId,
        cluster: rows[0]?.cluster ?? `cluster_${clusterId}`,
        description: rows[0]?.profile_description_ru ?? rows[0]?.profile.description_ru ?? 'Описание профиля не вернулось от ML-сервиса.',
        count: rows.length,
        averageRating: ratings.length ? ratings.reduce((total, value) => total + value, 0) / ratings.length : null,
        featureAverages: rows[0]?.profile.feature_averages ?? {},
      };
    })
    .sort((left, right) => left.cluster_id - right.cluster_id);
}

function ScoreBar({ label, value, tone = 'signal' }: { label: string; value: number | null | undefined; tone?: 'signal' | 'brass' | 'success' }) {
  const toneClass = tone === 'brass' ? 'bg-brass' : tone === 'success' ? 'bg-success' : 'bg-signal';
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3 text-xs font-bold uppercase tracking-widest text-muted">
        <span>{label}</span>
        <span className="text-cream">{formatNumber(value, 1)}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-pill bg-ink/45">
        <div className={`h-full rounded-pill ${toneClass}`} style={{ width: scoreWidth(value) }} />
      </div>
    </div>
  );
}

function LatestRunCard({ run }: { run: MlModelRun | undefined }) {
  return (
    <article className="rounded-3xl border border-signal/25 bg-signal/10 p-5">
      <p className="text-xs font-bold uppercase tracking-widest text-signal">Последний ML-запуск</p>
      {run ? (
        <>
          <h2 className="mt-3 font-display text-3xl text-cream">{run.display_name}</h2>
          <p className="mt-2 text-sm text-cream/80">{run.model_name} · {formatDateTime(run.created_at)}</p>
          <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-muted">Строк обучения</p>
              <p className="font-bold text-signal">{run.row_count}</p>
            </div>
            <div>
              <p className="text-muted">Признаков</p>
              <p className="font-bold text-brass">{run.feature_names.length}</p>
            </div>
          </div>
        </>
      ) : (
        <p className="mt-3 text-sm leading-6 text-cream/80">История запусков пуста. Нажмите «Пересчитать ML», чтобы добавить первые результаты.</p>
      )}
    </article>
  );
}

function ModelRunsSection({ runs }: { runs: MlModelRun[] }) {
  if (!runs.length) {
    return <EmptyBlock title="Запусков моделей пока нет" message="После пересчёта здесь появятся результаты по аномалиям, кластерам и прогнозам." />;
  }

  return (
    <section className="surface-card overflow-hidden">
      <div className="border-b border-line/25 p-5">
        <p className="section-label">Сравнение моделей</p>
        <h2 className="mt-2 font-display text-2xl text-cream">Последние ML-запуски</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Модель</th>
              <th>Статус</th>
              <th>Строки</th>
              <th>Метрики</th>
              <th>Создано</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line/20">
            {runs.slice(0, 10).map((run) => (
              <tr key={run.id} className="transition hover:bg-panelStrong/45">
                <td>
                  <p className="font-semibold text-cream">{run.display_name || runTypeLabel(run.run_type)}</p>
                  <p className="text-xs text-muted">{run.model_name}</p>
                </td>
                <td>
                  <span className={`rounded-pill border px-3 py-1 text-xs font-bold ${statusClasses(run.status)}`}>{statusLabel(run.status)}</span>
                </td>
                <td className="font-bold text-signal">{run.row_count}</td>
                <td>
                  {run.metrics_summary.length ? (
                    <div className="flex flex-wrap gap-2">
                      {run.metrics_summary.slice(0, 3).map((metric) => (
                        <span key={`${run.id}-${metric.name}`} className="rounded-pill border border-line/30 bg-panelStrong/60 px-3 py-1 text-xs text-cream/80">
                          {metric.name}: {formatMetricValue(metric.name, metric.value)}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
                </td>
                <td>{formatDateTime(run.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AnomaliesSection({ anomalies, onSelectVehicle }: { anomalies: MlAnomalyResult[]; onSelectVehicle: (vehicleId: string) => void }) {
  const visibleAnomalies = anomalies.filter((anomaly) => anomaly.label === 'anomaly');

  if (!visibleAnomalies.length) {
    return <EmptyBlock title="Аномалии не обнаружены" message="Отклонений нет или ML ещё не пересчитан." />;
  }

  return (
    <section className="surface-card p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="section-label">Аномалии</p>
          <h2 className="mt-2 font-display text-2xl text-cream">Объяснения отклонений</h2>
        </div>
        <p className="text-sm text-muted">Показаны только аномалии</p>
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        {visibleAnomalies.slice(0, 6).map((anomaly) => (
          <article key={`${anomaly.model_name}-${anomaly.vehicle_id}-${anomaly.period_start}`} className="rounded-3xl border border-danger/30 bg-danger/10 p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-danger">аномалия · {formatDate(anomaly.period_start)}</p>
                <h3 className="mt-2 text-lg font-bold text-cream">{vehicleLabel(anomaly.vehicle_id)}</h3>
              </div>
              <span className="rounded-pill border border-danger/35 bg-danger/20 px-3 py-1 text-xs font-bold text-danger">
                оценка {formatNumber(anomaly.score, 3)}
              </span>
            </div>
            <p className="mt-4 text-sm leading-6 text-cream/80">{anomaly.explanation.summary_ru}</p>
            <ul className="mt-4 space-y-2 text-sm text-cream/85">
              {anomaly.explanation.top_factors.slice(0, 3).map((factor) => (
                <li key={`${anomaly.vehicle_id}-${factor.feature}`} className="rounded-2xl border border-line/25 bg-ink/25 p-3">
                  {factor.message_ru}
                </li>
              ))}
              {!anomaly.explanation.top_factors.length && anomaly.explanation.negative_factors.slice(0, 3).map((reason) => (
                <li key={`${anomaly.vehicle_id}-${reason}`} className="rounded-2xl border border-line/25 bg-ink/25 p-3">
                  {reason}
                </li>
              ))}
            </ul>
            <button className="secondary-action mt-4" type="button" onClick={() => onSelectVehicle(anomaly.vehicle_id)}>
              Показать детализацию
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}

function ClustersSection({ clusters }: { clusters: ClusterSummary[] }) {
  if (!clusters.length) {
    return <EmptyBlock title="Кластеры пока не рассчитаны" message="После пересчёта здесь появятся профили поведения." />;
  }

  return (
    <section className="surface-card p-5">
      <p className="section-label">Кластерные профили</p>
      <h2 className="mt-2 font-display text-2xl text-cream">Сегменты поведения автопарка</h2>
      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        {clusters.map((cluster) => (
          <article key={`${cluster.model_name}:${cluster.cluster_id}`} className="rounded-3xl border border-line/30 bg-panelStrong/45 p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-brass">{cluster.model_name} · cluster {cluster.cluster_id}</p>
                <h3 className="mt-2 text-lg font-bold text-cream">{cluster.cluster}</h3>
              </div>
              <span className="rounded-pill border border-signal/25 bg-signal/10 px-3 py-1 text-xs font-bold text-signal">
                {cluster.count} строк
              </span>
            </div>
            <p className="mt-4 text-sm leading-6 text-cream/80">{cluster.description}</p>
            <div className="mt-4 space-y-3">
              <ScoreBar label="Средний рейтинг" value={cluster.averageRating} tone="success" />
              {topClusterFeatures(cluster.featureAverages).map(([feature, value]) => (
                <div key={`${cluster.cluster_id}-${feature}`} className="flex items-center justify-between gap-3 rounded-2xl border border-line/25 bg-ink/25 px-3 py-2 text-sm">
                  <span className="text-muted">{featureLabels[feature] ?? feature}</span>
                  <span className="font-bold text-cream">{formatFeatureValue(feature, value)}</span>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ForecastsSection({ forecasts }: { forecasts: MlForecastResult[] }) {
  if (!forecasts.length) {
    return <EmptyBlock title="Прогнозов пока нет" message="Нужна история рейтингов по нескольким окнам." />;
  }

  return (
    <section className="surface-card p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="section-label">Прогнозы по двум моделям</p>
          <h2 className="mt-2 font-display text-2xl text-cream">Факт и прогноз</h2>
        </div>
        <p className="text-sm text-muted">Прогнозы по двум моделям</p>
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
          {forecasts.slice(0, 6).map((forecast) => (
            <article key={`${forecast.vehicle_id}-${forecast.period_start}-${forecast.model_name}`} className="rounded-3xl border border-line/30 bg-panelStrong/45 p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-widest text-brass">{formatDate(forecast.period_start)} · {forecast.history_points} точек</p>
                <h3 className="mt-2 text-lg font-bold text-cream">{vehicleLabel(forecast.vehicle_id)}</h3>
              </div>
              <span className="rounded-pill border border-line/30 bg-ink/35 px-3 py-1 text-xs font-bold text-muted">{forecast.model_name}</span>
            </div>
            <div className="mt-5 space-y-4">
              <ScoreBar label="Факт" value={forecast.baseline_final_rating} tone="success" />
              <ScoreBar label="Прогноз: moving average" value={forecast.moving_average_forecast} tone="brass" />
              <ScoreBar label="Прогноз: random forest" value={forecast.random_forest_forecast} tone="signal" />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function VehicleExplanationPanel({ state, vehicleId }: { state: ExplanationState; vehicleId: string }) {
  if (!vehicleId) {
    return <EmptyBlock title="Выберите машину" message="Нажмите «Показать детализацию» в карточке аномалии." />;
  }

  if (state.isLoading) {
    return <LoadingState message="Загружаем объяснения..." />;
  }

  if (state.error) {
    return <ErrorState title="Не удалось загрузить объяснения" message={state.error} />;
  }

  const explanations = state.data;
  const anomaly = explanations?.results.anomaly?.find((row) => row.model_name === 'isolation_forest') ?? explanations?.results.anomaly?.[0];
  const cluster = explanations?.results.cluster?.find((row) => row.model_name === 'kmeans') ?? explanations?.results.cluster?.[0];
  const forecast = explanations?.results.forecast?.[0];

  return (
    <section className="surface-card p-5">
      <p className="section-label">Детализация по машине</p>
      <h2 className="mt-2 font-display text-2xl text-cream">{vehicleLabel(vehicleId)}</h2>
      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <article className="rounded-3xl border border-danger/25 bg-danger/10 p-4">
          <p className="text-xs font-bold uppercase tracking-widest text-danger">аномалия</p>
          <p className="mt-3 text-sm leading-6 text-cream/80">
            {anomaly?.explanation.top_factors[0]?.message_ru ?? anomaly?.explanation.summary_ru ?? 'Нет данных по аномалии.'}
          </p>
        </article>
        <article className="rounded-3xl border border-brass/25 bg-brass/10 p-4">
          <p className="text-xs font-bold uppercase tracking-widest text-brass">кластер</p>
          <h3 className="mt-3 font-bold text-cream">{cluster?.cluster ?? '—'}</h3>
          <p className="mt-2 text-sm leading-6 text-cream/80">{cluster?.profile_description_ru ?? 'Нет профиля кластера.'}</p>
        </article>
        <article className="rounded-3xl border border-signal/25 bg-signal/10 p-4">
          <p className="text-xs font-bold uppercase tracking-widest text-signal">прогноз</p>
          <p className="mt-3 text-sm leading-6 text-cream/80">
            Факт {formatNumber(forecast?.baseline_final_rating, 1)} · MA {formatNumber(forecast?.moving_average_forecast, 1)} · RF {formatNumber(forecast?.random_forest_forecast, 1)}
          </p>
        </article>
      </div>
    </section>
  );
}

function EmptyBlock({ title, message }: { title: string; message: string }) {
  return (
    <section className="surface-card p-5">
      <p className="section-label">Нет данных</p>
      <h2 className="mt-2 font-display text-2xl text-cream">{title}</h2>
      <p className="mt-3 text-sm leading-6 text-muted">{message}</p>
    </section>
  );
}

export function MlAnalyticsPage() {
  const { user } = useAuth();
  const [data, setData] = useState<MlPageData>(emptyData);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [selectedVehicleId, setSelectedVehicleId] = useState('');
  const [explanationState, setExplanationState] = useState<ExplanationState>({ data: null, error: null, isLoading: false });
  const loadRequestId = useRef(0);

  const loadMlData = useCallback(async () => {
    const requestId = loadRequestId.current + 1;
    loadRequestId.current = requestId;
    setIsLoading(true);
    setError(null);
    try {
      const [runsResponse, anomaliesResponse, clustersResponse, forecastsResponse] = await Promise.all([
        getMlModelComparison(),
        getMlAnomalies(),
        getMlClusters(),
          getMlForecasts(),
      ]);
      if (loadRequestId.current !== requestId) {
        return;
      }
      const nextData = {
        runs: runsResponse.results,
        anomalies: anomaliesResponse.results,
        clusters: clustersResponse.results,
        forecasts: forecastsResponse.results,
      };
      setData(nextData);
      const firstAnomaly = nextData.anomalies.find((row) => row.model_name === 'isolation_forest' && row.label === 'anomaly');
      const firstCluster = nextData.clusters.find((row) => row.model_name === 'kmeans');
      setSelectedVehicleId((current) => current || firstAnomaly?.vehicle_id || firstCluster?.vehicle_id || nextData.forecasts[0]?.vehicle_id || '');
    } catch (unknownError) {
      if (loadRequestId.current === requestId) {
        setError(unknownError instanceof Error ? unknownError.message : 'Не удалось загрузить ML-аналитику.');
      }
    } finally {
      if (loadRequestId.current === requestId) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadMlData();
  }, [loadMlData]);

  useEffect(() => {
    if (!selectedVehicleId) {
      setExplanationState({ data: null, error: null, isLoading: false });
      return;
    }

    let isActive = true;
    setExplanationState((current) => ({ ...current, error: null, isLoading: true }));
    getMlVehicleExplanations(selectedVehicleId)
      .then((response) => {
        if (isActive) {
          setExplanationState({ data: response, error: null, isLoading: false });
        }
      })
      .catch((unknownError: unknown) => {
        if (isActive) {
          setExplanationState({
            data: null,
            error: unknownError instanceof Error ? unknownError.message : 'Не удалось загрузить объяснение по машине.',
            isLoading: false,
          });
        }
      });

    return () => {
      isActive = false;
    };
  }, [selectedVehicleId]);

  const latestRun = data.runs[0];
  const preferredAnomalies = useMemo(
    () => data.anomalies.filter((anomaly) => anomaly.model_name === 'isolation_forest' && anomaly.label === 'anomaly'),
    [data.anomalies],
  );
  const preferredClusters = useMemo(() => data.clusters.filter((cluster) => cluster.model_name === 'kmeans'), [data.clusters]);
  const clusterSummaries = useMemo(() => buildClusterSummaries(preferredClusters), [preferredClusters]);
  const visibleAnomalyCount = preferredAnomalies.length;
  const hasAnyData = hasData(data);
  const canRecalculate = Boolean(user?.is_admin);

  async function handleRecalculate() {
    setIsRecalculating(true);
    setActionMessage(null);
    setError(null);
    try {
      const response = await recalculateMl();
      setActionMessage(
        `ML пересчитан: аномалии ${response.anomalies.results.length}, кластеры ${response.clusters.results.length}, прогнозы ${response.forecasts.results.length}.`,
      );
      await loadMlData();
    } catch (unknownError) {
      if (unknownError instanceof ApiError && unknownError.status === 403) {
        setError('Пересчёт ML доступен только администратору.');
      } else {
        setError(unknownError instanceof Error ? unknownError.message : 'Не удалось пересчитать ML-модели.');
      }
    } finally {
      setIsRecalculating(false);
    }
  }

  if (isLoading && !hasAnyData) {
    return <LoadingState message="Загружаем ML-аналитику..." />;
  }

  if (error && !hasAnyData) {
    return <ErrorState title="ML-аналитика недоступна" message={error} action={<button className="secondary-action" type="button" onClick={() => void loadMlData()}>Повторить</button>} />;
  }

  return (
    <div className="space-y-6 animate-reveal">
      <section className="surface-card p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-[1.25fr_0.75fr] lg:items-end">
          <div>
            <p className="section-label">ML-аналитика</p>
            <h1 className="mt-3 font-display text-4xl text-cream">Модели качества вождения</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
              Здесь собраны сравнение моделей, аномалии, кластеры и прогнозы по автопарку.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row lg:justify-end">
            {canRecalculate ? (
              <button className="primary-action" type="button" onClick={handleRecalculate} disabled={isRecalculating}>
                {isRecalculating ? 'Пересчитываем...' : 'Пересчитать ML'}
              </button>
            ) : (
              <button className="secondary-action" type="button" disabled>
                Только для администратора
              </button>
            )}
            <button className="secondary-action" type="button" onClick={() => void loadMlData()} disabled={isLoading || isRecalculating}>
              Обновить
            </button>
          </div>
        </div>
        {!canRecalculate ? <p className="mt-5 rounded-2xl border border-warning/35 bg-warning/10 px-4 py-3 text-sm text-warning">Пересчёт ML доступен только администратору. Остальные пользователи видят сохранённые результаты.</p> : null}
        {actionMessage ? <p className="mt-5 rounded-2xl border border-success/30 bg-success/10 px-4 py-3 text-sm text-success">{actionMessage}</p> : null}
      </section>

      {error ? <ErrorState title="Ошибка ML-действия" message={error} action={<button className="secondary-action" type="button" onClick={() => void loadMlData()}>Повторить загрузку</button>} /> : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <LatestRunCard run={latestRun} />
        <div className="surface-card p-5">
          <p className="section-label">Аномалии</p>
          <p className="mt-3 font-display text-4xl text-danger">{visibleAnomalyCount}</p>
          <p className="mt-2 text-sm text-muted">машин с аномалиями</p>
        </div>
        <div className="surface-card p-5">
          <p className="section-label">Кластеры</p>
          <p className="mt-3 font-display text-4xl text-brass">{clusterSummaries.length}</p>
          <p className="mt-2 text-sm text-muted">профилей поведения</p>
        </div>
        <div className="surface-card p-5">
          <p className="section-label">Прогнозы</p>
          <p className="mt-3 font-display text-4xl text-signal">{data.forecasts.length}</p>
          <p className="mt-2 text-sm text-muted">строк с прогнозом</p>
        </div>
      </section>

      {!hasAnyData ? (
        <EmptyState
          title="ML-результаты ещё не рассчитаны"
          message={canRecalculate ? 'Нажмите «Пересчитать ML», чтобы обновить модели и сохранить результаты для этой страницы.' : 'Здесь появятся сохранённые результаты после ML-пересчёта администратора.'}
          action={canRecalculate ? <button className="primary-action" type="button" onClick={handleRecalculate} disabled={isRecalculating}>{isRecalculating ? 'Пересчитываем...' : 'Пересчитать ML'}</button> : undefined}
        />
      ) : null}

      <ModelRunsSection runs={data.runs} />
      <AnomaliesSection anomalies={preferredAnomalies} onSelectVehicle={setSelectedVehicleId} />
      <ClustersSection clusters={clusterSummaries} />
      <ForecastsSection forecasts={data.forecasts} />
      <VehicleExplanationPanel state={explanationState} vehicleId={selectedVehicleId} />
    </div>
  );
}
