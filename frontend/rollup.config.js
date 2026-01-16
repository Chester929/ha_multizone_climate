import resolve from '@rollup/plugin-node-resolve';
import commonjs from '@rollup/plugin-commonjs';
import typescript from '@rollup/plugin-typescript';
import terser from '@rollup/plugin-terser';

const createConfig = (input, output) => ({
  input,
  output: {
    file: output,
    format: 'es',
    sourcemap: true,
  },
  plugins: [
    resolve({
      browser: true,
      preferBuiltins: false,
    }),
    commonjs(),
    typescript({
      tsconfig: './tsconfig.json',
      declaration: true,
      declarationDir: './dist',
    }),
    terser({
      compress: {
        drop_console: true,
      },
      output: {
        comments: false,
      },
    }),
  ],
  external: [],
});

export default [
  createConfig('src/cards/multizone-climate-card.ts', 'dist/multizone-climate-card.js'),
  createConfig('src/cards/main-climate-card.ts', 'dist/main-climate-card.js'),
  createConfig('src/cards/dashboard-panel.ts', 'dist/dashboard-panel.js'),
];
