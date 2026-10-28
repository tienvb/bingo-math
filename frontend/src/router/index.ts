import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
    { path: '/create', name: 'create', component: () => import('@/views/CreateRoomView.vue') },
    { path: '/host/:pin', name: 'host', component: () => import('@/views/HostView.vue'), props: true },
    // /screen/:pin?token=<screen_token>
    { path: '/screen/:pin', name: 'screen', component: () => import('@/views/ScreenView.vue'), props: true },
    { path: '/play', name: 'play-enter', component: () => import('@/views/PlayView.vue') },
    { path: '/play/:pin', name: 'play', component: () => import('@/views/PlayView.vue'), props: true },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
