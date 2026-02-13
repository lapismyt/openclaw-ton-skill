# Swap.Coffee Yield API Documentation

Official documentation for swap.coffee Yield API v1.

## Base URL

```
https://backend.swap.coffee/v1
```

## Endpoints

### 1. List Pools

```
GET /v1/yield/pools
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `blockchains` | string | Filter by blockchain (e.g., `ton`) |
| `providers` | array | Filter by DEX/protocol (e.g., `stonfi`, `dedust`, `tonco`) |
| `trusted` | boolean | `true` = 2,000 pools (default), `false` = 85,971+ pools |
| `with_active_boosts` | boolean | Only pools with active boosts |
| `with_liquidity_from` | string | User address to check liquidity |
| `search_text` | string | Search by pool address or token tickers |
| `order` | string | Sort field: `tvl`, `apr`, `volume` (default: `tvl`) |
| `descending_order` | boolean | Sort direction (default: true) |
| `in_groups` | boolean | Group related pools |
| `size` | integer | Results per page (max 100, default 10) |
| `page` | integer | Page number (default 1) |

**Example:**
```bash
# Get 5 dedust pools sorted by TVL
curl "https://backend.swap.coffee/v1/yield/pools?blockchains=ton&providers=dedust&trusted=true&size=5&order=tvl"

# Get ALL pools (85K+)
curl "https://backend.swap.coffee/v1/yield/pools?blockchains=ton&trusted=false&size=100&page=1"
```

**Response:**

```json
[{
  "total_count": 2000,
  "pools": [
    {
      "address": "EQA-X...",
      "protocol": "dedust",
      "is_trusted": true,
      "tokens": [...],
      "pool_statistics": {
        "tvl_usd": 931737.06,
        "volume_usd": 470059.27,
        "apr": 14.73
      },
      "pool": {
        "amm_type": "constant_product"
      }
    }
  ]
}]
```

### 2. Pool Details

```
GET /v1/yield/pool/{pool_address}
```

### 3. User Position

```
GET /v1/yield/pool/{pool_address}/{user_address}
```

**Response:**

```json
{
  "user_lp_amount": "1000000000",
  "user_lp_wallet": "EQW...",
  "boosts": [...]
}
```

### 4. Create Transaction (POST)

```
POST /v1/yield/pool/{pool_address}/{user_address}
```

**Request Body Format:**

```json
{
  "request_data": {
    "yieldTypeResolver": "operation_type",
    "field1": "value1"
  }
}
```

**Response:**

```json
[{
  "query_id": 1697643564986267,
  "message": {
    "payload_cell": "te6cck...",
    "address": "EQA-X...",
    "value": "100000000"
  }
}]
```

### 5. Check Transaction Status

```
GET /v1/yield/result?query_id={query_id}
```

---

## Operations by `yieldTypeResolver`

### DEX Operations

#### `dex_provide_liquidity`

```json
{
  "request_data": {
    "yieldTypeResolver": "dex_provide_liquidity",
    "user_wallet": "EQA...",
    "asset_1_amount": "1000000000",
    "asset_2_amount": "1000000000",
    "min_lp_amount": "900000000"
  }
}
```

#### `dex_withdraw_liquidity`

```json
{
  "request_data": {
    "yieldTypeResolver": "dex_withdraw_liquidity",
    "user_address": "EQA...",
    "lp_amount": "1000000000"
  }
}
```

### STON.fi Farm Operations

#### `dex_stonfi_lock_staking`

```json
{
  "request_data": {
    "yieldTypeResolver": "dex_stonfi_lock_staking",
    "lp_amount": "1000000000",
    "minter_address": "EQM..."
  }
}
```

#### `dex_stonfi_withdraw_staking`

```json
{
  "request_data": {
    "yieldTypeResolver": "dex_stonfi_withdraw_staking",
    "position_address": "EQP..."
  }
}
```

### Liquid Staking Operations

#### `liquid_staking_stake`

```json
{
  "request_data": {
    "yieldTypeResolver": "liquid_staking_stake",
    "amount": "1000000000"
  }
}
```

#### `liquid_staking_unstake`

```json
{
  "request_data": {
    "yieldTypeResolver": "liquid_staking_unstake",
    "amount": "1000000000"
  }
}
```

### Lending Operations

#### `lending_deposit`

```json
{
  "request_data": {
    "yieldTypeResolver": "lending_deposit",
    "amount": "1000000000"
  }
}
```

#### `lending_withdraw`

```json
{
  "request_data": {
    "yieldTypeResolver": "lending_withdraw",
    "amount": "1000000000"
  }
}
```

---

## Supported Providers

| Provider | Type | Operations |
|----------|------|------------|
| `stonfi` | DEX (v1) | withdraw only |
| `stonfi_v2` | DEX (v2) | deposit, withdraw, farm |
| `dedust` | DEX | deposit, withdraw |
| `tonco` | DEX | deposit, withdraw |
| `tonstakers` | Liquid Staking | stake, unstake |
| `bemo` | Liquid Staking | stake, unstake |
| `bemo_v2` | Liquid Staking | stake, unstake |
| `hipo` | Liquid Staking | stake, unstake |
| `kton` | Liquid Staking | stake, unstake |
| `stakee` | Liquid Staking | stake, unstake |
| `evaa` | Lending | deposit, withdraw |

---

## CLI Usage

```bash
# List trusted pools (default: 2000 pools)
python3 yield_cmd.py pools --size 10 --provider dedust

# List ALL pools (85K+)
python3 yield_cmd.py pools --size 10 --all-pools

# Search by token
python3 yield_cmd.py pools --search USDT --size 20

# Stake to liquid staking
python3 yield_cmd.py stake --pool EQCkW... --wallet EQAT... --amount 1000000000

# Check transaction status
python3 yield_cmd.py tx-status --query-id 1697643564986267
```

---

## Important Notes

1. **Body format**: Always wrap in `request_data` with `yieldTypeResolver` discriminator
2. **Pool counts**: `trusted=true` → 2,000 pools, `trusted=false` → 85,971+ pools
3. **Address format**: Use URL-safe base64 (replace `+` with `-`, `/` with `_`)
4. **Amounts**: All amounts are in minimum units (nanoTON for TON = 10^-9)
5. **Order values**: Valid sort values are `tvl`, `apr`, `volume`

---

*Last updated: 2026-02-13*
