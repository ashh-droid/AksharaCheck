import { defineConfig } from 'vite';

// GitHub Pages project sites use a repository path; local dev and FastAPI use '/'.
export default defineConfig(({ mode }) => ({
  base: mode === 'pages' ? '/AksharaCheck/' : '/',
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
}));
