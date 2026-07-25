export function Spinner({ size = 28 }: { size?: number }) {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        border: '3px solid oklch(0.9 0.005 250)',
        borderTopColor: 'var(--brand)',
        animation: 'spin 0.8s linear infinite',
      }}
    />
  );
}
