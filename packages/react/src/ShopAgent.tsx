import { useState } from 'react'
import { FiMessageCircle, FiSend, FiX } from 'react-icons/fi'

export interface ShopAgentProps {
  apiUrl: string
  apiKey: string
  storeId?: string
  primaryColor?: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export function ShopAgent({ apiUrl, apiKey, primaryColor = '#6366F1' }: ShopAgentProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId] = useState(() => crypto.randomUUID())

  async function sendMessage() {
    const text = input.trim()
    if (!text || loading) return

    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setInput('')
    setLoading(true)

    try {
      const response = await fetch(`${apiUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify({ message: text, session_id: sessionId }),
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
        position: 'fixed',
        bottom: 20,
        right: 20,
        zIndex: 999999,
        fontFamily: 'system-ui, -apple-system, sans-serif',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
      }}
    >
      {isOpen && (
        <div
          style={{
            width: 370,
            marginBottom: 16,
            borderRadius: 16,
            background: 'white',
            boxShadow: '0 8px 30px rgba(0,0,0,0.18)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '14px 18px',
              background: primaryColor,
              color: 'white',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <FiMessageCircle size={20} />
              <span style={{ fontWeight: 600, fontSize: 15 }}>ShopAgent</span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              aria-label="Close chat"
              style={{
                background: 'rgba(255,255,255,0.15)',
                border: 'none',
                color: 'white',
                width: 28,
                height: 28,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
              }}
            >
              <FiX size={16} />
            </button>
          </div>

          <div style={{ height: 340, overflowY: 'auto', padding: '16px 18px', background: '#fafafa' }}>
            {messages.length === 0 && (
              <div style={{ color: '#888', fontSize: 14, lineHeight: 1.5 }}>
                👋 Hi! Ask me about products, order status, or store policies.
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} style={{ textAlign: m.role === 'user' ? 'right' : 'left', margin: '10px 0' }}>
                <span
                  style={{
                    display: 'inline-block',
                    padding: '8px 14px',
                    borderRadius: 16,
                    fontSize: 14,
                    lineHeight: 1.4,
                    background: m.role === 'user' ? primaryColor : '#ececec',
                    color: m.role === 'user' ? 'white' : '#222',
                    maxWidth: '85%',
                  }}
                >
                  {m.content}
                </span>
              </div>
            ))}
            {loading && <div style={{ color: '#999', fontSize: 13 }}>ShopAgent is typing…</div>}
          </div>

          <div style={{ display: 'flex', gap: 8, padding: '14px 18px', borderTop: '1px solid #eee' }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
              placeholder="Type a message…"
              style={{
                flex: 1,
                padding: '10px 14px',
                borderRadius: 20,
                border: '1px solid #ddd',
                fontSize: 14,
                outline: 'none',
              }}
            />
            <button
              onClick={sendMessage}
              disabled={loading}
              aria-label="Send message"
              style={{
                width: 40,
                height: 40,
                borderRadius: '50%',
                border: 'none',
                background: primaryColor,
                color: 'white',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: loading ? 'default' : 'pointer',
                opacity: loading ? 0.6 : 1,
                flexShrink: 0,
              }}
            >
              <FiSend size={16} />
            </button>
          </div>
        </div>
      )}

      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          aria-label="Open chat"
          style={{
            width: 58,
            height: 58,
            borderRadius: '50%',
            border: 'none',
            background: primaryColor,
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            boxShadow: '0 4px 14px rgba(0,0,0,0.25)',
          }}
        >
          <FiMessageCircle size={26} />
        </button>
      )}
    </div>
  )
}
