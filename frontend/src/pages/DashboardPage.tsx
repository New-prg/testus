import { useEffect } from 'react';

import type { DashboardMetricScores, DashboardPeriod, ProblemVehicle } from '../api/dashboard';
import { KpiCard } from '../components/cards/KpiCard';
import { EmptyState, ErrorState, LoadingState } from '../components/cards/StateViews';
import { ComparisonBarChart } from '../components/charts/ComparisonBarChart';
import { EfficiencyTrendChart } from '../components/charts/EfficiencyTrendChart';
import { ComparisonTable } from '../components/tables/ComparisonTable';
import { useRouteData } from '../components/layout/RouteDataProvider';

const period: DashboardPeriod = 'week';

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function clampScore(value: number): number {
  return Math.max(0, Math.min(10, value));
}

function scoreText(value: number): string {
  return `${clampScore(value).toFixed(1)}/10`;
}

function metricScore(summary: { metric_scores?: DashboardMetricScores }, key: keyof DashboardMetricScores): number {
  return summary.metric_scores?.[key] ?? 0;
}

function metricDelta(summary: { metric_score_changes?: DashboardMetricScores }, key: keyof DashboardMetricScores): number {
  return summary.metric_score_changes?.[key] ?? 0;
}

function ProblemVehicleCard({ vehicle, label }: { vehicle: ProblemVehicle; label: 'Best' | 'Worst' }) {
  const isWorst = label === 'Worst';
  const localizedLabel = isWorst ? 'Проблемная' : 'Лучшая';
  return (
    <article className={`rounded-3xl border p-4 ${isWorst ? 'border-danger/35 bg-danger/10' : 'border-success/35 bg-success/10'}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-muted">{localizedLabel} машина</p>
          <h3 className="mt-2 text-lg font-bold text-cream">{vehicle.plate_number}</h3>
          <p className="text-sm text-muted">{vehicle.name} · {vehicle.vehicle_type}</p>
        </div>
        <span className={`rounded-pill px-3 py-1 text-xs font-bold ${vehicle.anomaly_flag ? 'bg-danger text-cream' : 'bg-success text-ink'}`}>
          {vehicle.anomaly_flag ? 'Аномалия' : 'Стабильно'}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
        <div>
          <p className="text-muted">Рейтинг</p>
          <p className="font-bold text-signal">{vehicle.rating.toFixed(1)}</p>
        </div>
        <div>
          <p className="text-muted">Топливо</p>
          <p className="font-bold text-brass">{vehicle.fuel_per_100km.toFixed(1)} L</p>
        </div>
        <div>
          <p className="text-muted">Простой</p>
          <p className="font-bold text-cream">{percent(vehicle.idle_ratio)}</p>
        </div>
      </div>
      {vehicle.anomaly_reasons.length ? (
        <ul className="mt-4 space-y-2 text-sm text-cream/80">
          {vehicle.anomaly_reasons.slice(0, 3).map((reason) => (
            <li key={reason}>• {reason}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

export function DashboardPage() {
  const { dashboardCache, ensureDashboard } = useRouteData();
  const dashboardState = dashboardCache[period] ?? { data: null, error: null, isLoading: false, loadedAt: null };
  const data = dashboardState.data;

  useEffect(() => {
    void ensureDashboard(period);
  }, [ensureDashboard]);

  if (dashboardState.isLoading && !data) {
    return <LoadingState message="Загружаем данные недельного дашборда..." />;
  }

  if (dashboardState.error && !data) {
    return <ErrorState title="Дашборд недоступен" message={dashboardState.error} action={<button className="secondary-action" type="button" onClick={() => void ensureDashboard(period, { force: true })}>Повторить</button>} />;
  }

  if (!data || (!data.timeseries.length && !data.comparison.length)) {
    return (
      <EmptyState
        title="Для недельного дашборда пока нет данных"
        message="Интерфейс использует /api/dashboard/summary, /timeseries, /comparison и /problem-vehicles с period=week. Выполните сидирование или расчёт аналитики, чтобы заполнить демо-данные."
        action={<button className="primary-action" type="button" onClick={() => void ensureDashboard(period, { force: true })}>Обновить дашборд</button>}
      />
    );
  }

  const bestVehicles = data.problemVehicles.best.slice(0, 2);
  const worstVehicles = data.problemVehicles.worst.slice(0, 2);
  const kpiCards: Array<{ label: string; score: string; actualValue: string; delta: number; tone: 'signal' | 'brass' | 'success' | 'warning' | 'danger' }> = [
    {
      label: 'Рейтинг автопарка',
      score: scoreText(metricScore(data.summary, 'fleet_rating')),
      actualValue: data.summary.fleet_rating.toFixed(1),
      delta: metricDelta(data.summary, 'fleet_rating'),
      tone: 'signal',
    },
    {
      label: 'Топливо / 100 км',
      score: scoreText(metricScore(data.summary, 'fuel_per_100km')),
      actualValue: `${data.summary.fuel_per_100km.toFixed(1)} л`,
      delta: metricDelta(data.summary, 'fuel_per_100km'),
      tone: 'brass',
    },
    {
      label: 'Доля простоя',
      score: scoreText(metricScore(data.summary, 'idle_ratio')),
      actualValue: percent(data.summary.idle_ratio),
      delta: metricDelta(data.summary, 'idle_ratio'),
      tone: data.summary.idle_ratio > 0.2 ? 'warning' : 'success',
    },
    {
      label: 'Готовность',
      score: scoreText(metricScore(data.summary, 'analytics_readiness_percent')),
      actualValue: `${data.summary.analytics_readiness_percent.toFixed(0)}%`,
      delta: metricDelta(data.summary, 'analytics_readiness_percent'),
      tone: 'success',
    },
    {
      label: 'Накат',
      score: scoreText(metricScore(data.summary, 'coasting_ratio')),
      actualValue: percent(data.summary.coasting_ratio),
      delta: metricDelta(data.summary, 'coasting_ratio'),
      tone: 'signal',
    },
    {
      label: 'Оптимальные обороты',
      score: scoreText(metricScore(data.summary, 'optimal_rpm_ratio')),
      actualValue: percent(data.summary.optimal_rpm_ratio),
      delta: metricDelta(data.summary, 'optimal_rpm_ratio'),
      tone: 'success',
    },
    {
      label: 'Торможения / 100 км',
      score: scoreText(metricScore(data.summary, 'brakes_per_100km')),
      actualValue: data.summary.brakes_per_100km.toFixed(1),
      delta: metricDelta(data.summary, 'brakes_per_100km'),
      tone: 'warning',
    },
    {
      label: 'Превышение скорости',
      score: scoreText(metricScore(data.summary, 'overspeed_ratio')),
      actualValue: percent(data.summary.overspeed_ratio),
      delta: metricDelta(data.summary, 'overspeed_ratio'),
      tone: data.summary.overspeed_ratio > 0.05 ? 'danger' : 'signal',
    },
  ];

  return (
    <div className="space-y-8 animate-reveal">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpiCards.slice(0, 4).map((card) => <KpiCard key={card.label} {...card} />)}
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpiCards.slice(4).map((card) => <KpiCard key={card.label} {...card} />)}
      </section>

      <EfficiencyTrendChart points={data.timeseries} />

      <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <ComparisonBarChart rows={data.comparison} />
        <div className="surface-card p-5">
          <p className="section-label">Лучшие и проблемные машины</p>
          <h2 className="mt-2 font-display text-2xl text-cream">Ключевые точки внимания</h2>
          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            {bestVehicles.map((vehicle) => <ProblemVehicleCard key={`best-${vehicle.vehicle_id}`} vehicle={vehicle} label="Best" />)}
            {worstVehicles.map((vehicle) => <ProblemVehicleCard key={`worst-${vehicle.vehicle_id}`} vehicle={vehicle} label="Worst" />)}
          </div>
        </div>
      </section>

      <ComparisonTable rows={data.comparison} />
    </div>
  );
}
