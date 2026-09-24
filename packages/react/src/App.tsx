import { ShopAgent } from './ShopAgent'

function App() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', marginTop: 40 }}>
      <ShopAgent apiUrl="http://127.0.0.1:8010" storeId="store_mock_001" />
    </div>
  )
}

export default App
