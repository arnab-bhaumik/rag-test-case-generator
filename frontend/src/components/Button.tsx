import type { ButtonHTMLAttributes } from 'react';
import styles from './Button.module.css';

type Variant = 'primary' | 'secondary' | 'danger';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  full?: boolean;
}

export function Button({ variant = 'secondary', full, className, ...rest }: ButtonProps) {
  const classes = [styles.btn, styles[variant], full ? styles.full : '', className].filter(Boolean).join(' ');
  return <button className={classes} {...rest} />;
}
