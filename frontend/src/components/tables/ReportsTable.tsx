import type { VehicleComparisonRow } from '../../api/dashboard';

type ReportsTableProps = {
  rows: VehicleComparisonRow[];
};

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function ReportsTable({ rows }: ReportsTableProps) {
  return (
    <div className="surface-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Объект</th>
              <th>Рейтинг</th>
              <th>Топливо / 100 км</th>
              <th>Простой</th>
              <th>Накат</th>
              <th>Оптимальный RPM</th>
              <th>Торможения</th>
              <th>Предугадывание</th>
              <th>Круиз-контроль</th>
              <th>Превышение</th>
              <th>Готовность</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line/20">
            {rows.map((row) => (
              <tr key={row.vehicle_id} className="transition hover:bg-panelStrong/45">
                <td>
                  <p className="font-semibold text-cream">{row.plate_number}</p>
                  <p className="text-xs text-muted">{row.name} · {row.vehicle_type}</p>
                </td>
                <td className="font-bold text-signal">{row.rating.toFixed(1)}</td>
                <td>{row.fuel_per_100km.toFixed(1)} л</td>
                <td>{percent(row.idle_ratio)}</td>
                <td>{percent(row.coasting_ratio)}</td>
                <td>{percent(row.optimal_rpm_ratio)}</td>
                <td>{row.brakes_per_100km.toFixed(1)}</td>
                <td>{row.high_speed_brakes_per_100km.toFixed(1)}</td>
                <td>{percent(row.cruise_control_ratio)}</td>
                <td>{percent(row.overspeed_ratio)}</td>
                <td>{row.analytics_readiness_percent.toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
