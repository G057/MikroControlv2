import { createContext, useContext, useState, useEffect, ReactNode, useMemo } from 'react';

type Theme = 'light' | 'dark';

export interface ThemeColors {
  bgPage: string;
  bgSidebar: string;
  bgCard: string;
  bgInput: string;
  bgHover: string;
  bgActive: string;
  bgOverlay: string;
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  textLink: string;
  textOnAccent: string;
  border: string;
  borderLight: string;
  borderFocus: string;
  accent: string;
  accentLight: string;
  green: string;
  greenBg: string;
  red: string;
  redBg: string;
  yellow: string;
  yellowBg: string;
  blue: string;
  blueBg: string;
  purple: string;
  purpleBg: string;
  cyan: string;
  cyanBg: string;
  orange: string;
  orangeBg: string;
  chartGrid: string;
  chartText: string;
  chartTooltipBg: string;
  chartTooltipBorder: string;
  chartTooltipText: string;
  shadow: string;
}

const LIGHT_COLORS: ThemeColors = {
  bgPage: '#F1F5F9', bgSidebar: '#FFFFFF', bgCard: '#FFFFFF', bgInput: '#FFFFFF',
  bgHover: 'rgba(0,0,0,0.05)', bgActive: 'rgba(29,78,216,0.08)', bgOverlay: 'rgba(0,0,0,0.5)',
  textPrimary: '#0F172A', textSecondary: '#475569', textMuted: '#64748B',
  textLink: '#1D4ED8', textOnAccent: '#FFFFFF',
  border: '#CBD5E1', borderLight: '#E2E8F0', borderFocus: '#1D4ED8',
  accent: '#0794C7', accentLight: 'rgba(7,148,199,0.1)',
  green: '#16A34A', greenBg: 'rgba(22,163,74,0.1)',
  red: '#DC2626', redBg: 'rgba(220,38,38,0.1)',
  yellow: '#CA8A04', yellowBg: 'rgba(202,138,4,0.1)',
  blue: '#1D4ED8', blueBg: 'rgba(29,78,216,0.1)',
  purple: '#7C3AED', purpleBg: 'rgba(124,58,237,0.1)',
  cyan: '#0891B2', cyanBg: 'rgba(8,145,178,0.1)',
  orange: '#C2410C', orangeBg: 'rgba(194,65,12,0.1)',
  chartGrid: '#CBD5E1', chartText: '#64748B',
  chartTooltipBg: '#FFFFFF', chartTooltipBorder: '#CBD5E1', chartTooltipText: '#0F172A',
  shadow: '0 1px 3px rgba(0,0,0,0.08)',
};

const DARK_COLORS: ThemeColors = {
  bgPage: '#0F172A', bgSidebar: '#1E293B', bgCard: '#1E293B', bgInput: '#0F172A',
  bgHover: 'rgba(51,65,85,0.7)', bgActive: 'rgba(56,189,248,0.15)', bgOverlay: 'rgba(0,0,0,0.6)',
  textPrimary: '#F8FAFC', textSecondary: '#CBD5E1', textMuted: '#94A3B8',
  textLink: '#60A5FA', textOnAccent: '#FFFFFF',
  border: '#475569', borderLight: '#334155', borderFocus: '#0794C7',
  accent: '#0794C7', accentLight: 'rgba(7,148,199,0.2)',
  green: '#4ADE80', greenBg: 'rgba(74,222,128,0.12)',
  red: '#F87171', redBg: 'rgba(248,113,113,0.12)',
  yellow: '#FACC15', yellowBg: 'rgba(250,204,21,0.12)',
  blue: '#60A5FA', blueBg: 'rgba(96,165,250,0.12)',
  purple: '#C084FC', purpleBg: 'rgba(192,132,252,0.12)',
  cyan: '#22D3EE', cyanBg: 'rgba(34,211,238,0.12)',
  orange: '#FB923C', orangeBg: 'rgba(251,146,60,0.12)',
  chartGrid: '#334155', chartText: '#94A3B8',
  chartTooltipBg: '#1E293B', chartTooltipBorder: '#475569', chartTooltipText: '#F8FAFC',
  shadow: '0 1px 3px rgba(0,0,0,0.3)',
};

interface ThemeContextType {
  theme: Theme;
  toggle: () => void;
  isDark: boolean;
  c: ThemeColors;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: 'dark', toggle: () => {}, isDark: true, c: DARK_COLORS,
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() =>
    (localStorage.getItem('mikrocontrol-theme') as Theme) || 'dark'
  );

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('mikrocontrol-theme', theme);
  }, [theme]);

  const toggle = () => setTheme(t => t === 'dark' ? 'light' : 'dark');
  const isDark = theme === 'dark';
  const c = useMemo(() => (isDark ? DARK_COLORS : LIGHT_COLORS), [isDark]);

  return (
    <ThemeContext.Provider value={{ theme, toggle, isDark, c }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
