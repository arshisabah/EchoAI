#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
const mode = args[0] || 'local';

const envFiles = {
  local: `VITE_BACKEND_URL=http://localhost:8000
VITE_ENABLE_ANALYTICS=true
VITE_ENABLE_VIDEO=true
VITE_ENABLE_RECORDING=true
VITE_DEBUG=true`,
  
  network: `VITE_BACKEND_URL=http://192.168.0.106:8000
VITE_ENABLE_ANALYTICS=true
VITE_ENABLE_VIDEO=true
VITE_ENABLE_RECORDING=true
VITE_DEBUG=true`,
  
  production: `VITE_BACKEND_URL=https://api.yourdomain.com
VITE_ENABLE_ANALYTICS=true
VITE_ENABLE_VIDEO=true
VITE_ENABLE_RECORDING=true
VITE_DEBUG=false`
};

if (!envFiles[mode]) {
  console.error(`❌ Invalid mode: ${mode}`);
  console.log('Available modes: local, network, production');
  process.exit(1);
}

const envPath = path.join(__dirname, '..', '.env');
fs.writeFileSync(envPath, envFiles[mode]);
console.log(`✅ Switched to ${mode} environment`);
console.log(`📝 .env file updated`);