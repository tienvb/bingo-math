/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "true" thì dùng mock client + REST giả, không cần BE. */
  readonly VITE_USE_MOCK?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}
