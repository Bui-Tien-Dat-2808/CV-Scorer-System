/**
 * Cấu hình Tailwind cho bản build tĩnh (frontend/assets/css/tailwind.build.css).
 * Build: npx tailwindcss@3.4.17 -c frontend/tailwind.config.js \
 *          -i frontend/tailwind.input.css -o frontend/assets/css/tailwind.build.css --minify
 */
module.exports = {
  content: ['./frontend/index.html', './frontend/assets/js/**/*.js'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
      },
    },
  },
  plugins: [],
};
