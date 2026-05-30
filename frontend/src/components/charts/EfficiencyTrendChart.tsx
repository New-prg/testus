import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import type { DashboardTimeseriesPoint } from '../../api/dashboard';
import { chartPalette, tokenColor } from './chartTheme';

type EfficiencyTrendChartProps = {
  points: DashboardTimeseriesPoint[];
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', { month: 'short', day: 'numeric' }).format(new Date(value));
}

function percent(value: number): number {
  return Number((value * 100).toFixed(1));
}

function chartTooltipStyle() {
  return {
    background: tokenColor('--color-panel-strong', 0.96),
    border: `1px solid ${chartPalette.line}`,
    borderRadius: 'var(--radius-card)',
    color: chartPalette.cream,
  };
}

export function EfficiencyTrendChart({ points }: EfficiencyTrendChartProps) {
  const data = [...points]
    .sort((left, right) => left.date.localeCompare(right.date))
    .map((point) => ({
      date: formatDate(point.date),
      rating: Number(point.rating.toFixed(1)),
      readiness: Number(point.analytics_readiness_percent.toFixed(1)),
      fuel: Number(point.fuel_per_100km.toFixed(1)),
      idle: percent(point.idle_ratio),
      coasting: percent(point.coasting_ratio),
      overspeed: percent(point.overspeed_ratio),
    }));

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <div className="surface-card p-5">
        <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="section-label">Временной ряд</p>
            <h2 className="mt-2 font-display text-2xl text-cream">Рейтинг и готовность</h2>
          </div>
          <p className="text-sm text-muted">Период: неделя</p>
        </div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="ratingFill" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="5%" stopColor={chartPalette.signal} stopOpacity={0.34} />
                  <stop offset="95%" stopColor={chartPalette.signal} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={chartPalette.line} vertical={false} />
              <XAxis dataKey="date" tick={{ fill: chartPalette.muted, fontSize: 12 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: chartPalette.muted, fontSize: 12 }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={chartTooltipStyle()} />
              <Area type="monotone" dataKey="rating" name="Рейтинг автопарка" stroke={chartPalette.signal} fill="url(#ratingFill)" strokeWidth={3} />
              <Area type="monotone" dataKey="readiness" name="Готовность %" stroke={chartPalette.success} fill="transparent" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="surface-card p-5">
        <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="section-label">Поведение эффективности</p>
            <h2 className="mt-2 font-display text-2xl text-cream">Топливо, простой и накат</h2>
          </div>
          <p className="text-sm text-muted">Чем ниже расход и простой, тем лучше</p>
        </div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="fuelFill" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="5%" stopColor={chartPalette.brass} stopOpacity={0.28} />
                  <stop offset="95%" stopColor={chartPalette.brass} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={chartPalette.line} vertical={false} />
              <XAxis dataKey="date" tick={{ fill: chartPalette.muted, fontSize: 12 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: chartPalette.muted, fontSize: 12 }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={chartTooltipStyle()} />
              <Area type="monotone" dataKey="fuel" name="Топливо / 100 км" stroke={chartPalette.brass} fill="url(#fuelFill)" strokeWidth={3} />
              <Area type="monotone" dataKey="idle" name="Простой %" stroke={chartPalette.ember} fill="transparent" strokeWidth={2} />
              <Area type="monotone" dataKey="coasting" name="Накат %" stroke={chartPalette.signal} fill="transparent" strokeWidth={2} />
              <Area type="monotone" dataKey="overspeed" name="Превышение %" stroke={chartPalette.danger} fill="transparent" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
