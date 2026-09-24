import { useState } from 'react'

export interface ShopAgentProps {
  apiUrl: string
  apiKey?: string
  storeId?: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export function ShopAgent({ apiUrl }: ShopAgentProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  async function sendMessage() {
    const text = input.trim()
    if (!text || loading) return

    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setInput('')
    setLoading(true)

    try {
      const response = await fetch(`${apiUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`)
      }

      const data = await response.json()
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        width: 360,
        border: '1px solid #ddd',
        borderRadius: 12,
        padding: 16,
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
      }}
    >
      <div style={{ height: 320, overflowY: 'auto', marginBottom: 12 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ textAlign: m.role === 'user' ? 'right' : 'left', margin: '8px 0' }}>
            <span
              style={{
                display: 'inline-block',
                padding: '6px 12px',
                borderRadius: 14,
                background: m.role === 'user' ? '#0b93f6' : '#e5e5ea',
                color: m.role === 'user' ? 'white' : 'black',
                maxWidth: '85%',
              }}
            >
              {m.content}
            </span>
          </div>
        ))}
        {loading && <div style={{ color: '#999', fontSize: 14 }}>ShopAgent is typing…</div>}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Ask about products, orders, or policies…"
          style={{ flex: 1, padding: 8, borderRadius: 6, border: '1px solid #ccc' }}
        />
        <button onClick={sendMessage} disabled={loading}>
          Send
        </button>
      </div>
    </div>
  )
}
