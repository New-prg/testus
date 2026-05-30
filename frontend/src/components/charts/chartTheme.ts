export const tokenColor = (token: string, alpha = 1) => `rgb(var(${token}) / ${alpha})`;

export const chartPalette = {
  signal: tokenColor('--color-signal'),
  brass: tokenColor('--color-brass'),
  ember: tokenColor('--color-ember'),
  success: tokenColor('--color-success'),
  danger: tokenColor('--color-danger'),
  muted: tokenColor('--color-muted'),
  cream: tokenColor('--color-cream'),
  line: tokenColor('--color-line', 0.32),
  panel: tokenColor('--color-panel', 0.9),
};
