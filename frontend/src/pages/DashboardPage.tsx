import { useEffect } from 'react';

import type { DashboardMetricScores, DashboardPeriod } from '../api/dashboard';
import { KpiCard } from '../components/cards/KpiCard';
import { EmptyState, ErrorState, LoadingState } from '../components/cards/StateViews';
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
        message="Сейчас нет недельных данных. Загрузите демо-данные или пересчитайте аналитику."
        action={<button className="primary-action" type="button" onClick={() => void ensureDashboard(period, { force: true })}>Обновить дашборд</button>}
      />
    );
  }

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

      <ComparisonTable rows={data.comparison} />
    </div>
  );
}
