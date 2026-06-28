/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'media',
  theme: {
    extend: {
      colors: {
        // 核心语义颜色（组件中使用的）
        primary: {
          DEFAULT: '#8B4513',
          light: '#A0522D',
          dark: '#6B3410',
        },
        accent: {
          DEFAULT: '#C0392B',
          light: '#E74C3C',
          dark: '#A93226',
        },
        secondary: {
          DEFAULT: '#D4A574',
          light: '#E8C9A0',
          dark: '#B8935F',
        },
        surface: {
          DEFAULT: '#FAF5EF',
          dark: '#2C1810',
        },
        background: {
          DEFAULT: '#FDF6EC',
          dark: '#1A1410',
        },
        border: {
          DEFAULT: '#E8DDD0',
          dark: '#4A3B2F',
        },
        text: {
          DEFAULT: '#2C1810',
          muted: '#8B7355',
          dark: '#E8DDD0',
        },
        // jiao 品牌色系（保留兼容）
        jiao: {
          bg: '#FDF6EC',
          text: '#2C1810',
          brown: '#8B4513',
          warm: '#D4A574',
          red: '#C0392B',
          gold: '#B8860B',
          light: '#F5E6D3',
          dark: '#3C2415',
          gray: '#8B7355',
        },
      },
      fontFamily: {
        serif: ['Georgia', 'STSong', 'SimSun', 'serif'],
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'PingFang SC',
          'Hiragino Sans GB',
          'Microsoft YaHei',
          'sans-serif',
        ],
      },
      borderRadius: {
        'bubble-lg': '1rem',
        'bubble-sm': '0.5rem',
      },
      boxShadow: {
        'soft': '0 1px 3px rgba(139, 69, 19, 0.08)',
        'medium': '0 4px 12px rgba(139, 69, 19, 0.12)',
        'glow': '0 0 12px rgba(192, 57, 43, 0.3)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-slow': 'pulse 3s infinite',
        'spin-slow': 'spin 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}