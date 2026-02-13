#!/usr/bin/env python3
"""
OpenClaw TON Skill — DCA & Limit Orders via swap.coffee Strategies API

=============================================================================
IMPORTANT: PROXY WALLET DEPLOYMENT REQUIRED
=============================================================================
Before using DCA/limit orders, you MUST deploy a proxy wallet contract.
This is a one-time operation per wallet.

FLOW:
1. check      — Check if proxy wallet exists (GET /v2/strategy/wallets)
2. eligible   — Check if user is eligible for strategies (GET /v2/strategy/eligible)
3. create-proxy — Deploy proxy wallet contract (POST /v2/strategy/create-proxy-wallet)
                  Returns transaction(s) to sign and send
4. create-order — Create DCA/limit order (only works AFTER proxy is deployed)

If step 1 returns no proxy wallets, user must run step 3 first!
=============================================================================

Features:
- Check eligibility for strategies
- Check if proxy wallet is deployed
- Deploy proxy wallet contract (one-time)
- List active DCA/limit orders
- Create new DCA or limit orders
- Cancel existing orders

API Endpoints (v2):
- GET /v2/strategy/eligible?wallet_address=... — check eligibility
- GET /v2/strategy/wallets?wallet_address=... — check proxy wallet status
- POST /v2/strategy/create-proxy-wallet — build proxy deployment transaction
- GET /v2/strategy/orders?wallet_address=... — list orders
- POST /v2/strategy/create-order — create new order
- POST /v2/strategy/cancel-order — cancel order
"""

import os
import sys
import json
import base64
import argparse
import getpass
from pathlib import Path
from typing import Optional, List, Dict

# Локальный импорт
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from utils import api_request, tonapi_request, load_config, is_valid_address

# TON SDK
try:
    from tonsdk.contract.wallet import Wallets, WalletVersionEnum
    from tonsdk.boc import Cell

    TONSDK_AVAILABLE = True
except ImportError:
    TONSDK_AVAILABLE = False


# =============================================================================
# Constants
# =============================================================================

SWAP_COFFEE_API = "https://backend.swap.coffee"

# Order types
ORDER_TYPES = ["dca", "limit"]

# Strategy status
STRATEGY_STATUS = ["active", "completed", "cancelled"]


# =============================================================================
# Swap.coffee API
# =============================================================================


def get_swap_coffee_key() -> Optional[str]:
    """Получает API ключ swap.coffee из конфига."""
    config = load_config()
    return config.get("swap_coffee_key") or None


def swap_coffee_request(
    endpoint: str,
    method: str = "GET",
    params: Optional[dict] = None,
    json_data: Optional[dict] = None,
    version: str = "v2",
) -> dict:
    """
    Запрос к swap.coffee API.

    Args:
        endpoint: Endpoint (например "/strategy/wallets")
        method: HTTP метод
        params: Query параметры
        json_data: JSON body
        version: Версия API ("v1" или "v2")

    Returns:
        dict с результатом
    """
    base_url = f"{SWAP_COFFEE_API}/{version}"
    api_key = get_swap_coffee_key()

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-Api-Key"] = api_key

    return api_request(
        url=f"{base_url}{endpoint}",
        method=method,
        headers=headers,
        params=params,
        json_data=json_data,
    )


def _make_url_safe(address: str) -> str:
    """Конвертирует адрес в URL-safe формат."""
    return address.replace("+", "-").replace("/", "_")


# =============================================================================
# Wallet Storage
# =============================================================================


def get_wallet_from_storage(identifier: str, password: str) -> Optional[dict]:
    """Получает кошелёк из хранилища."""
    try:
        from wallet import WalletStorage
        storage = WalletStorage(password)
        return storage.get_wallet(identifier, include_secrets=True)
    except Exception as e:
        return None


def create_wallet_instance(wallet_data: dict):
    """Создаёт инстанс кошелька для подписания."""
    if not TONSDK_AVAILABLE:
        raise RuntimeError("tonsdk not available")

    mnemonic = wallet_data.get("mnemonic")
    if not mnemonic:
        raise ValueError("Wallet has no mnemonic")

    version_map = {
        "v3r2": WalletVersionEnum.v3r2,
        "v4r2": WalletVersionEnum.v4r2,
    }

    version = wallet_data.get("version", "v4r2")
    wallet_version = version_map.get(version.lower(), WalletVersionEnum.v4r2)

    _, _, _, wallet = Wallets.from_mnemonics(mnemonic, wallet_version, workchain=0)

    return wallet


def get_seqno(address: str) -> int:
    """Получает seqno кошелька."""
    addr_safe = _make_url_safe(address)
    result = tonapi_request(f"/wallet/{addr_safe}/seqno")
    if result["success"]:
        return result["data"].get("seqno", 0)
    return 0


# =============================================================================
# Strategy Wallet & Eligibility
# =============================================================================


def check_eligibility(wallet_address: str) -> dict:
    """
    Проверяет, может ли пользователь использовать стратегии.
    
    Некоторые кошельки могут быть не eligible (например, новые или с низким объёмом).

    Args:
        wallet_address: Адрес кошелька

    Returns:
        dict с информацией об eligibility
    """
    addr_safe = _make_url_safe(wallet_address)

    result = swap_coffee_request(
        "/strategy/eligible",
        params={"wallet_address": addr_safe}
    )

    if not result["success"]:
        # If endpoint doesn't exist or returns error, assume eligible
        if result.get("status_code") == 404:
            return {
                "success": True,
                "wallet_address": wallet_address,
                "eligible": True,
                "message": "Eligibility check not available, assuming eligible"
            }
        return {
            "success": False,
            "error": result.get("error", "Failed to check eligibility"),
            "wallet_address": wallet_address
        }

    data = result["data"]
    eligible = data.get("eligible", True) if isinstance(data, dict) else True

    return {
        "success": True,
        "wallet_address": wallet_address,
        "eligible": eligible,
        "reason": data.get("reason") if isinstance(data, dict) else None,
        "requirements": data.get("requirements") if isinstance(data, dict) else None,
        "message": "Eligible for strategies" if eligible else "Not eligible for strategies"
    }


def check_strategy_wallet(wallet_address: str) -> dict:
    """
    Проверяет, развёрнут ли прокси-кошелёк для стратегий.
    
    ВАЖНО: Перед созданием DCA/limit ордеров необходимо развернуть прокси-кошелёк!
    Это одноразовая операция. Если прокси-кошелёк не найден, используйте 'create-proxy'.

    Args:
        wallet_address: Адрес кошелька

    Returns:
        dict с информацией о прокси-кошельке
    """
    addr_safe = _make_url_safe(wallet_address)

    result = swap_coffee_request(
        "/strategy/wallets",
        params={"wallet_address": addr_safe}
    )

    if not result["success"]:
        # 404 означает, что прокси-кошелёк не развёрнут
        if result.get("status_code") == 404:
            return {
                "success": True,
                "has_proxy": False,
                "wallet_address": wallet_address,
                "proxy_wallets": [],
                "message": "⚠️ Proxy wallet NOT deployed. You must deploy it first using 'create-proxy' command before creating orders.",
                "next_step": "Run: strategies.py create-proxy --wallet <your_wallet> --confirm"
            }
        return {
            "success": False,
            "error": result.get("error", "Failed to check proxy wallet"),
            "wallet_address": wallet_address
        }

    data = result["data"]
    
    # Парсим ответ
    wallets = data if isinstance(data, list) else ([data] if data else [])
    has_proxy = len(wallets) > 0
    
    return {
        "success": True,
        "has_proxy": has_proxy,
        "wallet_address": wallet_address,
        "proxy_wallets": wallets,
        "message": f"✅ Proxy wallet deployed. Found {len(wallets)} proxy wallet(s). Ready to create orders." if has_proxy else "⚠️ No proxy wallets found. Deploy one using 'create-proxy'.",
        "next_step": "Run: strategies.py create-limit/create-dca ..." if has_proxy else "Run: strategies.py create-proxy --wallet <your_wallet> --confirm"
    }


def build_create_proxy_tx(wallet_address: str) -> dict:
    """
    Строит транзакцию для развёртывания прокси-кошелька.
    
    Прокси-кошелёк — это смарт-контракт, который будет исполнять DCA/limit ордера.
    Развёртывание требует отправки транзакции с оплатой gas.

    Args:
        wallet_address: Адрес основного кошелька

    Returns:
        dict с транзакцией для подписания и отправки
    """
    result = swap_coffee_request(
        "/strategy/create-proxy-wallet",
        method="POST",
        json_data={"wallet_address": wallet_address}
    )

    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Failed to build proxy deployment transaction"),
            "wallet_address": wallet_address
        }

    data = result["data"]
    
    # API может вернуть транзакции для подписания
    transactions = data.get("transactions", []) if isinstance(data, dict) else []
    
    # Или может вернуть уже развёрнутый адрес (если уже существует)
    proxy_address = data.get("proxy_address") or data.get("address") if isinstance(data, dict) else None

    return {
        "success": True,
        "wallet_address": wallet_address,
        "transactions": transactions,
        "proxy_address": proxy_address,
        "message": "Proxy wallet deployment transaction ready. Sign and send to deploy." if transactions else "Proxy wallet info retrieved.",
        "note": "This is a one-time deployment. After the transaction is confirmed, you can create DCA/limit orders."
    }


# =============================================================================
# Orders
# =============================================================================


def list_orders(
    wallet_address: str,
    order_type: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """
    Получает список ордеров для кошелька.

    Args:
        wallet_address: Адрес кошелька
        order_type: Фильтр по типу (dca, limit)
        status: Фильтр по статусу (active, completed, cancelled)

    Returns:
        dict со списком ордеров
    """
    addr_safe = _make_url_safe(wallet_address)

    params = {"wallet_address": addr_safe}
    if order_type:
        params["order_type"] = order_type
    if status:
        params["status"] = status

    result = swap_coffee_request("/strategy/orders", params=params)

    if not result["success"]:
        if result.get("status_code") == 404:
            return {
                "success": True,
                "wallet_address": wallet_address,
                "orders": [],
                "orders_count": 0,
                "message": "No orders found"
            }
        return {
            "success": False,
            "error": result.get("error", "Failed to get orders")
        }

    data = result["data"]
    orders = data if isinstance(data, list) else data.get("orders", [])

    # Нормализуем ордера
    normalized = []
    for order in orders:
        normalized.append({
            "id": order.get("id") or order.get("order_id"),
            "type": order.get("type") or order.get("order_type"),
            "status": order.get("status"),
            "input_token": order.get("input_token"),
            "output_token": order.get("output_token"),
            "input_amount": order.get("input_amount"),
            "output_amount": order.get("output_amount"),
            "executed_amount": order.get("executed_amount"),
            "remaining_amount": order.get("remaining_amount"),
            "price": order.get("price") or order.get("target_price"),
            "interval": order.get("interval"),  # For DCA
            "created_at": order.get("created_at"),
            "raw": order
        })

    return {
        "success": True,
        "wallet_address": wallet_address,
        "orders": normalized,
        "orders_count": len(normalized),
        "filters": {
            "order_type": order_type,
            "status": status
        }
    }


def get_order(order_id: str, wallet_address: str) -> dict:
    """
    Получает детали конкретного ордера.

    Args:
        order_id: ID ордера
        wallet_address: Адрес кошелька

    Returns:
        dict с деталями ордера
    """
    result = swap_coffee_request(
        f"/strategy/orders/{order_id}",
        params={"wallet_address": _make_url_safe(wallet_address)}
    )

    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Order not found"),
            "order_id": order_id
        }

    return {
        "success": True,
        "order": result["data"]
    }


def build_create_order_tx(
    wallet_address: str,
    order_type: str,
    input_token: str,
    output_token: str,
    input_amount: float,
    target_price: Optional[float] = None,
    interval_hours: Optional[int] = None,
    total_orders: Optional[int] = None,
) -> dict:
    """
    Строит транзакцию для создания ордера.

    Args:
        wallet_address: Адрес кошелька
        order_type: Тип ордера (dca, limit)
        input_token: Входной токен (адрес или символ)
        output_token: Выходной токен
        input_amount: Сумма входного токена
        target_price: Целевая цена (для limit)
        interval_hours: Интервал между покупками в часах (для dca)
        total_orders: Количество покупок (для dca)

    Returns:
        dict с транзакцией для подписания
    """
    # Валидация
    if order_type not in ORDER_TYPES:
        return {
            "success": False,
            "error": f"Invalid order type. Must be one of: {ORDER_TYPES}"
        }

    if order_type == "limit" and not target_price:
        return {
            "success": False,
            "error": "target_price required for limit orders"
        }

    if order_type == "dca":
        if not interval_hours or not total_orders:
            return {
                "success": False,
                "error": "interval_hours and total_orders required for DCA orders"
            }

    # Формируем запрос
    order_data = {
        "wallet_address": wallet_address,
        "order_type": order_type,
        "input_token": {"blockchain": "ton", "address": input_token},
        "output_token": {"blockchain": "ton", "address": output_token},
        "input_amount": input_amount,
    }

    if order_type == "limit":
        order_data["target_price"] = target_price

    if order_type == "dca":
        order_data["interval_seconds"] = interval_hours * 3600
        order_data["total_orders"] = total_orders
        order_data["amount_per_order"] = input_amount / total_orders

    result = swap_coffee_request(
        "/strategy/create-order",
        method="POST",
        json_data=order_data
    )

    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Failed to build order transaction")
        }

    data = result["data"]

    return {
        "success": True,
        "order_type": order_type,
        "transactions": data.get("transactions", []),
        "order_preview": {
            "input_token": input_token,
            "output_token": output_token,
            "input_amount": input_amount,
            "target_price": target_price,
            "interval_hours": interval_hours,
            "total_orders": total_orders,
        },
        "raw_response": data
    }


def build_cancel_order_tx(order_id: str, wallet_address: str) -> dict:
    """
    Строит транзакцию для отмены ордера.

    Args:
        order_id: ID ордера для отмены
        wallet_address: Адрес кошелька

    Returns:
        dict с транзакцией для подписания
    """
    result = swap_coffee_request(
        "/strategy/cancel-order",
        method="POST",
        json_data={
            "order_id": order_id,
            "wallet_address": wallet_address
        }
    )

    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Failed to build cancel transaction"),
            "order_id": order_id
        }

    data = result["data"]

    return {
        "success": True,
        "order_id": order_id,
        "transactions": data.get("transactions", []),
        "raw_response": data
    }


# =============================================================================
# Transaction Execution
# =============================================================================


def emulate_transaction(boc_b64: str) -> dict:
    """Эмулирует транзакцию."""
    result = tonapi_request(
        "/wallet/emulate",
        method="POST",
        json_data={"boc": boc_b64}
    )

    if not result["success"]:
        return {"success": False, "error": result.get("error")}

    data = result["data"]
    event = data.get("event", data)
    extra = event.get("extra", 0)
    fee = abs(extra) if extra < 0 else 0

    return {
        "success": True,
        "fee_nano": fee,
        "fee_ton": fee / 1e9,
        "actions": event.get("actions", []),
    }


def send_transaction(boc_b64: str) -> dict:
    """Отправляет транзакцию."""
    result = tonapi_request(
        "/blockchain/message",
        method="POST",
        json_data={"boc": boc_b64}
    )

    if not result["success"]:
        return {"success": False, "error": result.get("error")}

    return {"success": True, "data": result.get("data")}


def execute_strategy_tx(
    wallet_label: str,
    transactions: List[dict],
    password: str,
    confirm: bool = False
) -> dict:
    """
    Выполняет транзакции стратегии.

    Args:
        wallet_label: Лейбл кошелька
        transactions: Список транзакций от API
        password: Пароль кошелька
        confirm: Подтверждение выполнения

    Returns:
        dict с результатом
    """
    if not TONSDK_AVAILABLE:
        return {"success": False, "error": "tonsdk not installed"}

    # Получаем кошелёк
    wallet_data = get_wallet_from_storage(wallet_label, password)
    if not wallet_data:
        return {"success": False, "error": f"Wallet not found: {wallet_label}"}

    sender_address = wallet_data["address"]
    wallet = create_wallet_instance(wallet_data)
    seqno = get_seqno(sender_address)

    signed_txs = []
    total_fee = 0

    for i, tx in enumerate(transactions):
        to_addr = tx.get("address")
        amount = int(tx.get("value", "0"))
        cell_b64 = tx.get("cell")
        send_mode = tx.get("send_mode", 3)

        if not to_addr:
            continue

        payload = None
        if cell_b64:
            try:
                cell_bytes = base64.b64decode(cell_b64)
                payload = Cell.one_from_boc(cell_bytes)
            except Exception as e:
                return {"success": False, "error": f"Failed to decode cell: {e}"}

        try:
            query = wallet.create_transfer_message(
                to_addr=to_addr,
                amount=amount,
                payload=payload,
                seqno=seqno + i,
                send_mode=send_mode,
            )
        except Exception as e:
            return {"success": False, "error": f"Failed to create transfer: {e}"}

        boc = query["message"].to_boc(False)
        boc_b64 = base64.b64encode(boc).decode("ascii")

        emulation = emulate_transaction(boc_b64)

        signed_txs.append({
            "index": i,
            "to": to_addr,
            "amount_nano": amount,
            "amount_ton": amount / 1e9,
            "boc": boc_b64,
            "emulation": emulation,
        })

        if emulation["success"]:
            total_fee += emulation.get("fee_nano", 0)

    result = {
        "wallet": sender_address,
        "transactions": signed_txs,
        "total_fee_nano": total_fee,
        "total_fee_ton": total_fee / 1e9,
    }

    if confirm:
        sent_count = 0
        errors = []

        for tx in signed_txs:
            send_result = send_transaction(tx["boc"])
            if send_result["success"]:
                sent_count += 1
            else:
                errors.append(send_result.get("error"))

        result["sent_count"] = sent_count
        result["total_transactions"] = len(signed_txs)

        if sent_count == len(signed_txs):
            result["success"] = True
            result["message"] = "Transaction executed successfully"
        else:
            result["success"] = False
            result["error"] = "Failed to send transactions"
            result["errors"] = errors
    else:
        result["success"] = True
        result["confirmed"] = False
        result["message"] = "Transaction simulated. Use --confirm to execute."

    return result


# =============================================================================
# CLI
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="DCA & Limit Orders via swap.coffee Strategies API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
================================================================================
IMPORTANT: PROXY WALLET REQUIRED
================================================================================
Before creating DCA/limit orders, you MUST deploy a proxy wallet contract.
This is a one-time operation per wallet.

RECOMMENDED FLOW:
  1. %(prog)s check --wallet UQBvW8...     # Check if proxy exists
  2. %(prog)s eligible --wallet UQBvW8...  # Check eligibility (optional)
  3. %(prog)s create-proxy --wallet main --confirm  # Deploy proxy (one-time)
  4. %(prog)s create-limit/create-dca ...  # Create orders

================================================================================

Examples:
  # Check proxy wallet status (REQUIRED first step)
  %(prog)s check --address UQBvW8...
  
  # Check eligibility for strategies
  %(prog)s eligible --address UQBvW8...
  
  # Deploy proxy wallet (one-time, requires --confirm)
  %(prog)s create-proxy --wallet main --confirm
  
  # List active orders
  %(prog)s list --wallet main --status active
  
  # Create a limit order (execute when price reaches target)
  %(prog)s create-limit --wallet main --from TON --to USDT --amount 10 --price 5.5 --confirm
  
  # Create a DCA order (buy USDT with 100 TON over 10 orders, every 24 hours)
  %(prog)s create-dca --wallet main --from TON --to USDT --amount 100 --orders 10 --interval 24 --confirm
  
  # Cancel an order
  %(prog)s cancel --wallet main --order-id abc123 --confirm

Order Types:
  - limit: Execute when target price is reached
  - dca: Dollar Cost Averaging - split purchase over time intervals
"""
    )

    parser.add_argument(
        "--password", "-p", help="Wallet password (or WALLET_PASSWORD env)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # --- check (alias for check-wallet) ---
    check_p = subparsers.add_parser("check", help="Check if proxy wallet is deployed (required before orders)")
    check_p.add_argument("--address", "-a", required=True, help="Wallet address")
    
    # --- check-wallet (legacy, same as check) ---
    check_wallet_p = subparsers.add_parser("check-wallet", help="Alias for 'check'")
    check_wallet_p.add_argument("--address", "-a", required=True, help="Wallet address")

    # --- eligible ---
    eligible_p = subparsers.add_parser("eligible", help="Check if wallet is eligible for strategies")
    eligible_p.add_argument("--address", "-a", required=True, help="Wallet address")

    # --- create-proxy ---
    proxy_p = subparsers.add_parser("create-proxy", help="Deploy proxy wallet contract (one-time)")
    proxy_p.add_argument("--wallet", "-w", required=True, help="Wallet label or address")
    proxy_p.add_argument("--confirm", action="store_true", help="Confirm execution (required to deploy)")

    # --- list ---
    list_p = subparsers.add_parser("list", help="List strategy orders")
    list_p.add_argument("--wallet", "-w", required=True, help="Wallet label or address")
    list_p.add_argument("--type", "-t", choices=ORDER_TYPES, help="Filter by order type")
    list_p.add_argument("--status", "-s", choices=STRATEGY_STATUS, help="Filter by status")

    # --- get ---
    get_p = subparsers.add_parser("get", help="Get order details")
    get_p.add_argument("--wallet", "-w", required=True, help="Wallet address")
    get_p.add_argument("--order-id", "-o", required=True, help="Order ID")

    # --- create-limit ---
    limit_p = subparsers.add_parser("create-limit", help="Create limit order")
    limit_p.add_argument("--wallet", "-w", required=True, help="Wallet label")
    limit_p.add_argument("--from", "-f", dest="input_token", required=True, help="Input token")
    limit_p.add_argument("--to", "-t", dest="output_token", required=True, help="Output token")
    limit_p.add_argument("--amount", "-a", type=float, required=True, help="Input amount")
    limit_p.add_argument("--price", type=float, required=True, help="Target price")
    limit_p.add_argument("--confirm", action="store_true", help="Confirm execution")

    # --- create-dca ---
    dca_p = subparsers.add_parser("create-dca", help="Create DCA order")
    dca_p.add_argument("--wallet", "-w", required=True, help="Wallet label")
    dca_p.add_argument("--from", "-f", dest="input_token", required=True, help="Input token")
    dca_p.add_argument("--to", "-t", dest="output_token", required=True, help="Output token")
    dca_p.add_argument("--amount", "-a", type=float, required=True, help="Total input amount")
    dca_p.add_argument("--orders", "-n", type=int, required=True, help="Number of orders")
    dca_p.add_argument("--interval", "-i", type=int, required=True, help="Interval in hours")
    dca_p.add_argument("--confirm", action="store_true", help="Confirm execution")

    # --- cancel ---
    cancel_p = subparsers.add_parser("cancel", help="Cancel an order")
    cancel_p.add_argument("--wallet", "-w", required=True, help="Wallet label")
    cancel_p.add_argument("--order-id", "-o", required=True, help="Order ID")
    cancel_p.add_argument("--confirm", action="store_true", help="Confirm execution")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        password = args.password or os.environ.get("WALLET_PASSWORD")

        if args.command in ("check", "check-wallet"):
            result = check_strategy_wallet(args.address)

        elif args.command == "eligible":
            result = check_eligibility(args.address)

        elif args.command == "create-proxy":
            # Resolve wallet address
            wallet_addr = args.wallet
            if not is_valid_address(wallet_addr):
                if not password:
                    if sys.stdin.isatty():
                        password = getpass.getpass("Wallet password: ")
                    else:
                        print(json.dumps({"error": "Password required"}))
                        sys.exit(1)
                wallet_data = get_wallet_from_storage(wallet_addr, password)
                if wallet_data:
                    wallet_addr = wallet_data["address"]
                else:
                    print(json.dumps({"error": f"Wallet not found: {args.wallet}"}))
                    sys.exit(1)

            # Build the proxy deployment transaction
            tx_result = build_create_proxy_tx(wallet_addr)
            
            if not tx_result["success"]:
                result = tx_result
            elif tx_result.get("transactions"):
                # Execute the deployment transaction
                if not password:
                    if sys.stdin.isatty():
                        password = getpass.getpass("Wallet password: ")
                    else:
                        print(json.dumps({"error": "Password required for signing"}))
                        sys.exit(1)
                
                result = execute_strategy_tx(
                    wallet_label=args.wallet,
                    transactions=tx_result["transactions"],
                    password=password,
                    confirm=args.confirm
                )
                result["operation"] = "deploy_proxy_wallet"
                result["proxy_address"] = tx_result.get("proxy_address")
                
                if args.confirm and result.get("success"):
                    result["message"] = "✅ Proxy wallet deployed! You can now create DCA/limit orders."
                    result["next_step"] = "Run: strategies.py create-limit/create-dca ..."
            elif tx_result.get("proxy_address"):
                # Proxy already exists
                result = {
                    "success": True,
                    "message": "Proxy wallet already exists",
                    "proxy_address": tx_result.get("proxy_address"),
                    "next_step": "Run: strategies.py create-limit/create-dca ..."
                }
            else:
                result = tx_result

        elif args.command == "list":
            # Resolve wallet address
            wallet_addr = args.wallet
            if not is_valid_address(wallet_addr):
                if password:
                    wallet_data = get_wallet_from_storage(wallet_addr, password)
                    if wallet_data:
                        wallet_addr = wallet_data["address"]

            result = list_orders(
                wallet_address=wallet_addr,
                order_type=args.type,
                status=args.status
            )

        elif args.command == "get":
            result = get_order(args.order_id, args.wallet)

        elif args.command == "create-limit":
            if not password:
                if sys.stdin.isatty():
                    password = getpass.getpass("Wallet password: ")
                else:
                    print(json.dumps({"error": "Password required"}))
                    sys.exit(1)

            wallet_data = get_wallet_from_storage(args.wallet, password)
            if not wallet_data:
                print(json.dumps({"error": f"Wallet not found: {args.wallet}"}))
                sys.exit(1)

            tx_result = build_create_order_tx(
                wallet_address=wallet_data["address"],
                order_type="limit",
                input_token=args.input_token,
                output_token=args.output_token,
                input_amount=args.amount,
                target_price=args.price
            )

            if not tx_result["success"]:
                result = tx_result
            elif tx_result.get("transactions"):
                result = execute_strategy_tx(
                    wallet_label=args.wallet,
                    transactions=tx_result["transactions"],
                    password=password,
                    confirm=args.confirm
                )
                result["order_preview"] = tx_result.get("order_preview")
            else:
                result = tx_result

        elif args.command == "create-dca":
            if not password:
                if sys.stdin.isatty():
                    password = getpass.getpass("Wallet password: ")
                else:
                    print(json.dumps({"error": "Password required"}))
                    sys.exit(1)

            wallet_data = get_wallet_from_storage(args.wallet, password)
            if not wallet_data:
                print(json.dumps({"error": f"Wallet not found: {args.wallet}"}))
                sys.exit(1)

            tx_result = build_create_order_tx(
                wallet_address=wallet_data["address"],
                order_type="dca",
                input_token=args.input_token,
                output_token=args.output_token,
                input_amount=args.amount,
                interval_hours=args.interval,
                total_orders=args.orders
            )

            if not tx_result["success"]:
                result = tx_result
            elif tx_result.get("transactions"):
                result = execute_strategy_tx(
                    wallet_label=args.wallet,
                    transactions=tx_result["transactions"],
                    password=password,
                    confirm=args.confirm
                )
                result["order_preview"] = tx_result.get("order_preview")
            else:
                result = tx_result

        elif args.command == "cancel":
            if not password:
                if sys.stdin.isatty():
                    password = getpass.getpass("Wallet password: ")
                else:
                    print(json.dumps({"error": "Password required"}))
                    sys.exit(1)

            wallet_data = get_wallet_from_storage(args.wallet, password)
            if not wallet_data:
                print(json.dumps({"error": f"Wallet not found: {args.wallet}"}))
                sys.exit(1)

            tx_result = build_cancel_order_tx(args.order_id, wallet_data["address"])

            if not tx_result["success"]:
                result = tx_result
            elif tx_result.get("transactions"):
                result = execute_strategy_tx(
                    wallet_label=args.wallet,
                    transactions=tx_result["transactions"],
                    password=password,
                    confirm=args.confirm
                )
                result["cancelled_order_id"] = args.order_id
            else:
                result = tx_result

        else:
            result = {"error": f"Unknown command: {args.command}"}

        print(json.dumps(result, indent=2, ensure_ascii=False))

        if not result.get("success", False):
            sys.exit(1)

    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
