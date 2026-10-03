---
name: strider-amazon
description: Shop on Amazon via Strider Labs MCP connector. Search products, add to cart, place orders, track shipments, and manage returns.
metadata:
  openclaw:
    requires:
      bins: ["npx"]
    category: "commerce"
    author: "Strider Labs"
    homepage: "https://striderlabs.ai"
---

# Strider Amazon Connector

MCP connector for shopping on Amazon. Part of the Strider Labs action execution layer for AI agents.

## Installation

```bash
npm install @striderlabs/mcp-amazon
```

## MCP Configuration

Add to your MCP client configuration (Claude Desktop, Cursor, etc.):

```json
{
  "mcpServers": {
    "amazon": {
      "command": "npx",
      "args": ["-y", "@striderlabs/mcp-amazon"]
    }
  }
}
```

## Available Tools

### amazon.search_products
Search for products on Amazon.

**Input Schema:**
```json
{
  "query": "string",
  "category": "string (optional)",
  "prime_only": "boolean (optional)",
  "max_price": "number (optional)",
  "min_rating": "number (optional)"
}
```

**Output:**
```json
{
  "products": [
    {
      "asin": "string",
      "title": "string",
      "price": "number",
      "rating": "number",
      "review_count": "number",
      "prime": "boolean",
      "delivery_estimate": "string"
    }
  ]
}
```

### amazon.add_to_cart
Add a product to shopping cart.

### amazon.place_order
Complete checkout and place an order.

### amazon.track_order
Get shipping status for an order.

### amazon.get_order_history
Retrieve past orders.

### amazon.initiate_return
Start a return process for an item.

## Authentication

First use triggers OAuth authorization flow:
1. User is redirected to Amazon to authorize
2. Tokens are stored encrypted per-user
3. Automatic refresh handles token expiration

## Usage Examples

**Search for products:**
```
Find wireless earbuds under $100 with at least 4 stars on Amazon
```

**Add to cart and order:**
```
Add the AirPods Pro to my Amazon cart and place the order
```

**Track a shipment:**
```
Where's my Amazon order from last week?
```

**Start a return:**
```
I need to return the headphones I bought on Amazon
```

## Error Handling

| Code | Meaning | Action |
|------|---------|--------|
| AUTH_EXPIRED | Session expired | Re-authenticate |
| AUTH_MFA_REQUIRED | 2FA challenge | Notify user |
| OUT_OF_STOCK | Item unavailable | Suggest alternatives |
| RATE_LIMITED | Too many requests | Retry after delay |
| PAYMENT_FAILED | Card declined | Update payment method |

## Use Cases

- Household essentials: Reorder consumables automatically
- Gift buying: Search, compare, and order gifts
- Price monitoring: Check prices on wishlist items
- Order management: Track shipments and manage returns

## Links

- npm: https://npmjs.com/package/@striderlabs/mcp-amazon
- Strider Labs: https://striderlabs.ai
- MCP Registry: https://registry.modelcontextprotocol.io
