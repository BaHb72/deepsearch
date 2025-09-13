import React, { useState } from 'react'
import Button from '../components/base/Button'
import Input from '../components/base/Input'
import Card, { CardGrid, CardMeta } from '../components/base/Card'
import { 
  SearchOutlined, 
  SettingOutlined, 
  HeartOutlined,
  ShareAltOutlined,
  EditOutlined,
  DeleteOutlined,
  PlusOutlined,
  MinusOutlined
} from '@ant-design/icons'
import '../styles/variables.css'
import './ComponentShowcase.scss'

/**
 * Component Showcase Page
 * Demonstrates all unified components with their variants
 */
const ComponentShowcase = () => {
  const [theme, setTheme] = useState('light')
  const [inputValue, setInputValue] = useState('')
  const [numberValue, setNumberValue] = useState(0)
  const [passwordValue, setPasswordValue] = useState('')
  const [textareaValue, setTextareaValue] = useState('')
  
  // Toggle theme
  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
    document.documentElement.setAttribute('data-theme', newTheme)
  }
  
  return (
    <div className="component-showcase">
      <div className="showcase-header">
        <h1>DeepSearch Component Library</h1>
        <p>Unified React components with consistent design and behavior</p>
        <Button onClick={toggleTheme} variant="secondary">
          Toggle Theme ({theme})
        </Button>
      </div>
      
      {/* Button Section */}
      <section className="showcase-section">
        <h2>Buttons</h2>
        
        <div className="showcase-group">
          <h3>Variants</h3>
          <div className="showcase-row">
            <Button variant="primary">Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="success">Success</Button>
            <Button variant="warning">Warning</Button>
            <Button variant="danger">Danger</Button>
            <Button variant="info">Info</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="link">Link</Button>
            <Button variant="text">Text</Button>
          </div>
        </div>
        
        <div className="showcase-group">
          <h3>Sizes</h3>
          <div className="showcase-row">
            <Button size="small">Small</Button>
            <Button size="medium">Medium</Button>
            <Button size="large">Large</Button>
          </div>
        </div>
        
        <div className="showcase-group">
          <h3>With Icons</h3>
          <div className="showcase-row">
            <Button icon={<SearchOutlined />}>Search</Button>
            <Button icon={<SettingOutlined />} iconPosition="right">Settings</Button>
            <Button icon={<PlusOutlined />} variant="success">Add Item</Button>
            <Button icon={<DeleteOutlined />} variant="danger">Delete</Button>
          </div>
        </div>
        
        <div className="showcase-group">
          <h3>States</h3>
          <div className="showcase-row">
            <Button loading>Loading</Button>
            <Button disabled>Disabled</Button>
            <Button active>Active</Button>
            <Button variant="primary" ghost>Ghost Primary</Button>
          </div>
        </div>
        
        <div className="showcase-group">
          <h3>Shapes</h3>
          <div className="showcase-row">
            <Button round>Round</Button>
            <Button circle icon={<SearchOutlined />} />
            <Button circle icon={<SettingOutlined />} size="large" />
            <Button block>Block Button</Button>
          </div>
        </div>
      </section>
      
      {/* Input Section */}
      <section className="showcase-section">
        <h2>Inputs</h2>
        
        <div className="showcase-group">
          <h3>Basic Inputs</h3>
          <div className="showcase-column">
            <Input 
              placeholder="Enter text..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              label="Text Input"
              helper="This is a help text"
            />
            
            <Input 
              type="password"
              placeholder="Enter password..."
              value={passwordValue}
              onChange={(e) => setPasswordValue(e.target.value)}
              label="Password"
              visibilityToggle
            />
            
            <Input 
              type="number"
              placeholder="Enter number..."
              value={numberValue}
              onChange={(e) => setNumberValue(e.target.value)}
              label="Number Input"
              min={0}
              max={100}
              step={5}
            />
            
            <Input 
              type="email"
              placeholder="Enter email..."
              label="Email"
              required
            />
          </div>
        </div>
        
        <div className="showcase-group">
          <h3>Input Features</h3>
          <div className="showcase-column">
            <Input 
              placeholder="Search..."
              type="search"
              enterButton="Search"
              onSearch={(value) => console.log('Search:', value)}
            />
            
            <Input 
              placeholder="With clear button"
              allowClear
              defaultValue="Clear me!"
            />
            
            <Input 
              placeholder="With prefix and suffix"
              prefix={<SearchOutlined />}
              suffix=".com"
            />
            
            <Input 
              placeholder="With character count"
              showCount
              maxLength={20}
              defaultValue="Count my chars"
            />
          </div>
        </div>
        
        <div className="showcase-group">
          <h3>Textarea</h3>
          <div className="showcase-column">
            <Input 
              type="textarea"
              placeholder="Enter long text..."
              value={textareaValue}
              onChange={(e) => setTextareaValue(e.target.value)}
              rows={4}
              showCount
              maxLength={200}
              label="Description"
              helper="Maximum 200 characters"
            />
          </div>
        </div>
        
        <div className="showcase-group">
          <h3>Input States</h3>
          <div className="showcase-column">
            <Input 
              placeholder="Success state"
              success
              defaultValue="Valid input"
              helper="Input is valid!"
            />
            
            <Input 
              placeholder="Error state"
              error
              defaultValue="Invalid input"
              helper="Please correct this field"
            />
            
            <Input 
              placeholder="Loading state"
              loading
              defaultValue="Processing..."
            />
            
            <Input 
              placeholder="Disabled state"
              disabled
              defaultValue="Cannot edit"
            />
            
            <Input 
              placeholder="Read-only state"
              readOnly
              defaultValue="Read only content"
            />
          </div>
        </div>
        
        <div className="showcase-group">
          <h3>Input Sizes</h3>
          <div className="showcase-column">
            <Input placeholder="Small input" size="small" />
            <Input placeholder="Medium input" size="medium" />
            <Input placeholder="Large input" size="large" />
          </div>
        </div>
      </section>
      
      {/* Card Section */}
      <section className="showcase-section">
        <h2>Cards</h2>
        
        <div className="showcase-group">
          <h3>Basic Cards</h3>
          <CardGrid cols={3}>
            <Card title="Default Card" subtitle="With subtitle">
              <p>This is the card content. Cards are versatile containers for grouping related content.</p>
            </Card>
            
            <Card 
              title="Card with Extra"
              extra={<Button variant="link" size="small">More</Button>}
            >
              <p>Card content with an extra action button in the header.</p>
            </Card>
            
            <Card 
              title="Card with Actions"
              actions={[
                <Button variant="text" icon={<HeartOutlined />} size="small">Like</Button>,
                <Button variant="text" icon={<ShareAltOutlined />} size="small">Share</Button>,
                <Button variant="text" icon={<EditOutlined />} size="small">Edit</Button>,
              ]}
            >
              <p>This card has action buttons at the bottom.</p>
            </Card>
          </CardGrid>
        </div>
        
        <div className="showcase-group">
          <h3>Card Variants</h3>
          <CardGrid cols={4}>
            <Card variant="default" title="Default">
              <p>Default card style</p>
            </Card>
            
            <Card variant="outlined" title="Outlined">
              <p>Outlined card style</p>
            </Card>
            
            <Card variant="elevated" title="Elevated">
              <p>Elevated card style</p>
            </Card>
            
            <Card variant="filled" title="Filled">
              <p>Filled card style</p>
            </Card>
          </CardGrid>
        </div>
        
        <div className="showcase-group">
          <h3>Card Features</h3>
          <CardGrid cols={3}>
            <Card 
              title="Hoverable Card"
              hoverable
            >
              <p>Hover over this card to see the effect.</p>
            </Card>
            
            <Card 
              title="Selected Card"
              selected
            >
              <p>This card is in selected state.</p>
            </Card>
            
            <Card 
              title="Loading Card"
              loading
            >
              <p>This card is loading...</p>
            </Card>
          </CardGrid>
        </div>
        
        <div className="showcase-group">
          <h3>Card with Cover</h3>
          <CardGrid cols={2}>
            <Card 
              cover="https://via.placeholder.com/400x200"
              title="Card with Image"
            >
              <CardMeta
                title="Beautiful Landscape"
                description="This is a card with a cover image and metadata component."
              />
            </Card>
            
            <Card 
              title="Financial Data Card"
              variant="elevated"
              extra={<span style={{ color: 'var(--color-bullish)' }}>+2.45%</span>}
            >
              <div className="financial-stats">
                <div className="stat-item">
                  <span className="stat-label">Open</span>
                  <span className="stat-value">3,245.67</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">High</span>
                  <span className="stat-value" style={{ color: 'var(--color-bullish)' }}>3,289.12</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Low</span>
                  <span className="stat-value" style={{ color: 'var(--color-bearish)' }}>3,221.34</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Volume</span>
                  <span className="stat-value">1.2B</span>
                </div>
              </div>
            </Card>
          </CardGrid>
        </div>
        
        <div className="showcase-group">
          <h3>Card Sizes</h3>
          <CardGrid cols={3}>
            <Card title="Small Card" size="small">
              <p>Small sized card</p>
            </Card>
            
            <Card title="Medium Card" size="medium">
              <p>Medium sized card (default)</p>
            </Card>
            
            <Card title="Large Card" size="large">
              <p>Large sized card with more padding</p>
            </Card>
          </CardGrid>
        </div>
        
        <div className="showcase-group">
          <h3>Clickable Cards</h3>
          <CardGrid cols={2}>
            <Card 
              title="Clickable Card"
              hoverable
              onClick={() => alert('Card clicked!')}
            >
              <p>Click this card to trigger an action.</p>
            </Card>
            
            <Card 
              title="Disabled Card"
              disabled
              onClick={() => alert('This should not trigger')}
            >
              <p>This card is disabled and cannot be clicked.</p>
            </Card>
          </CardGrid>
        </div>
      </section>
      
      {/* Design Tokens Preview */}
      <section className="showcase-section">
        <h2>Design System</h2>
        
        <div className="showcase-group">
          <h3>Color Palette</h3>
          <div className="color-grid">
            <div className="color-group">
              <h4>Brand Colors</h4>
              <div className="color-swatches">
                <div className="color-swatch" style={{ background: '#4A69FF' }}>
                  <span>Primary</span>
                </div>
                <div className="color-swatch" style={{ background: '#00D4AA' }}>
                  <span>Secondary</span>
                </div>
                <div className="color-swatch" style={{ background: '#FF6B6B' }}>
                  <span>Accent</span>
                </div>
              </div>
            </div>
            
            <div className="color-group">
              <h4>Market Colors</h4>
              <div className="color-swatches">
                <div className="color-swatch" style={{ background: '#F5222D' }}>
                  <span>Bullish</span>
                </div>
                <div className="color-swatch" style={{ background: '#52C41A' }}>
                  <span>Bearish</span>
                </div>
                <div className="color-swatch" style={{ background: '#8C8C8C' }}>
                  <span>Flat</span>
                </div>
              </div>
            </div>
            
            <div className="color-group">
              <h4>Semantic Colors</h4>
              <div className="color-swatches">
                <div className="color-swatch" style={{ background: '#52C41A' }}>
                  <span>Success</span>
                </div>
                <div className="color-swatch" style={{ background: '#FAAD14' }}>
                  <span>Warning</span>
                </div>
                <div className="color-swatch" style={{ background: '#F5222D' }}>
                  <span>Error</span>
                </div>
                <div className="color-swatch" style={{ background: '#1890FF' }}>
                  <span>Info</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div className="showcase-group">
          <h3>Typography Scale</h3>
          <div className="typography-samples">
            <div style={{ fontSize: '46px' }}>Display Title (46px)</div>
            <div style={{ fontSize: '36px' }}>Page Title (36px)</div>
            <div style={{ fontSize: '28px' }}>Primary Heading (28px)</div>
            <div style={{ fontSize: '22px' }}>Secondary Heading (22px)</div>
            <div style={{ fontSize: '18px' }}>Emphasis Content (18px)</div>
            <div style={{ fontSize: '16px' }}>Body Text (16px)</div>
            <div style={{ fontSize: '14px' }}>Secondary Content (14px)</div>
            <div style={{ fontSize: '12px' }}>Auxiliary Info (12px)</div>
          </div>
        </div>
      </section>
    </div>
  )
}

export default ComponentShowcase