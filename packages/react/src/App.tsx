import { ShopAgent } from './ShopAgent'

function App() {
  return (
    <div style={{ padding: 40, fontFamily: 'system-ui, sans-serif' }}>
      <h1>Example Store</h1>
      <p>
        This page stands in for a real store owner's website. The ShopAgent widget
        floats over it in the bottom-right corner, regardless of where it's mounted
        in the page.
      </p>
      <ShopAgent
        apiUrl="http://127.0.0.1:8010"
        storeId="store_mock_001"
        primaryColor="#16A34A"
      />
    </div>
  )
}

export default App
