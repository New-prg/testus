import type { Vehicle } from '../../api/vehicles';

export type VehicleSortKey =
  | 'identity'
  | 'rating'
  | 'fuel_per_100km'
  | 'idle_ratio'
  | 'coasting_ratio'
  | 'optimal_rpm_ratio'
  | 'brakes_per_100km'
  | 'high_speed_brakes_per_100km'
  | 'cruise_control_ratio'
  | 'overspeed_ratio'
  | 'analytics_readiness_percent'
  | 'last_sync_at';
export type SortDirection = 'asc' | 'desc';

type VehiclesTableProps = {
  vehicles: Vehicle[];
  sortKey: VehicleSortKey;
  sortDirection: SortDirection;
  onSort: (key: VehicleSortKey) => void;
};

type SortableHeaderProps = {
  label: string;
  sortKey: VehicleSortKey;
  activeSortKey: VehicleSortKey;
  sortDirection: SortDirection;
  onSort: (key: VehicleSortKey) => void;
};

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function dateOrDash(value: string | null): string {
  if (!value) {
    return 'Не синхронизировано';
  }
  return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function ratingTone(rating: number): string {
  if (rating >= 85) {
    return 'text-success';
  }
  if (rating >= 70) {
    return 'text-signal';
  }
  if (rating >= 55) {
    return 'text-warning';
  }
  return 'text-danger';
}

function SortableHeader({ label, sortKey, activeSortKey, sortDirection, onSort }: SortableHeaderProps) {
  const isActive = sortKey === activeSortKey;

  return (
    <button
      className={`flex items-center gap-2 text-left transition hover:text-signal focus:outline-none focus:ring-2 focus:ring-signal/35 ${isActive ? 'text-signal' : ''}`}
      type="button"
      onClick={() => onSort(sortKey)}
      aria-sort={isActive ? (sortDirection === 'asc' ? 'ascending' : 'descending') : undefined}
    >
      {label}
      <span className={isActive ? 'text-signal' : 'text-muted/60'} aria-hidden>
        {isActive ? (sortDirection === 'asc' ? '↑' : '↓') : '↕'}
      </span>
    </button>
  );
}

export function VehiclesTable({ vehicles, sortKey, sortDirection, onSort }: VehiclesTableProps) {
  return (
    <div className="surface-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th><SortableHeader label="Номер / машина" sortKey="identity" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} /></th>
              <th>Тип / IMEI</th>
              <th>
                <SortableHeader label="Рейтинг" sortKey="rating" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
              </th>
              <th><SortableHeader label="Топливо" sortKey="fuel_per_100km" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} /></th>
              <th><SortableHeader label="Простой" sortKey="idle_ratio" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} /></th>
              <th><SortableHeader label="Накат" sortKey="coasting_ratio" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} /></th>
              <th><SortableHeader label="Оптимальные обороты" sortKey="optimal_rpm_ratio" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} /></th>
              <th><SortableHeader label="Торможения" sortKey="brakes_per_100km" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} /></th>
              <th><SortableHeader label="Резкие торможения" sortKey="high_speed_brakes_per_100km" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} /></th>
              <th><SortableHeader label="Круиз" sortKey="cruise_control_ratio" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} /></th>
              <th><SortableHeader label="Превышение" sortKey="overspeed_ratio" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} /></th>
              <th><SortableHeader label="Готовность" sortKey="analytics_readiness_percent" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} /></th>
              <th><SortableHeader label="Последняя синхронизация" sortKey="last_sync_at" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} /></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line/20">
            {vehicles.map((vehicle) => (
              <tr key={vehicle.id} className="transition hover:bg-panelStrong/45">
                <td>
                  <p className="font-semibold text-cream">{vehicle.plate_number}</p>
                  <p className="text-xs text-muted">{vehicle.name}</p>
                </td>
                <td>
                  <p>{vehicle.vehicle_type}</p>
                  <p className="text-xs text-muted">IMEI {vehicle.imei}</p>
                </td>
                <td className={`font-bold ${ratingTone(vehicle.rating)}`}>{vehicle.rating.toFixed(1)}</td>
                <td>{vehicle.fuel_per_100km.toFixed(1)} л</td>
                <td>{percent(vehicle.idle_ratio)}</td>
                <td>{percent(vehicle.coasting_ratio)}</td>
                <td>{percent(vehicle.optimal_rpm_ratio)}</td>
                <td>{vehicle.brakes_per_100km.toFixed(1)}</td>
                <td>{vehicle.high_speed_brakes_per_100km.toFixed(1)}</td>
                <td>{percent(vehicle.cruise_control_ratio)}</td>
                <td>{percent(vehicle.overspeed_ratio)}</td>
                <td>
                  <span className="rounded-pill border border-signal/20 bg-signal/10 px-3 py-1 text-xs font-bold text-signal">
                    {vehicle.analytics_readiness_percent.toFixed(0)}%
                  </span>
                </td>
                <td>{dateOrDash(vehicle.last_sync_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
