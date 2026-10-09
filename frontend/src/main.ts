import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import './styles/variables.css'
import './styles/base.css'
// 正文样式必须全局引入：v-html 插入的内容拿不到 scoped 的 data-v 属性，
// 放在组件里写 <style scoped> 是不会生效的。
import './styles/markdown.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
