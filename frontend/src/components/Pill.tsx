import type { ReactNode } from 'react';
import styles from './Pill.module.css';

type PillTone = 'success' | 'danger' | 'warning' | 'neutral' | 'brand';

export function Pill({ tone, children }: { tone: PillTone; children: ReactNode }) {
  return <span className={`${styles.pill} ${styles[tone]}`}>{children}</span>;
}
