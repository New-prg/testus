import { useEffect, useMemo, useState } from 'react';

import type { DashboardPeriod, VehicleComparisonRow } from '../api/dashboard';
import type { FleetReport, ReportConclusion, ReportObjectType, VehicleReport } from '../api/reports';
import { exportReportCsv, getFleetReport, getVehicleReport } from '../api/reports';
import { EmptyState, ErrorState, LoadingState } from '../components/cards/StateViews';
import { useRouteData } from '../components/layout/RouteDataProvider';
import { ReportsTable } from '../components/tables/ReportsTable';

type ActiveReport = FleetReport | VehicleReport;

const periodOptions: Array<{ value: DashboardPeriod; label: string }> = [
  { value: 'week', label: 'Неделя' },
  { value: 'month', label: 'Месяц' },
  { value: 'quarter', label: 'Квартал' },
];

function isVehicleReport(report: ActiveReport): report is VehicleReport {
  return 'vehicle' in report;
}

function rowsFromReport(report: ActiveReport | null): VehicleComparisonRow[] {
  if (!report) {
    return [];
  }
  if (isVehicleReport(report)) {
    return [report.summary];
  }
  return report.comparison;
}

function conclusionTone(severity: ReportConclusion['severity']): string {
  if (severity === 'positive') {
    return 'border-success/30 bg-success/10 text-success';
  }
  if (severity === 'critical') {
    return 'border-danger/35 bg-danger/10 text-danger';
  }
  if (severity === 'warning') {
    return 'border-warning/35 bg-warning/10 text-warning';
  }
  return 'border-line/30 bg-panelStrong/70 text-cream';
}

function severityLabel(severity: ReportConclusion['severity']): string {
  if (severity === 'positive') {
    return 'сильная сторона';
  }
  if (severity === 'critical') {
    return 'критично';
  }
  if (severity === 'warning') {
    return 'предупреждение';
  }
  return 'нейтрально';
}

export function ReportsPage() {
  const { ensureReport, ensureVehicles, getReportKey, reportsCache, vehiclesState } = useRouteData();
  const [period, setPeriod] = useState<DashboardPeriod>('week');
  const [objectType, setObjectType] = useState<ReportObjectType>('fleet');
  const [selectedVehicleId, setSelectedVehicleId] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const vehicles = vehiclesState.data ?? [];
  const activeVehicleId = objectType === 'vehicle' ? selectedVehicleId || vehicles[0]?.id || '' : undefined;
  const cacheKey = getReportKey({ objectType, period, vehicleId: activeVehicleId });
  const reportState = reportsCache[cacheKey] ?? { data: null, error: null, isLoading: false, loadedAt: null };
  const report = reportState.data;

  async function refreshReport() {
    setActionError(null);
    await ensureReport({ objectType, period, vehicleId: activeVehicleId }, { force: true });
  }

  useEffect(() => {
    void ensureVehicles();
  }, [ensureVehicles]);

  useEffect(() => {
    if (objectType === 'vehicle' && !selectedVehicleId) {
      const fallbackVehicleId = vehicles[0]?.id;
      if (fallbackVehicleId) {
        setSelectedVehicleId(fallbackVehicleId);
      }
      return;
    }

    void ensureReport({ objectType, period, vehicleId: activeVehicleId });
  }, [activeVehicleId, ensureReport, objectType, period, selectedVehicleId, vehicles]);

  const rows = useMemo(() => rowsFromReport(report), [report]);

  const headline = useMemo(() => {
    if (!report) {
      return 'Выберите тип отчёта и период, чтобы загрузить текстовые выводы с бекэнда.';
    }
    if (isVehicleReport(report)) {
      return `${report.vehicle.plate_number}: рейтинг ${report.summary.rating.toFixed(1)} за период ${report.period}, расход ${report.summary.fuel_per_100km.toFixed(1)} л/100 км и готовность аналитики ${report.summary.analytics_readiness_percent.toFixed(0)}%.`;
    }
    return `Отчёт по автопарку за период ${report.period}: ${report.summary.vehicles_count} машин, средний рейтинг ${report.summary.fleet_rating.toFixed(1)}, аномалий ${report.summary.anomaly_vehicles_count}.`;
  }, [report]);

  function handleObjectTypeChange(value: ReportObjectType) {
    setObjectType(value);
    setActionError(null);
  }

  function handlePeriodChange(value: DashboardPeriod) {
    setPeriod(value);
    setActionError(null);
  }

  function handleVehicleChange(value: string) {
    setSelectedVehicleId(value);
    setActionError(null);
  }

  async function handleExportCsv() {
    setIsExporting(true);
    setActionError(null);
    try {
      const blob = await exportReportCsv(objectType, period, objectType === 'vehicle' ? selectedVehicleId : undefined);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${objectType === 'fleet' ? 'автопарк' : 'машина'}-отчёт-${period}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setActionError('Не удалось выгрузить CSV-отчёт.');
    } finally {
      setIsExporting(false);
    }
  }

  if ((reportState.isLoading || vehiclesState.isLoading) && !report) {
    return <LoadingState message="Загружаем отчёт..." />;
  }

  return (
    <div className="space-y-6 animate-reveal">
      <section className="surface-card p-6 sm:p-8">
        <div className="grid gap-6 lg:grid-cols-2 lg:items-end">
          <div>
            <p className="section-label">Отчёты и выводы</p>
            <h1 className="mt-3 font-display text-4xl text-cream">Отчёты</h1>
            <p className="mt-3 text-sm leading-6 text-muted">
              Выберите отчёт по автопарку или по машине, задайте период, изучите выводы бекэнда и выгрузите тот же отчёт в CSV.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-sm font-semibold text-cream">
              Объект
              <select className="control-field mt-2" value={objectType} onChange={(event) => handleObjectTypeChange(event.target.value as ReportObjectType)}>
                <option value="fleet">Автопарк</option>
                <option value="vehicle">Машина</option>
              </select>
            </label>
            <label className="text-sm font-semibold text-cream">
              Период
              <select className="control-field mt-2" value={period} onChange={(event) => handlePeriodChange(event.target.value as DashboardPeriod)}>
                {periodOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label className="text-sm font-semibold text-cream">
              Машина
              <select className="control-field mt-2" value={selectedVehicleId} onChange={(event) => handleVehicleChange(event.target.value)} disabled={objectType === 'fleet'}>
                {vehicles.map((vehicle) => (
                  <option key={vehicle.id} value={vehicle.id}>{vehicle.plate_number} · {vehicle.name}</option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <button className="primary-action" type="button" onClick={() => void refreshReport()} disabled={reportState.isLoading}>
            {reportState.isLoading ? 'Обновляем...' : 'Обновить отчёт'}
          </button>
          <button className="secondary-action" type="button" onClick={handleExportCsv} disabled={isExporting || (objectType === 'vehicle' && !selectedVehicleId)}>
            {isExporting ? 'Выгружаем...' : 'Экспорт CSV'}
          </button>
        </div>
      </section>

      {(actionError || reportState.error) ? <ErrorState title="Ошибка при работе с отчётом" message={actionError ?? reportState.error ?? ''} action={<button className="secondary-action" type="button" onClick={() => void refreshReport()}>Повторить загрузку</button>} /> : null}

      <section className="surface-card p-5">
        <p className="section-label">Текстовый вывод</p>
        <p className="mt-3 text-lg leading-8 text-cream">{headline}</p>
      </section>

      {report?.conclusions.length ? (
        <section className="grid gap-4 lg:grid-cols-3">
          {report.conclusions.map((conclusion) => (
            <article key={`${conclusion.title}-${conclusion.text}`} className={`rounded-3xl border p-5 ${conclusionTone(conclusion.severity)}`}>
              <p className="text-xs font-bold uppercase tracking-widest opacity-80">{severityLabel(conclusion.severity)}</p>
              <h2 className="mt-3 text-lg font-bold text-cream">{conclusion.title}</h2>
              <p className="mt-2 text-sm leading-6 text-cream/80">{conclusion.text}</p>
            </article>
          ))}
        </section>
      ) : null}

      {rows.length ? (
        <ReportsTable rows={rows} />
      ) : (
        <EmptyState title="Для выбранного отчёта нет строк" message="Выбранный эндпоинт отчёта не вернул строки сравнения машин. Попробуйте другой период или другой объект отчёта." />
      )}
    </div>
  );
}
