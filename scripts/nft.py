#!/usr/bin/env python3
"""
OpenClaw TON Skill — NFT операции

- Список NFT в кошельке
- Информация об NFT
- Информация о коллекции
- Трансфер NFT (с эмуляцией)
- Поиск коллекций
"""

import os
import sys
import json
import base64
import argparse
import getpass
from pathlib import Path
from typing import Optional, List, Dict, Any

# Локальный импорт
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from utils import (
    tonapi_request,
    is_valid_address,
    normalize_address,
    raw_to_friendly,
    friendly_to_raw,
    load_config
)
from dns import resolve_address, is_ton_domain
from wallet import WalletStorage, get_account_info

# TON SDK
try:
    from tonsdk.contract.wallet import Wallets, WalletVersionEnum
    from tonsdk.utils import to_nano, from_nano
    from tonsdk.boc import Cell
    TONSDK_AVAILABLE = True
except ImportError:
    TONSDK_AVAILABLE = False


# =============================================================================
# Constants
# =============================================================================

# NFT Transfer opcode (TEP-62)
NFT_TRANSFER_OPCODE = 0x5fcc3d14


# =============================================================================
# Wallet Helpers
# =============================================================================

def get_wallet_from_storage(identifier: str, password: str) -> Optional[dict]:
    """Получает кошелёк из хранилища с приватными данными."""
    storage = WalletStorage(password)
    return storage.get_wallet(identifier, include_secrets=True)


def create_wallet_instance(wallet_data: dict):
    """Создаёт инстанс кошелька для подписания."""
    if not TONSDK_AVAILABLE:
        raise RuntimeError("tonsdk not available. Install: pip install tonsdk")
    
    mnemonic = wallet_data.get("mnemonic")
    if not mnemonic:
        raise ValueError("Wallet has no mnemonic")
    
    version_map = {
        "v3r2": WalletVersionEnum.v3r2,
        "v4r2": WalletVersionEnum.v4r2,
    }
    
    version = wallet_data.get("version", "v4r2")
    wallet_version = version_map.get(version.lower(), WalletVersionEnum.v4r2)
    
    mnemonics, pub_k, priv_k, wallet = Wallets.from_mnemonics(
        mnemonic,
        wallet_version,
        workchain=0
    )
    
    return wallet


def get_seqno(address: str) -> int:
    """Получает текущий seqno кошелька."""
    result = tonapi_request(f"/wallet/{address}/seqno")
    
    if result["success"]:
        return result["data"].get("seqno", 0)
    
    return 0


# =============================================================================
# NFT List
# =============================================================================

def looks_like_address(s: str) -> bool:
    """Быстрая проверка - похоже ли на TON адрес."""
    if not s:
        return False
    # Raw формат: 0:abc123...
    if ':' in s and len(s) > 40:
        return True
    # Friendly формат: UQ..., EQ..., kQ..., 0Q...
    if len(s) >= 48 and s[:2] in ('UQ', 'EQ', 'kQ', '0Q', 'Uf', 'Ef', 'kf', '0f'):
        return True
    return False


def list_nfts(wallet_identifier: str, password: Optional[str] = None, limit: int = 100) -> dict:
    """
    Получает список NFT в кошельке.
    
    Args:
        wallet_identifier: Лейбл или адрес кошелька
        password: Пароль (нужен если ищем по лейблу)
        limit: Максимальное количество NFT
    
    Returns:
        dict со списком NFT
    """
    # Резолвим адрес кошелька
    address = None
    
    # Сначала пробуем как адрес
    if looks_like_address(wallet_identifier):
        address = wallet_identifier
    elif is_ton_domain(wallet_identifier):
        resolved = resolve_address(wallet_identifier)
        if resolved["success"]:
            address = resolved["address"]
    else:
        # Ищем в хранилище по лейблу
        if password:
            try:
                storage = WalletStorage(password)
                wallet_data = storage.get_wallet(wallet_identifier, include_secrets=False)
                if wallet_data:
                    address = wallet_data["address"]
            except:
                pass
    
    if not address:
        return {
            "success": False,
            "error": f"Cannot resolve wallet: {wallet_identifier}"
        }
    
    # Нормализуем адрес для API
    try:
        api_address = normalize_address(address, "friendly")
    except:
        api_address = address
    
    # Запрос к TonAPI
    result = tonapi_request(
        f"/accounts/{api_address}/nfts",
        params={"limit": limit, "indirect_ownership": "true"}
    )
    
    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Failed to fetch NFTs")
        }
    
    data = result["data"]
    nft_items = data.get("nft_items", [])
    
    # Парсим NFT
    nfts = []
    for item in nft_items:
        metadata = item.get("metadata", {})
        collection = item.get("collection", {})
        previews = item.get("previews", [])
        
        # Выбираем превью (предпочитаем среднее разрешение)
        preview_url = None
        for p in previews:
            if p.get("resolution") == "500x500":
                preview_url = p.get("url")
                break
        if not preview_url and previews:
            preview_url = previews[0].get("url")
        
        nft = {
            "address": item.get("address"),
            "index": item.get("index"),
            "name": metadata.get("name") or item.get("dns") or f"NFT #{item.get('index', '?')}",
            "description": metadata.get("description"),
            "preview_url": preview_url,
            "collection": {
                "address": collection.get("address"),
                "name": collection.get("name"),
            } if collection else None,
            "verified": item.get("verified", False),
            "owner": item.get("owner", {}).get("address"),
        }
        
        # DNS домен?
        if item.get("dns"):
            nft["dns_domain"] = item.get("dns")
        
        nfts.append(nft)
    
    return {
        "success": True,
        "wallet": api_address,
        "count": len(nfts),
        "nfts": nfts
    }


# =============================================================================
# NFT Info
# =============================================================================

def get_nft_info(nft_address: str) -> dict:
    """
    Получает детальную информацию об NFT.
    
    Args:
        nft_address: Адрес NFT
    
    Returns:
        dict с информацией об NFT
    """
    # Нормализуем адрес
    try:
        api_address = normalize_address(nft_address, "friendly")
    except:
        api_address = nft_address
    
    result = tonapi_request(f"/nfts/{api_address}")
    
    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Failed to fetch NFT info")
        }
    
    item = result["data"]
    metadata = item.get("metadata", {})
    collection = item.get("collection", {})
    previews = item.get("previews", [])
    
    # Все превью
    preview_urls = {}
    for p in previews:
        resolution = p.get("resolution", "unknown")
        preview_urls[resolution] = p.get("url")
    
    # Атрибуты (traits)
    attributes = metadata.get("attributes", [])
    traits = []
    for attr in attributes:
        traits.append({
            "trait": attr.get("trait_type"),
            "value": attr.get("value")
        })
    
    # Sale info
    sale = item.get("sale")
    sale_info = None
    if sale:
        sale_info = {
            "marketplace": sale.get("market", {}).get("name"),
            "price_nano": sale.get("price", {}).get("value"),
            "price_ton": int(sale.get("price", {}).get("value", 0)) / 1e9 if sale.get("price", {}).get("token_name") == "TON" else None,
            "token": sale.get("price", {}).get("token_name"),
        }
    
    return {
        "success": True,
        "address": item.get("address"),
        "index": item.get("index"),
        "name": metadata.get("name") or item.get("dns") or f"NFT #{item.get('index', '?')}",
        "description": metadata.get("description"),
        "image": metadata.get("image"),
        "previews": preview_urls,
        "traits": traits,
        "owner": {
            "address": item.get("owner", {}).get("address"),
            "name": item.get("owner", {}).get("name"),
        },
        "collection": {
            "address": collection.get("address"),
            "name": collection.get("name"),
            "description": collection.get("description"),
        } if collection else None,
        "verified": item.get("verified", False),
        "approved_by": item.get("approved_by", []),
        "dns_domain": item.get("dns"),
        "sale": sale_info,
        "metadata_url": item.get("metadata", {}).get("external_url"),
    }


# =============================================================================
# Collection Info
# =============================================================================

def get_collection_info(collection_address: str) -> dict:
    """
    Получает информацию о коллекции NFT.
    
    Args:
        collection_address: Адрес коллекции
    
    Returns:
        dict с информацией о коллекции
    """
    # Нормализуем адрес
    try:
        api_address = normalize_address(collection_address, "friendly")
    except:
        api_address = collection_address
    
    result = tonapi_request(f"/nfts/collections/{api_address}")
    
    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Failed to fetch collection info")
        }
    
    data = result["data"]
    metadata = data.get("metadata", {})
    previews = data.get("previews", [])
    
    # Превью
    preview_url = None
    for p in previews:
        if p.get("resolution") == "500x500":
            preview_url = p.get("url")
            break
    if not preview_url and previews:
        preview_url = previews[0].get("url")
    
    # Социальные ссылки
    social_links = metadata.get("social_links", [])
    
    return {
        "success": True,
        "address": data.get("address"),
        "name": metadata.get("name") or data.get("name"),
        "description": metadata.get("description") or data.get("description"),
        "image": metadata.get("image"),
        "preview_url": preview_url,
        "items_count": data.get("next_item_index", 0),
        "owner": {
            "address": data.get("owner", {}).get("address"),
            "name": data.get("owner", {}).get("name"),
        } if data.get("owner") else None,
        "social_links": social_links,
        "verified": data.get("verified", False),
        "approved_by": data.get("approved_by", []),
    }


# =============================================================================
# Search Collections
# =============================================================================

def search_collections(query: str, limit: int = 10) -> dict:
    """
    Поиск коллекций NFT по названию.
    
    Args:
        query: Поисковый запрос
        limit: Максимальное количество результатов
    
    Returns:
        dict со списком коллекций
    """
    # TonAPI не имеет прямого поиска коллекций,
    # используем общий поиск accounts
    result = tonapi_request(
        "/accounts/search",
        params={"name": query}
    )
    
    collections = []
    
    if result["success"]:
        addresses = result["data"].get("addresses", [])
        
        # Фильтруем только коллекции (проверяем тип аккаунта)
        for addr_info in addresses[:limit * 2]:  # Берём больше, т.к. будем фильтровать
            address = addr_info.get("address")
            name = addr_info.get("name")
            
            # Проверяем является ли это коллекцией
            # Делаем запрос к collection endpoint
            coll_result = tonapi_request(f"/nfts/collections/{address}")
            
            if coll_result["success"]:
                coll_data = coll_result["data"]
                metadata = coll_data.get("metadata", {})
                
                collections.append({
                    "address": address,
                    "name": metadata.get("name") or name or "Unknown",
                    "description": metadata.get("description"),
                    "items_count": coll_data.get("next_item_index", 0),
                    "verified": coll_data.get("verified", False),
                })
                
                if len(collections) >= limit:
                    break
    
    # Альтернативный поиск через getgems API (если TonAPI не даёт результатов)
    # или через список известных коллекций
    
    return {
        "success": True,
        "query": query,
        "count": len(collections),
        "collections": collections
    }


# =============================================================================
# NFT Transfer
# =============================================================================

def build_nft_transfer(
    wallet,
    nft_address: str,
    to_address: str,
    response_address: str,
    forward_amount: int = 1,
    seqno: int = 0
) -> bytes:
    """
    Строит транзакцию трансфера NFT (TEP-62).
    
    Args:
        wallet: Инстанс кошелька (tonsdk)
        nft_address: Адрес NFT контракта
        to_address: Адрес нового владельца
        response_address: Куда отправить excess (обычно = отправитель)
        forward_amount: Сколько TON форвардить новому владельцу
        seqno: Sequence number
    
    Returns:
        bytes BOC
    """
    from tonsdk.boc import Cell
    from tonsdk.utils import Address
    
    # NFT Transfer payload (TEP-62)
    # https://github.com/ton-blockchain/TEPs/blob/master/text/0062-nft-standard.md
    payload = Cell()
    payload.bits.write_uint(NFT_TRANSFER_OPCODE, 32)  # op: transfer
    payload.bits.write_uint(0, 64)  # query_id
    payload.bits.write_address(Address(to_address))  # new_owner
    payload.bits.write_address(Address(response_address))  # response_destination
    payload.bits.write_bit(0)  # custom_payload = null
    payload.bits.write_coins(forward_amount)  # forward_amount (1 nano для уведомления)
    payload.bits.write_bit(0)  # forward_payload in-place (empty)
    
    # Создаём транзакцию на NFT контракт
    # Нужно отправить ~0.05 TON для покрытия комиссии
    query = wallet.create_transfer_message(
        to_addr=nft_address,
        amount=to_nano(0.05, "ton"),  # 0.05 TON для газа
        payload=payload,
        seqno=seqno
    )
    
    return query["message"].to_boc(False)


def emulate_transfer(boc_b64: str, wallet_address: str) -> dict:
    """
    Эмулирует транзакцию через TonAPI.
    """
    result = tonapi_request(
        "/wallet/emulate",
        method="POST",
        json_data={"boc": boc_b64}
    )
    
    if not result["success"]:
        result = tonapi_request(
            "/events/emulate",
            method="POST",
            json_data={"boc": boc_b64}
        )
    
    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Emulation failed")
        }
    
    data = result["data"]
    event = data.get("event", data)
    actions = event.get("actions", [])
    
    # Комиссия
    extra = event.get("extra", 0)
    fee = abs(extra) if extra < 0 else 0
    
    # Ищем NFT transfer action
    nft_transfer = None
    for action in actions:
        if action.get("type") == "NftItemTransfer":
            nft_transfer = action.get("NftItemTransfer", {})
            break
    
    return {
        "success": True,
        "fee_nano": fee,
        "fee_ton": fee / 1e9,
        "nft_transfer": nft_transfer,
        "actions_count": len(actions),
        "risk": event.get("risk", {}),
    }


def send_transaction(boc_b64: str) -> dict:
    """Отправляет транзакцию в сеть."""
    result = tonapi_request(
        "/blockchain/message",
        method="POST",
        json_data={"boc": boc_b64}
    )
    
    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Failed to send transaction")
        }
    
    return {
        "success": True,
        "message": "Transaction sent"
    }


def transfer_nft(
    nft_address: str,
    from_wallet: str,
    to_address: str,
    password: str,
    confirm: bool = False
) -> dict:
    """
    Переводит NFT на другой адрес.
    
    Args:
        nft_address: Адрес NFT
        from_wallet: Лейбл или адрес кошелька-отправителя (владельца)
        to_address: Адрес или .ton домен получателя
        password: Пароль от хранилища
        confirm: Выполнить перевод (иначе только эмуляция)
    
    Returns:
        dict с результатом
    """
    if not TONSDK_AVAILABLE:
        return {"success": False, "error": "tonsdk not installed"}
    
    # 1. Резолвим адрес получателя
    resolved = resolve_address(to_address)
    if not resolved["success"]:
        return {
            "success": False,
            "error": f"Cannot resolve recipient: {resolved.get('error')}"
        }
    recipient = resolved["address"]
    
    # 2. Получаем кошелёк отправителя
    wallet_data = get_wallet_from_storage(from_wallet, password)
    if not wallet_data:
        return {
            "success": False,
            "error": f"Wallet not found: {from_wallet}"
        }
    
    wallet = create_wallet_instance(wallet_data)
    sender_address = wallet_data["address"]
    
    # 3. Проверяем что NFT принадлежит отправителю
    nft_info = get_nft_info(nft_address)
    if not nft_info["success"]:
        return {
            "success": False,
            "error": f"Cannot fetch NFT info: {nft_info.get('error')}"
        }
    
    nft_owner = nft_info.get("owner", {}).get("address")
    
    # Нормализуем для сравнения
    try:
        sender_raw = normalize_address(sender_address, "raw")
        owner_raw = normalize_address(nft_owner, "raw") if nft_owner else None
    except:
        sender_raw = sender_address
        owner_raw = nft_owner
    
    if owner_raw != sender_raw:
        return {
            "success": False,
            "error": f"NFT is not owned by this wallet. Owner: {nft_owner}"
        }
    
    # 4. Нормализуем адрес NFT
    try:
        nft_addr_friendly = normalize_address(nft_address, "friendly")
    except:
        nft_addr_friendly = nft_address
    
    # 5. Получаем seqno
    seqno = get_seqno(sender_address)
    
    # 6. Строим транзакцию
    boc = build_nft_transfer(
        wallet=wallet,
        nft_address=nft_addr_friendly,
        to_address=recipient,
        response_address=sender_address,
        forward_amount=1,  # 1 нано-TON
        seqno=seqno
    )
    boc_b64 = base64.b64encode(boc).decode('ascii')
    
    # 7. Эмулируем
    emulation = emulate_transfer(boc_b64, sender_address)
    
    result = {
        "action": "transfer_nft",
        "nft": {
            "address": nft_address,
            "name": nft_info.get("name"),
            "collection": nft_info.get("collection", {}).get("name") if nft_info.get("collection") else None,
        },
        "from": sender_address,
        "to": recipient,
        "to_input": to_address,
        "is_domain": resolved.get("is_domain", False),
        "emulation": emulation
    }
    
    if not emulation["success"]:
        result["success"] = False
        result["error"] = emulation.get("error", "Emulation failed")
        return result
    
    result["fee_ton"] = emulation["fee_ton"]
    
    # 8. Отправляем если confirm
    if confirm:
        send_result = send_transaction(boc_b64)
        result["sent"] = send_result["success"]
        if send_result["success"]:
            result["success"] = True
            result["message"] = "NFT transfer sent successfully"
        else:
            result["success"] = False
            result["error"] = send_result.get("error", "Failed to send")
    else:
        result["success"] = True
        result["confirmed"] = False
        result["message"] = "Emulation successful. Use --confirm to send."
    
    return result


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="NFT operations on TON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Список NFT в кошельке (по лейблу)
  %(prog)s list --wallet trading
  
  # Список NFT по адресу
  %(prog)s list --wallet UQBvW8...
  
  # Информация об NFT
  %(prog)s info --address EQC7...
  
  # Информация о коллекции
  %(prog)s collection --address EQCV...
  
  # Поиск коллекций
  %(prog)s search --query "TON Diamonds"
  
  # Эмуляция трансфера NFT
  %(prog)s transfer --nft EQC7... --from trading --to wallet.ton
  
  # Трансфер NFT с подтверждением
  %(prog)s transfer --nft EQC7... --from trading --to UQBvW8... --confirm
"""
    )
    
    parser.add_argument("--password", "-p", help="Wallet password (or WALLET_PASSWORD env)")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # --- list ---
    list_p = subparsers.add_parser("list", help="List NFTs in wallet")
    list_p.add_argument("--wallet", "-w", required=True, help="Wallet label, address or .ton domain")
    list_p.add_argument("--limit", "-l", type=int, default=100, help="Max NFTs to fetch")
    
    # --- info ---
    info_p = subparsers.add_parser("info", help="Get NFT details")
    info_p.add_argument("--address", "-a", required=True, help="NFT address")
    
    # --- collection ---
    coll_p = subparsers.add_parser("collection", help="Get collection info")
    coll_p.add_argument("--address", "-a", required=True, help="Collection address")
    
    # --- search ---
    search_p = subparsers.add_parser("search", help="Search collections")
    search_p.add_argument("--query", "-q", required=True, help="Search query")
    search_p.add_argument("--limit", "-l", type=int, default=10, help="Max results")
    
    # --- transfer ---
    transfer_p = subparsers.add_parser("transfer", help="Transfer NFT")
    transfer_p.add_argument("--nft", "-n", required=True, help="NFT address")
    transfer_p.add_argument("--from", "-f", dest="from_wallet", required=True, help="Sender wallet (label or address)")
    transfer_p.add_argument("--to", "-t", required=True, help="Recipient (address or .ton domain)")
    transfer_p.add_argument("--confirm", action="store_true", help="Confirm and send")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Получаем пароль если нужен
    password = args.password or os.environ.get("WALLET_PASSWORD")
    needs_password = args.command in ["transfer"] or (args.command == "list" and not looks_like_address(args.wallet) and not is_ton_domain(args.wallet))
    
    if needs_password and not password:
        if sys.stdin.isatty():
            password = getpass.getpass("Wallet password: ")
        else:
            # Для list без пароля пробуем как адрес
            if args.command != "list":
                print(json.dumps({"error": "Password required. Use --password or WALLET_PASSWORD env"}))
                sys.exit(1)
    
    try:
        if args.command == "list":
            result = list_nfts(
                wallet_identifier=args.wallet,
                password=password,
                limit=args.limit
            )
        
        elif args.command == "info":
            result = get_nft_info(args.address)
        
        elif args.command == "collection":
            result = get_collection_info(args.address)
        
        elif args.command == "search":
            result = search_collections(args.query, args.limit)
        
        elif args.command == "transfer":
            if not TONSDK_AVAILABLE:
                print(json.dumps({
                    "error": "Missing dependency: tonsdk",
                    "install": "pip install tonsdk"
                }, indent=2))
                sys.exit(1)
            
            if not password:
                print(json.dumps({"error": "Password required for transfer"}))
                sys.exit(1)
            
            result = transfer_nft(
                nft_address=args.nft,
                from_wallet=args.from_wallet,
                to_address=args.to,
                password=password,
                confirm=args.confirm
            )
        
        else:
            result = {"error": f"Unknown command: {args.command}"}
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if not result.get("success", False):
            sys.exit(1)
        
    except ValueError as e:
        print(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Unexpected error: {e}"}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
