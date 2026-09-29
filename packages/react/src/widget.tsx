import { createRoot } from 'react-dom/client'
import { ShopAgent, type ShopAgentProps } from './index'

function init(config: ShopAgentProps) {
  const container = document.createElement('div')
  container.id = 'shopagent-widget-root'
  document.body.appendChild(container)
  createRoot(container).render(<ShopAgent {...config} />)
}

declare global {
  interface Window {
    ShopAgent: { init: typeof init }
  }
}

window.ShopAgent = { init }
