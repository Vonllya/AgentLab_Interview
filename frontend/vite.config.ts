import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],server:{
  strictPort:true,
  fs:{strict:true,allow:[new URL('.',import.meta.url).pathname]},
  proxy:{'/api':'http://127.0.0.1:8000'}
}});
