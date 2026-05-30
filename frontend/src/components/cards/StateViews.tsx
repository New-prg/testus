type StateViewProps = {
  title: string;
  message: string;
  action?: React.ReactNode;
};

export function LoadingState({ message = 'Загружаем аналитику...' }: { message?: string }) {
  return (
    <div className="surface-card flex min-h-64 flex-col items-center justify-center gap-4 p-8 text-center">
      <div className="h-12 w-12 rounded-full border-2 border-line/30 border-t-signal animate-spin" />
      <p className="text-sm font-semibold uppercase tracking-widest text-muted">{message}</p>
    </div>
  );
}

export function EmptyState({ title, message, action }: StateViewProps) {
  return (
    <div className="surface-card flex min-h-64 flex-col items-center justify-center p-8 text-center">
      <p className="section-label">Нет данных</p>
      <h2 className="mt-3 font-display text-3xl text-cream">{title}</h2>
      <p className="mt-3 max-w-xl text-sm leading-6 text-muted">{message}</p>
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ title, message, action }: StateViewProps) {
  return (
    <div className="surface-card border-danger/40 bg-danger/10 p-6">
      <p className="section-label text-danger">Требуется действие</p>
      <h2 className="mt-2 font-display text-2xl text-cream">{title}</h2>
      <p className="mt-3 text-sm leading-6 text-cream/80">{message}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
