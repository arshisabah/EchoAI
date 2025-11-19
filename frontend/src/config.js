const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
const WS_URL = BACKEND_URL.replace(/^http/, 'ws');

export const config = {
  // API Configuration
  BACKEND_URL: BACKEND_URL,
  WS_URL: WS_URL,
  API_URL: `${BACKEND_URL}/api`,
  
  // Feature Flags
  ENABLE_ANALYTICS: import.meta.env.VITE_ENABLE_ANALYTICS === 'true',
  ENABLE_VIDEO: import.meta.env.VITE_ENABLE_VIDEO === 'true',
  ENABLE_RECORDING: import.meta.env.VITE_ENABLE_RECORDING === 'true',
  
  // Debug
  DEBUG: import.meta.env.VITE_DEBUG === 'true',
  
  // Environment
  IS_DEV: import.meta.env.DEV,
  IS_PROD: import.meta.env.PROD,
};

// Log configuration in development
if (config.DEBUG || config.IS_DEV) {
  console.log('🔧 EchoAI Configuration:', config);
}

export default config;