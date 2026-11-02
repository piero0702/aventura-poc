/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        papel: '#FAF9F7', 'papel-2': '#F2F0EC', tinta: '#151515',
        'tinta-60': 'rgba(21,21,21,.60)', 'tinta-12': 'rgba(21,21,21,.12)',
        lila: '#D59FFF', turquesa: '#3BDCE1', celeste: '#48BBD8', cobalto: '#497CDD',
        lima: '#DFE270', aguamarina: '#69C9BB', magenta: '#E85DB6',
      },
      fontFamily: { sans: ['Instrument Sans', 'sans-serif'], editorial: ['Gloock', 'serif'] },
      borderRadius: { tarjeta: '24px', campo: '12px', pildora: '999px' },
    },
  },
  plugins: [],
};
