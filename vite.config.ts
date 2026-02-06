import path from 'path';

import react from '@vitejs/plugin-react-swc';
import { defineConfig } from 'vite';

const BACKEND_URL = 'http://127.0.0.1:8300';

export default defineConfig({
  plugins: [react()],

  resolve: {
    extensions: ['.js', '.jsx', '.ts', '.tsx', '.json'],
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  build: {
    target: 'esnext',
    outDir: 'dist',
    sourcemap: process.env.NODE_ENV === 'development',
    chunkSizeWarningLimit: 500,
    minify: 'esbuild',
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
        admin: path.resolve(__dirname, 'admin.html'),
        privacy: path.resolve(__dirname, 'privacy.html'),
      },
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'ui-vendor': ['lucide-react'],
          'markdown': ['react-markdown', 'remark-gfm'],
        },
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      },
    },
  },

  optimizeDeps: {
    include: ['react', 'react-dom', 'lucide-react'],
  },

  server: {
    host: '0.0.0.0',
    port: 3000,
    open: false,
    allowedHosts: ['localhost', '35.212.208.67', 'youthafterwork.com'],
    hmr: {
      // 只在明确需要时配置外部访问
      // 生产环境构建时会自动排除 HMR 代码
      clientPort: process.env.VITE_HMR_PORT ? parseInt(process.env.VITE_HMR_PORT) : 3000,
      // 注释掉固定 host，让 Vite 自动检测
      // host: '35.212.208.67',
    },
    proxy: {
      '/api': { target: BACKEND_URL, changeOrigin: false, secure: false },
      '/auth': { target: BACKEND_URL, changeOrigin: false, secure: false },
      '/uploads': { target: BACKEND_URL, changeOrigin: false, secure: false },
    },
  },
});
