export const API_BASE_URL = 'http://10.62.215.108:8000';

export const COLORS = {
  bgMain: '#06060E',
  bgSurface: '#0E0D1A',
  bgCard: '#131120',
  bgInput: '#0A0915',
  primary: '#8B5CF6',
  primaryHover: '#7C3AED',
  textMain: '#F1F0F5',
  textSecondary: '#B4B0C8',
  textMuted: '#706D85',
  success: '#34D399',
  danger: '#F87171',
  warning: '#FBBF24',
  border: 'rgba(255, 255, 255, 0.06)',
};

export const FONTS = {
  regular: { fontSize: 15, color: COLORS.textMain },
  small: { fontSize: 13, color: COLORS.textSecondary },
  title: { fontSize: 24, fontWeight: '800' as const, color: COLORS.textMain },
  subtitle: { fontSize: 14, color: COLORS.textMuted },
};
