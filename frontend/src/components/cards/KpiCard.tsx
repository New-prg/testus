import { useState } from 'react';

type KpiCardProps = {
  label: string;
  score: string;
  actualValue: string;
  delta: number;
  tone?: 'signal' | 'brass' | 'success' | 'warning' | 'danger';
};

const toneClasses: Record<NonNullable<KpiCardProps['tone']>, string> = {
  signal: 'text-signal bg-signal/10 border-signal/25',
  brass: 'text-brass bg-brass/10 border-brass/25',
  success: 'text-success bg-success/10 border-success/25',
  warning: 'text-warning bg-warning/10 border-warning/25',
  danger: 'text-danger bg-danger/10 border-danger/25',
};

function formatDelta(delta: number): string {
  return `${delta >= 0 ? '+' : ''}${delta.toFixed(1)}`;
}

function deltaClasses(delta: number): string {
  if (delta > 0) {
    return 'border-success/30 bg-success/10 text-success';
  }
  if (delta < 0) {
    return 'border-danger/35 bg-danger/10 text-danger';
  }
  return 'border-line/30 bg-panelStrong/70 text-muted';
}

export function KpiCard({ label, score, actualValue, delta, tone = 'signal' }: KpiCardProps) {
  const [showsActual, setShowsActual] = useState(false);
  const displayedValue = showsActual ? actualValue : score;
  const deltaText = formatDelta(delta);

  return (
    <button
        className="surface-card group relative w-full overflow-hidden p-5 text-left transition hover:-translate-y-1 hover:border-signal/40 focus:outline-none focus:ring-2 focus:ring-signal/35"
        type="button"
        aria-pressed={showsActual}
        aria-label={`${label}: ${showsActual ? 'фактическое значение' : 'оценка по 10-балльной шкале'}. Нажмите, чтобы переключить вид.`}
        title={showsActual ? `Изменение по бальной шкале относительно прошлого периода: ${deltaText}` : `Изменение относительно прошлого периода: ${deltaText}`}
        onClick={() => setShowsActual((current) => !current)}
      >
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-transparent via-signal/70 to-transparent opacity-0 transition group-hover:opacity-100" />
      <div className="flex items-start justify-between gap-3">
        <p className={`inline-flex rounded-pill border px-3 py-1 text-xs font-bold uppercase tracking-widest ${toneClasses[tone]}`}>
          {label}
        </p>
          <span className={`rounded-pill border px-3 py-1 text-xs font-bold tabular-nums ${deltaClasses(delta)}`}>
            {deltaText}
          </span>
        </div>
      <p className="mt-5 font-display text-4xl font-bold text-cream">{displayedValue}</p>
      {showsActual ? <p className="mt-3 text-xs font-bold uppercase tracking-widest text-muted">Фактическое значение · оценка {score} · Δ балла {deltaText}</p> : null}
    </button>
  );
}
