import { NavLink } from 'react-router-dom';
import {
  BookIcon,
  ChecklistIcon,
  ClockIcon,
  CoverageIcon,
  DownloadIcon,
  GearIcon,
  PencilIcon,
} from './icons';
import styles from './Sidebar.module.css';

const NAV_ITEMS = [
  { to: '/', label: 'Generate', icon: PencilIcon, end: true },
  { to: '/review', label: 'Review', icon: ChecklistIcon },
  { to: '/coverage', label: 'Coverage Matrix', icon: CoverageIcon },
  { to: '/export', label: 'Export', icon: DownloadIcon },
  { to: '/library', label: 'Test Case Library', icon: BookIcon },
  { to: '/history', label: 'Run History', icon: ClockIcon },
];

export function Sidebar() {
  return (
    <div className={styles.sidebar}>
      <div className={styles.brand}>
        <div className={styles.logo} />
        <span className={styles.brandName}>QA Test Generator</span>
      </div>

      <nav className={styles.nav}>
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => `${styles.navItem} ${isActive ? styles.navItemActive : ''}`}
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      <NavLink to="/settings" className={({ isActive }) => `${styles.settings} ${isActive ? styles.navItemActive : ''}`}>
        <GearIcon size={16} />
        Settings
      </NavLink>
    </div>
  );
}
