# First 5 minutes — OpenClaw TON skill

This is a minimal quickstart for **swapcoffee/openclaw-ton-skill**.

## What you can do today

High-level capabilities (via the included Python scripts):

- Wallets: create/import/list/export, show balances (TON + jettons)
- Transfers: send TON / jettons, resolve `.ton` domains
- Swaps: get swap quotes and execute swaps (via swap.coffee)
- Yield/DeFi: browse pools and basic analytics (via swap.coffee)
- NFTs: list, basic trading operations (Marketapp integration)
- Monitoring: transaction monitor daemon (SSE)

> Safety note: treat this as **beta**. Always start with small amounts.

## Requirements

- Python 3.10+ (see `.python-version`)
- `pip`

Install deps:

```bash
pip install -r requirements.txt
# optional for monitoring
pip install sseclient-py
```

## Configuration

The skill reads config from `~/.openclaw/ton-skill/config.json`.

Set keys using the helper:

```bash
cd scripts
python utils.py config set tonapi_key "YOUR_TONAPI_KEY"      # recommended
python utils.py config set swap_coffee_key "YOUR_SWAP_KEY"   # optional
python utils.py config set dyor_key "YOUR_DYOR_KEY"          # optional
python utils.py config set marketapp_key "YOUR_MARKETAPP_KEY"# for NFT ops
```

Wallet encryption password:

- set `WALLET_PASSWORD` env var, **or**
- pass `-p/--password` to wallet operations.

## Example commands (local)

Create a wallet:

```bash
python scripts/wallet.py create --label main
```

List wallets (+ balances can be slower):

```bash
python scripts/wallet.py list
python scripts/wallet.py list --balances
```

Send TON:

```bash
python scripts/transfer.py -p "$WALLET_PASSWORD" ton --from main --to <ADDRESS_OR_DOMAIN.ton> --amount 0.1
```

Get a swap quote (example TON→USDT):

```bash
python scripts/swap.py quote --from TON --to USDT --amount 1 --wallet <WALLET_ADDRESS>
```

Execute a swap:

```bash
# Default behavior is emulation unless you pass --confirm
python scripts/swap.py -p "$WALLET_PASSWORD" execute --wallet main --from TON --to USDT --amount 1

# Actually send on-chain:
python scripts/swap.py -p "$WALLET_PASSWORD" execute --wallet main --from TON --to USDT --amount 1 --confirm
```

## Example prompts (OpenClaw / agent)

Use these as “user asks” in OpenClaw:

- “Create a new TON wallet and show me the address.”
- “Check balance for wallet `main` (TON + jettons).”
- “Send 0.1 TON from `main` to `foundation.ton` (confirm before sending).”
- “Quote a swap 2 TON → USDT; then execute with 0.5% slippage after emulation.”
- “List top 10 yield pools by APR with TVL > $1M and low risk label.”
- “List my NFTs in wallet `main` and show floor prices.”

## Capabilities matrix

| Area | Script(s) | Read-only | Writes on-chain | Notes |
|---|---|---:|---:|---|
| Wallets | `wallet.py` | ✅ | ✅ | Create/import changes local encrypted store; on-chain only when spending |
| Balances | `wallet.py` | ✅ | ❌ | May require TonAPI for richer data |
| Transfers | `transfer.py` | ❌ | ✅ | Supports `.ton` resolution |
| Swaps | `swap.py` | ✅ (quote) | ✅ (execute) | Uses swap.coffee; emulation supported |
| Yield/DeFi | `yield_cmd.py` | ✅ (browse/position) | ✅ (deposit/withdraw/stake/unstake) | Read-only listing is safe; deposit/withdraw/stake are on-chain writes |
| NFTs | `nft.py` | ✅ | ✅ | Marketapp needed for trading |
| Monitoring | `monitor.py` | ✅ | ❌ | SSE + daemon mode |

## Known limitations (current)

- Not all APIs expose “user activity” endpoints (e.g., comments/upvotes history).
- Some features require API keys (TonAPI/Marketapp). Without them, certain commands degrade or are unavailable.
- Token symbol lookup may be ambiguous if the upstream API returns a near-match; prefer explicit addresses when possible.
- This repo is evolving quickly; interfaces may change.

## How to contribute

- Open issues for bugs/feature requests.
- PRs are welcome (and may be eligible for TON rewards if the maintainer offers bounties).

Suggested PR ideas:
- Expand this quickstart with screenshots and exact OpenClaw config examples.
- Add deterministic fixtures for swap/yield flows.
- Add policy-gated “unsafe” actions + dry-run mode.
