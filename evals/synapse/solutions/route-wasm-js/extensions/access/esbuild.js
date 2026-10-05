require('esbuild').build({
  entryPoints: ['src/index.ts'],
  outdir: 'dist',
  bundle: true,
  format: 'cjs',
  target: ['es2020'],
});
