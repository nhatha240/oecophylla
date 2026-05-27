import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
export default {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter(),
    csrf: {
      trustedOrigins: [
        'http://127.0.0.1:3000',
        'http://localhost:3000',
        'http://127.0.0.1:4173',
        'http://localhost:4173',
      ],
    },
  }
};
