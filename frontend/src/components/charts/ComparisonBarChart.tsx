import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import type { VehicleComparisonRow } from '../../api/dashboard';
import { chartPalette, tokenColor } from './chartTheme';

type ComparisonBarChartProps = {
  rows: VehicleComparisonRow[];
};

export function ComparisonBarChart({ rows }: ComparisonBarChartProps) {
  const data = [...rows]
    .sort((left, right) => right.rating - left.rating)
    .slice(0, 8)
    .map((row) => ({
      vehicle: row.plate_number || row.name,
      rating: Number(row.rating.toFixed(1)),
      fuel: Number(row.fuel_per_100km.toFixed(1)),
      idle: Number((row.idle_ratio * 100).toFixed(1)),
    }));

  return (
    <div className="surface-card p-5">
      <div className="mb-6">
        <p className="section-label">Сравнение машин</p>
        <h2 className="mt-2 font-display text-2xl text-cream">Лучшие машины по рейтингу</h2>
      </div>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={chartPalette.line} vertical={false} />
            <XAxis dataKey="vehicle" tick={{ fill: chartPalette.muted, fontSize: 12 }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fill: chartPalette.muted, fontSize: 12 }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{
                background: tokenColor('--color-panel-strong', 0.96),
                border: `1px solid ${chartPalette.line}`,
                borderRadius: 'var(--radius-card)',
                color: chartPalette.cream,
              }}
            />
            <Bar dataKey="rating" name="Рейтинг" fill={chartPalette.signal} radius={[8, 8, 0, 0]} />
            <Bar dataKey="fuel" name="Топливо / 100 км" fill={chartPalette.brass} radius={[8, 8, 0, 0]} />
            <Bar dataKey="idle" name="Простой %" fill={chartPalette.ember} radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
