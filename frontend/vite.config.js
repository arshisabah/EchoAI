import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Load env file based on mode
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
    plugins: [react()],
    
    // Build optimizations
    build: {
      minify: 'esbuild',  // ✅ Faster than terser, already included in Vite
      
      // esbuild minify options
      esbuildOptions: {
        drop: ['console', 'debugger'],
      },
      
      rollupOptions: {
        output: {
          manualChunks: {
            // Only include packages that are actually installed and used
            'react-vendor': ['react', 'react-dom', 'react-router-dom']
          }
        }
      },
      chunkSizeWarningLimit: 1000,
      
      // Additional optimizations
      sourcemap: false,           // Disable sourcemaps in production for smaller size
      cssCodeSplit: true,         // Split CSS into separate files
      reportCompressedSize: false, // Faster build times
      
      // Optimize assets
      assetsInlineLimit: 4096,    // Inline assets smaller than 4kb
    },
    
    // Development server config
    server: {
      port: 5173,
      host: true,                 // Listen on all addresses (0.0.0.0)
      strictPort: true,           // Exit if port is already in use
      open: false,                // Don't auto-open browser
      cors: true,                 // Enable CORS
      
      // Proxy API requests in development (optional)
      proxy: {
        '/api': {
          target: env.VITE_BACKEND_URL || 'http://localhost:8000',
          changeOrigin: true,
          secure: false
        }
      }
    },
    
    // Preview server config (for testing production build)
    preview: {
      port: 4173,
      host: true,
      strictPort: true,
      open: false
    },
    
    // Optimize dependencies
    optimizeDeps: {
      include: ['react', 'react-dom', 'react-router-dom'],
      exclude: []
    },
    
    // Define global constants
    define: {
      'import.meta.env.VITE_BACKEND_URL': JSON.stringify(
        env.VITE_BACKEND_URL || 'http://localhost:8000'
      ),
      'import.meta.env.VITE_WS_URL': JSON.stringify(
        env.VITE_WS_URL || 'ws://localhost:8000'
      )
    }
  }
})