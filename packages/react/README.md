# @elthratech/shopagent-react

A drop-in React chat widget for [ShopAgent-OS](https://github.com/sri-mathi/ShopAgent) — a self-hosted, open-source e-commerce AI agent. It answers customer questions about products, order status, and store policies by talking to your own ShopAgent-OS backend.

## Install

```bash
npm install @elthratech/shopagent-react
```

Requires `react` and `react-dom` ^19 as peer dependencies.

## Usage

```tsx
import { ShopAgent } from '@elthratech/shopagent-react'

function App() {
  return (
    <ShopAgent
      apiUrl="https://your-shopagent-backend.example.com"
      apiKey="your-shopagent-api-key"
    />
  )
}
```

Render it once near the root of your app — it's a fixed-position widget that floats in the bottom-right corner of the page.

## Props

| Prop | Type | Required | Description |
|---|---|---|---|
| `apiUrl` | `string` | yes | Base URL of your ShopAgent-OS backend (no trailing slash, no `/chat` suffix). |
| `apiKey` | `string` | yes | The `SHOPAGENT_API_KEY` value configured on your backend. |
| `primaryColor` | `string` | no | Hex color for the widget's accent (header, bubble, send button). Defaults to `#6366F1`. |
| `customerEmail` | `string` | no | Pass the logged-in customer's email if your site already has it, so the agent can verify order ownership automatically instead of asking for it in chat. |
| `onMessage` | `(exchange: { userMessage: string; reply: string; sessionId: string }) => void` | no | Called after each successful exchange — use it to log conversations to your own analytics/database. The widget itself keeps no history once the page is closed or refreshed. |

## Security note

`apiKey` is used directly from the browser to authenticate requests to your backend. Don't embed it in a publicly hosted page unless you understand the implications — anyone who views the page source can read it. It's intended for apps where the widget is served to your own logged-in customers, not for fully public demo pages.

## Not using React?

A framework-free version is also published with this package — load it directly via a `<script>` tag, no build step required:

```html
<script src="https://unpkg.com/@elthratech/shopagent-react/dist/widget.js"></script>
<script>
  ShopAgent.init({
    apiUrl: "https://your-shopagent-backend.example.com",
    apiKey: "your-shopagent-api-key",
  })
</script>
```

## License

MIT
