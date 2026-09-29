import { resolve } from 'path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  define: {
    // Vite's library mode doesn't auto-replace this like its normal app-build
    // mode does. React reads process.env.NODE_ENV internally, and `process`
    // doesn't exist in a browser at all - this bundle has no further build
    // step to do that substitution for us, so we do it explicitly here.
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
  build: {
    lib: {
      entry: resolve(import.meta.dirname, 'src/widget.tsx'),
      formats: ['iife'],
      name: 'ShopAgent',
      fileName: () => 'widget.js',
    },
    // Deliberately no `rollupOptions.external` here, unlike vite.config.ts -
    // a plain <script> tag has no bundler and no npm, so React/ReactDOM must
    // be bundled directly into this output, not left for the consumer to
    // provide.
  },
})
