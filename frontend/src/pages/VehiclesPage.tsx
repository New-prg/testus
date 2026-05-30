import { useEffect, useMemo, useState } from 'react';

import type { Vehicle } from '../api/vehicles';
import { EmptyState, ErrorState, LoadingState } from '../components/cards/StateViews';
import { useRouteData } from '../components/layout/RouteDataProvider';
import type { SortDirection, VehicleSortKey } from '../components/tables/VehiclesTable';
import { VehiclesTable } from '../components/tables/VehiclesTable';

type SortState = {
  key: VehicleSortKey;
  direction: SortDirection;
};

function average(values: number[]): number {
  if (!values.length) {
    return 0;
  }
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function sortValue(vehicle: Vehicle, key: VehicleSortKey): number | string {
  if (key === 'identity') {
    return `${vehicle.plate_number} ${vehicle.name}`;
  }
  if (key === 'last_sync_at') {
    return vehicle.last_sync_at ? new Date(vehicle.last_sync_at).getTime() : 0;
  }
  return vehicle[key];
}

function compareVehicles(left: Vehicle, right: Vehicle, sortState: SortState): number {
  const leftValue = sortValue(left, sortState.key);
  const rightValue = sortValue(right, sortState.key);
  const directionMultiplier = sortState.direction === 'desc' ? -1 : 1;

  if (typeof leftValue === 'string' && typeof rightValue === 'string') {
    return leftValue.localeCompare(rightValue, 'ru-RU', { numeric: true, sensitivity: 'base' }) * directionMultiplier;
  }

  return (Number(leftValue) - Number(rightValue)) * directionMultiplier;
}

export function VehiclesPage() {
  const { vehiclesState, ensureVehicles } = useRouteData();
  const [search, setSearch] = useState('');
  const [sortState, setSortState] = useState<SortState>({ key: 'rating', direction: 'desc' });
  const vehicles = vehiclesState.data ?? [];

  useEffect(() => {
    void ensureVehicles();
  }, [ensureVehicles]);

  const filteredVehicles = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return vehicles
      .filter((vehicle) => {
        if (!normalizedSearch) {
          return true;
        }
        return [vehicle.plate_number, vehicle.name].some((value) => value.toLowerCase().includes(normalizedSearch));
      })
      .sort((left, right) => compareVehicles(left, right, sortState));
  }, [search, sortState, vehicles]);

  const fleetStats = useMemo(
    () => ({
      rating: average(vehicles.map((vehicle) => vehicle.rating)),
      fuel: average(vehicles.map((vehicle) => vehicle.fuel_per_100km)),
    }),
    [vehicles],
  );

  function handleSort(key: VehicleSortKey) {
    setSortState((current) => ({
      key,
      direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc',
    }));
  }

  if (vehiclesState.isLoading && !vehicles.length) {
    return <LoadingState message="Загружаем реестр автопарка..." />;
  }

  if (vehiclesState.error && !vehicles.length) {
    return <ErrorState title="Реестр автопарка недоступен" message={vehiclesState.error} action={<button className="secondary-action" type="button" onClick={() => void ensureVehicles({ force: true })}>Повторить</button>} />;
  }

  return (
    <div className="space-y-6 animate-reveal">
      <section className="surface-card p-4">
        <label className="text-sm font-semibold text-cream" htmlFor="vehicleSearch">
          Поиск
        </label>
        <input
          id="vehicleSearch"
          className="control-field mt-2"
          placeholder="Госномер или название"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <div className="surface-card p-4">
          <p className="section-label">Средний рейтинг по автопарку</p>
          <p className="mt-2 font-display text-3xl text-signal">{fleetStats.rating.toFixed(1)}</p>
        </div>
        <div className="surface-card p-4">
          <p className="section-label">Средний расход топлива / 100 км</p>
          <p className="mt-2 font-display text-3xl text-brass">{fleetStats.fuel.toFixed(1)} л</p>
        </div>
      </section>

      {filteredVehicles.length ? (
        <VehiclesTable vehicles={filteredVehicles} sortKey={sortState.key} sortDirection={sortState.direction} onSort={handleSort} />
      ) : (
        <EmptyState title="По этому запросу машин не найдено" message="Поиск выполняется только по полям plate_number и name. Очистите фильтр или синхронизируйте машины, чтобы заполнить реестр." />
      )}
    </div>
  );
}
