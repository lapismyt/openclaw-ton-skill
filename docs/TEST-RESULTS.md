# TEST-RESULTS.md — Real Transaction Testing

**Date:** 2026-02-13  
**Test Wallet:** skill-test (EQDAPfo13Rclr9z3blh0XaFLgXaKmqZM1KiljM1nwi_esRfs)  
**Initial Balance:** ~20 TON  
**Budget:** Max 20 TON total

---

## Pre-Test Fixes

### FIX-001: Non-bounceable addresses for uninitialized wallets
**Files:** `transfer.py`  
**Issue:** Transfer script didn't check recipient wallet status. Sending to uninit/nonexist wallets with bounce=true would fail.  
**Fix:** Added `get_account_status()` function and bounce flag handling in `build_ton_transfer()` and `transfer_ton()`.  
**Status:** ✅ IMPLEMENTED

### FIX-002: Missing referral parameters in execute_swap()
**Files:** `swap.py`  
**Issue:** CLI passed `referral_address` and `referral_fee_percent` but function didn't accept them.  
**Fix:** Added optional parameters to `execute_swap()` function signature.  
**Status:** ✅ FIXED

---

## Test Results

### Test 1: Wallet Balance Check
**Command:** `WALLET_PASSWORD=test123 python3 scripts/wallet.py balance skill-test`  
**Result:** Successfully retrieved balance (19.99 TON, status: uninit)  
**Status:** ✅ Pass

---

### Test 2: TON Transfer (Real Transaction)
**Command:** `WALLET_PASSWORD=test123 python3 scripts/transfer.py -p test123 ton --from skill-test --to EQATYemb_I7KeyQVIekCXWsspttRQMjtdp3_UV5OT-u6hZLm --amount 0.1 --confirm`  
**Result:** 
- Transaction sent successfully
- 0.1 TON transferred to misha wallet
- Fee: ~0.0054 TON
- Wallet deployed (status changed from uninit → active)
- New balance: ~19.89 TON
**Status:** ✅ Pass
**Notes:** First transaction also deploys the wallet contract

---

### Test 3: Swap Quote (TON → USDT)
**Command:** `python3 scripts/swap.py quote --from TON --to USDT --amount 0.5 --wallet skill-test`  
**Result:** 
- Found route via "moon" DEX
- 0.5 TON → 0.69 USDT expected
- Price: 1.38 USDT/TON
- Price impact: -0.76%
- Recommended gas: 0.2 TON
**Status:** ✅ Pass

---

### Test 4: Swap Execute (Real Transaction)
**Command:** `WALLET_PASSWORD=test123 python3 scripts/swap.py execute --wallet skill-test --from TON --to USDT --amount 0.5 --confirm`  
**Result:** 
- Swap executed successfully
- 0.5 TON swapped for 0.69 USDT
- Fee: ~0.02 TON
- New balance: ~19.37 TON + 0.69 USDT
**Status:** ✅ Pass

---

### Test 5: Token List/Search
**Command:** `python3 scripts/tokens.py list --search USDT --size 3`  
**Result:** Found USDT, jUSDT, USDe with metadata  
**Status:** ✅ Pass

---

### Test 6: Token Info with Market Stats
**Command:** `python3 scripts/tokens.py info EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs`  
**Result:** 
- USDT: $1.00, Volume 24h: $2.88M, TVL: $15.86M
- Trust score: 100
- Holders: 3M+
**Status:** ✅ Pass

---

### Test 7: DNS Resolution
**Command:** `python3 scripts/dns.py resolve foundation.ton`  
**Result:** 
- Resolved to EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N
- Name: "TON Foundation (OLD)"
**Status:** ✅ Pass

---

### Test 8: Yield Pools
**Command:** `python3 scripts/yield_cmd.py pools --size 3`  
**Result:** 
- Found 2000 trusted pools
- Top pools: TON/tsTON (TVL $64.5M, APR 2.96%), TON/STAKED, USDT-SLP
**Status:** ✅ Pass

---

### Test 9: Staking Pools
**Command:** `python3 scripts/staking.py pools`  
**Result:** 
- 6 staking protocols: tonstakers, stakee, bemo, bemo_v2, hipo, kton
- APRs range from 2.9% to 4%
**Status:** ✅ Pass

---

### Test 10: NFT List
**Command:** `WALLET_PASSWORD=test123 python3 scripts/nft.py list --wallet EQDAPfo13Rclr9z3blh0XaFLgXaKmqZM1KiljM1nwi_esRfs`  
**Result:** 0 NFTs found (wallet is new, expected)  
**Status:** ✅ Pass
**Bug:** Wallet label lookup doesn't work with `--wallet skill-test`, must use address

---

### Test 11: Wallet Balance with Jettons
**Command:** `WALLET_PASSWORD=test123 python3 scripts/wallet.py balance skill-test --full`  
**Result:** 
- TON: 19.37
- Jettons: 0.69 USDT
**Status:** ✅ Pass

---

## Bugs Found During Testing

### BUG-009: NFT list doesn't resolve wallet labels
**File:** `dns.py`  
**Description:** `is_ton_domain()` was too permissive - it treated "skill-test" as a potential .ton domain.  
**Root Cause:** Function assumed any alphanumeric string with hyphens could be a domain without .ton suffix.  
**Fix:** Changed `is_ton_domain()` to only return True for strings explicitly ending with ".ton"  
**Status:** ✅ FIXED

---

## Summary

| Category | Tests | Passed | Failed |
|----------|-------|--------|--------|
| Wallet | 2 | 2 | 0 |
| Transfer | 1 | 1 | 0 |
| Swap | 2 | 2 | 0 |
| Tokens | 2 | 2 | 0 |
| DNS | 1 | 1 | 0 |
| Yield | 1 | 1 | 0 |
| Staking | 1 | 1 | 0 |
| NFT | 1 | 1 | 0 |
| **Total** | **11** | **11** | **0** |

**Final Wallet State:**
- TON: 19.373814348
- USDT: 0.690016
- Spent on tests: ~0.63 TON

**Fixes Applied:**
1. Bounce flag handling for uninit wallets (transfer.py)
2. Missing referral parameters in execute_swap (swap.py)
3. is_ton_domain() too permissive in dns.py - fixed to require explicit .ton suffix

**All critical functionality working!** ✅
