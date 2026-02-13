#!/usr/bin/env python3
"""
OpenClaw TON Skill — Profile & Extras via swap.coffee API

Covers remaining swap.coffee v1 API endpoints:
- Profile: tx history, account settings
- Cashback: cashback info, rewards
- Claim: claim stats, claim tokens
- Referral: referral info, bind, aliases
- Statistics: generic DEX stats
- Contests: active contests, leaderboard

API Base: https://backend.swap.coffee/v1

Documentation: https://docs.swap.coffee/technical-guides/aggregator-api/introduction
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, List

# Локальный импорт
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from utils import api_request, load_config, is_valid_address


def _make_url_safe(address: str) -> str:
    """Конвертирует адрес в URL-safe формат (заменяет +/ на -_)."""
    return address.replace("+", "-").replace("/", "_")


# =============================================================================
# Constants
# =============================================================================

SWAP_COFFEE_API = "https://backend.swap.coffee"
SWAP_COFFEE_API_V1 = "https://backend.swap.coffee/v1"


# =============================================================================
# API Helper
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
    version: str = "v1",
) -> dict:
    """
    Запрос к swap.coffee API.

    Args:
        endpoint: Endpoint (например "/profile/history")
        method: HTTP метод
        params: Query параметры
        json_data: JSON body
        version: Версия API ("v1" или "v2")

    Returns:
        dict с результатом
    """
    if version == "v2":
        base_url = f"{SWAP_COFFEE_API}/v2"
    elif version == "v1":
        base_url = SWAP_COFFEE_API_V1
    else:
        base_url = SWAP_COFFEE_API

    api_key = get_swap_coffee_key()

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-Api-Key"] = api_key

    return api_request(
        url=f"{base_url}{endpoint}",
        method=method,
        headers=headers if headers else None,
        params=params,
        json_data=json_data,
    )


# =============================================================================
# Profile API
# =============================================================================


def get_profile_history(
    wallet_address: str,
    page: int = 1,
    size: int = 20,
    tx_type: Optional[str] = None,
) -> dict:
    """
    Получает историю транзакций профиля.
    
    GET /v1/profile/history
    
    Args:
        wallet_address: Адрес кошелька
        page: Номер страницы (1-indexed)
        size: Количество записей на странице (max 100)
        tx_type: Тип транзакций (swap, provide, withdraw и т.д.)
    
    Returns:
        dict с историей транзакций
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {
        "wallet_address": wallet_address,
        "page": page,
        "size": min(size, 100),
    }
    
    if tx_type:
        params["type"] = tx_type
    
    result = swap_coffee_request("/profile/history", params=params)
    
    if result["success"]:
        data = result["data"]
        return {
            "success": True,
            "wallet": wallet_address,
            "page": page,
            "size": size,
            "history": data.get("transactions", data) if isinstance(data, dict) else data,
            "total_count": data.get("total_count") if isinstance(data, dict) else None,
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get profile history"),
        "status_code": result.get("status_code"),
    }


def get_profile_settings(wallet_address: str) -> dict:
    """
    Получает настройки профиля пользователя.
    
    GET /v1/profile/settings
    
    Args:
        wallet_address: Адрес кошелька
    
    Returns:
        dict с настройками
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {"wallet_address": wallet_address}
    result = swap_coffee_request("/profile/settings", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "settings": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get profile settings"),
        "status_code": result.get("status_code"),
    }


def update_profile_settings(
    wallet_address: str,
    settings: dict,
) -> dict:
    """
    Обновляет настройки профиля.
    
    POST /v1/profile/settings
    
    Args:
        wallet_address: Адрес кошелька
        settings: Словарь с настройками для обновления
    
    Returns:
        dict с результатом
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    body = {
        "wallet_address": wallet_address,
        **settings,
    }
    
    result = swap_coffee_request("/profile/settings", method="POST", json_data=body)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "updated_settings": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to update profile settings"),
        "status_code": result.get("status_code"),
    }


def get_profile_summary(wallet_address: str) -> dict:
    """
    Получает сводку профиля (общая статистика).
    
    GET /v1/profile/summary
    
    Args:
        wallet_address: Адрес кошелька
    
    Returns:
        dict со сводкой
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {"wallet_address": wallet_address}
    result = swap_coffee_request("/profile/summary", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "summary": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get profile summary"),
        "status_code": result.get("status_code"),
    }


# =============================================================================
# Cashback API
# =============================================================================


def get_cashback_info(wallet_address: str) -> dict:
    """
    Получает информацию о кешбэке пользователя.
    
    GET /v1/cashback/info
    
    Args:
        wallet_address: Адрес кошелька
    
    Returns:
        dict с информацией о кешбэке
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {"wallet_address": wallet_address}
    result = swap_coffee_request("/cashback/info", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "cashback": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get cashback info"),
        "status_code": result.get("status_code"),
    }


def get_cashback_rewards(wallet_address: str) -> dict:
    """
    Получает список доступных наград кешбэка.
    
    GET /v1/cashback/rewards
    
    Args:
        wallet_address: Адрес кошелька
    
    Returns:
        dict со списком наград
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {"wallet_address": wallet_address}
    result = swap_coffee_request("/cashback/rewards", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "rewards": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get cashback rewards"),
        "status_code": result.get("status_code"),
    }


def get_cashback_history(
    wallet_address: str,
    page: int = 1,
    size: int = 20,
) -> dict:
    """
    Получает историю начисления кешбэка.
    
    GET /v1/cashback/history
    
    Args:
        wallet_address: Адрес кошелька
        page: Номер страницы
        size: Количество записей
    
    Returns:
        dict с историей кешбэка
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {
        "wallet_address": wallet_address,
        "page": page,
        "size": min(size, 100),
    }
    
    result = swap_coffee_request("/cashback/history", params=params)
    
    if result["success"]:
        data = result["data"]
        return {
            "success": True,
            "wallet": wallet_address,
            "page": page,
            "history": data.get("history", data) if isinstance(data, dict) else data,
            "total_count": data.get("total_count") if isinstance(data, dict) else None,
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get cashback history"),
        "status_code": result.get("status_code"),
    }


# =============================================================================
# Claim API
# =============================================================================


def get_claim_stats(wallet_address: str) -> dict:
    """
    Получает статистику клейма токенов.
    
    GET /v1/claim/stats
    
    Args:
        wallet_address: Адрес кошелька
    
    Returns:
        dict со статистикой клейма
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {"wallet_address": wallet_address}
    result = swap_coffee_request("/claim/stats", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "claim_stats": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get claim stats"),
        "status_code": result.get("status_code"),
    }


def get_claim_available(wallet_address: str) -> dict:
    """
    Получает доступные для клейма токены.
    
    GET /v1/claim/available
    
    Args:
        wallet_address: Адрес кошелька
    
    Returns:
        dict с доступными токенами для клейма
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {"wallet_address": wallet_address}
    result = swap_coffee_request("/claim/available", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "available": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get available claims"),
        "status_code": result.get("status_code"),
    }


def claim_tokens(
    wallet_address: str,
    claim_id: Optional[str] = None,
    claim_all: bool = False,
) -> dict:
    """
    Создаёт транзакцию для клейма токенов.
    
    POST /v1/claim
    
    Args:
        wallet_address: Адрес кошелька
        claim_id: ID конкретного клейма (если не claim_all)
        claim_all: Клеймить все доступные токены
    
    Returns:
        dict с транзакциями для подписания
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    body = {"wallet_address": wallet_address}
    
    if claim_all:
        body["claim_all"] = True
    elif claim_id:
        body["claim_id"] = claim_id
    else:
        return {"success": False, "error": "Either claim_id or claim_all must be specified"}
    
    result = swap_coffee_request("/claim", method="POST", json_data=body)
    
    if result["success"]:
        data = result["data"]
        transactions = data if isinstance(data, list) else [data]
        
        return {
            "success": True,
            "wallet": wallet_address,
            "operation": "claim",
            "claim_id": claim_id,
            "claim_all": claim_all,
            "transactions": transactions,
            "transactions_count": len(transactions),
            "note": "Send these transactions via TonConnect to claim tokens",
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to create claim transaction"),
        "status_code": result.get("status_code"),
    }


# =============================================================================
# Referral API
# =============================================================================


def get_referral_info(wallet_address: str) -> dict:
    """
    Получает информацию о реферальной программе.
    
    GET /v1/referral/info
    
    Args:
        wallet_address: Адрес кошелька
    
    Returns:
        dict с реферальной информацией
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {"wallet_address": wallet_address}
    result = swap_coffee_request("/referral/info", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "referral": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get referral info"),
        "status_code": result.get("status_code"),
    }


def get_referral_stats(wallet_address: str) -> dict:
    """
    Получает статистику рефералов.
    
    GET /v1/referral/stats
    
    Args:
        wallet_address: Адрес кошелька
    
    Returns:
        dict со статистикой рефералов
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {"wallet_address": wallet_address}
    result = swap_coffee_request("/referral/stats", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "stats": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get referral stats"),
        "status_code": result.get("status_code"),
    }


def get_referral_rewards(wallet_address: str) -> dict:
    """
    Получает реферальные награды.
    
    GET /v1/referral/rewards
    
    Args:
        wallet_address: Адрес кошелька
    
    Returns:
        dict с реферальными наградами
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {"wallet_address": wallet_address}
    result = swap_coffee_request("/referral/rewards", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "rewards": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get referral rewards"),
        "status_code": result.get("status_code"),
    }


def bind_referral(
    wallet_address: str,
    referral_code: str,
) -> dict:
    """
    Привязывает реферальный код к кошельку.
    
    POST /v1/referral/bind
    
    Args:
        wallet_address: Адрес кошелька
        referral_code: Реферальный код для привязки
    
    Returns:
        dict с результатом
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    body = {
        "wallet_address": wallet_address,
        "referral_code": referral_code,
    }
    
    result = swap_coffee_request("/referral/bind", method="POST", json_data=body)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "referral_code": referral_code,
            "result": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to bind referral"),
        "status_code": result.get("status_code"),
    }


def get_referral_aliases(wallet_address: str) -> dict:
    """
    Получает алиасы (псевдонимы) реферальной ссылки.
    
    GET /v1/referral/aliases
    
    Args:
        wallet_address: Адрес кошелька
    
    Returns:
        dict со списком алиасов
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {"wallet_address": wallet_address}
    result = swap_coffee_request("/referral/aliases", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "aliases": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get referral aliases"),
        "status_code": result.get("status_code"),
    }


def create_referral_alias(
    wallet_address: str,
    alias: str,
) -> dict:
    """
    Создаёт новый алиас для реферальной ссылки.
    
    POST /v1/referral/aliases
    
    Args:
        wallet_address: Адрес кошелька
        alias: Новый алиас
    
    Returns:
        dict с результатом
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    body = {
        "wallet_address": wallet_address,
        "alias": alias,
    }
    
    result = swap_coffee_request("/referral/aliases", method="POST", json_data=body)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "alias": alias,
            "result": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to create referral alias"),
        "status_code": result.get("status_code"),
    }


def delete_referral_alias(
    wallet_address: str,
    alias: str,
) -> dict:
    """
    Удаляет алиас реферальной ссылки.
    
    DELETE /v1/referral/aliases
    
    Args:
        wallet_address: Адрес кошелька
        alias: Алиас для удаления
    
    Returns:
        dict с результатом
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {
        "wallet_address": wallet_address,
        "alias": alias,
    }
    
    result = swap_coffee_request("/referral/aliases", method="DELETE", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "wallet": wallet_address,
            "deleted_alias": alias,
            "result": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to delete referral alias"),
        "status_code": result.get("status_code"),
    }


# =============================================================================
# Statistics API
# =============================================================================


def get_dex_statistics() -> dict:
    """
    Получает общую статистику DEX.
    
    GET /v1/statistics
    
    Returns:
        dict со статистикой
    """
    result = swap_coffee_request("/statistics")
    
    if result["success"]:
        return {
            "success": True,
            "statistics": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get DEX statistics"),
        "status_code": result.get("status_code"),
    }


def get_statistics_volume(period: str = "24h") -> dict:
    """
    Получает статистику объёмов.
    
    GET /v1/statistics/volume
    
    Args:
        period: Период (24h, 7d, 30d)
    
    Returns:
        dict со статистикой объёмов
    """
    params = {"period": period}
    result = swap_coffee_request("/statistics/volume", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "period": period,
            "volume": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get volume statistics"),
        "status_code": result.get("status_code"),
    }


def get_statistics_tokens(
    sort_by: str = "volume",
    limit: int = 20,
) -> dict:
    """
    Получает топ токенов по объёму/ликвидности.
    
    GET /v1/statistics/tokens
    
    Args:
        sort_by: Сортировка (volume, liquidity, txs)
        limit: Количество токенов
    
    Returns:
        dict со списком топ токенов
    """
    params = {
        "sort_by": sort_by,
        "limit": min(limit, 100),
    }
    
    result = swap_coffee_request("/statistics/tokens", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "sort_by": sort_by,
            "tokens": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get token statistics"),
        "status_code": result.get("status_code"),
    }


# =============================================================================
# Contests API
# =============================================================================


def get_active_contests() -> dict:
    """
    Получает список активных конкурсов.
    
    GET /v1/contests/active
    
    Returns:
        dict со списком активных конкурсов
    """
    result = swap_coffee_request("/contests/active")
    
    if result["success"]:
        contests = result["data"]
        return {
            "success": True,
            "contests_count": len(contests) if isinstance(contests, list) else 1,
            "contests": contests,
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get active contests"),
        "status_code": result.get("status_code"),
    }


def get_contest_info(contest_id: str) -> dict:
    """
    Получает информацию о конкретном конкурсе.
    
    GET /v1/contests/{contest_id}
    
    Args:
        contest_id: ID конкурса
    
    Returns:
        dict с информацией о конкурсе
    """
    result = swap_coffee_request(f"/contests/{contest_id}")
    
    if result["success"]:
        return {
            "success": True,
            "contest_id": contest_id,
            "contest": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get contest info"),
        "status_code": result.get("status_code"),
    }


def get_contest_leaderboard(
    contest_id: str,
    page: int = 1,
    size: int = 50,
) -> dict:
    """
    Получает лидерборд конкурса.
    
    GET /v1/contests/{contest_id}/leaderboard
    
    Args:
        contest_id: ID конкурса
        page: Номер страницы
        size: Записей на странице
    
    Returns:
        dict с лидербордом
    """
    params = {
        "page": page,
        "size": min(size, 100),
    }
    
    result = swap_coffee_request(f"/contests/{contest_id}/leaderboard", params=params)
    
    if result["success"]:
        data = result["data"]
        return {
            "success": True,
            "contest_id": contest_id,
            "page": page,
            "leaderboard": data.get("leaderboard", data) if isinstance(data, dict) else data,
            "total_count": data.get("total_count") if isinstance(data, dict) else None,
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get contest leaderboard"),
        "status_code": result.get("status_code"),
    }


def get_contest_user_position(
    contest_id: str,
    wallet_address: str,
) -> dict:
    """
    Получает позицию пользователя в конкурсе.
    
    GET /v1/contests/{contest_id}/user
    
    Args:
        contest_id: ID конкурса
        wallet_address: Адрес кошелька
    
    Returns:
        dict с позицией пользователя
    """
    if not is_valid_address(wallet_address):
        return {"success": False, "error": f"Invalid wallet address: {wallet_address}"}
    
    params = {"wallet_address": wallet_address}
    result = swap_coffee_request(f"/contests/{contest_id}/user", params=params)
    
    if result["success"]:
        return {
            "success": True,
            "contest_id": contest_id,
            "wallet": wallet_address,
            "position": result["data"],
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get user contest position"),
        "status_code": result.get("status_code"),
    }


def get_all_contests(
    include_finished: bool = False,
    page: int = 1,
    size: int = 20,
) -> dict:
    """
    Получает список всех конкурсов.
    
    GET /v1/contests
    
    Args:
        include_finished: Включать завершённые
        page: Номер страницы
        size: Записей на странице
    
    Returns:
        dict со списком конкурсов
    """
    params = {
        "include_finished": include_finished,
        "page": page,
        "size": min(size, 100),
    }
    
    result = swap_coffee_request("/contests", params=params)
    
    if result["success"]:
        data = result["data"]
        contests = data.get("contests", data) if isinstance(data, dict) else data
        return {
            "success": True,
            "page": page,
            "contests_count": len(contests) if isinstance(contests, list) else 1,
            "contests": contests,
            "total_count": data.get("total_count") if isinstance(data, dict) else None,
        }
    
    return {
        "success": False,
        "error": result.get("error", "Failed to get contests"),
        "status_code": result.get("status_code"),
    }


# =============================================================================
# CLI
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Profile & Extras via swap.coffee API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Profile
  %(prog)s profile-history --wallet EQAbc...
  %(prog)s profile-settings --wallet EQAbc...
  %(prog)s profile-summary --wallet EQAbc...
  
  # Cashback
  %(prog)s cashback-info --wallet EQAbc...
  %(prog)s cashback-rewards --wallet EQAbc...
  %(prog)s cashback-history --wallet EQAbc...
  
  # Claim
  %(prog)s claim-stats --wallet EQAbc...
  %(prog)s claim-available --wallet EQAbc...
  %(prog)s claim --wallet EQAbc... --claim-id 123
  %(prog)s claim --wallet EQAbc... --all
  
  # Referral
  %(prog)s referral-info --wallet EQAbc...
  %(prog)s referral-bind --wallet EQAbc... --code REF123
  %(prog)s referral-aliases --wallet EQAbc...
  %(prog)s referral-alias-create --wallet EQAbc... --alias myalias
  %(prog)s referral-alias-delete --wallet EQAbc... --alias myalias
  
  # Statistics
  %(prog)s stats
  %(prog)s stats-volume --period 7d
  %(prog)s stats-tokens --sort volume --limit 10
  
  # Contests
  %(prog)s contests-active
  %(prog)s contest --id contest123
  %(prog)s contest-leaderboard --id contest123 --size 20
  %(prog)s contest-position --id contest123 --wallet EQAbc...

API Categories:
  Profile:     History, settings, summary
  Cashback:    Rewards info, history
  Claim:       Stats, available tokens, claim
  Referral:    Info, bind code, aliases
  Statistics:  DEX stats, volumes, top tokens
  Contests:    Active contests, leaderboards
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # --- Profile ---
    ph_p = subparsers.add_parser("profile-history", help="Get profile transaction history")
    ph_p.add_argument("--wallet", "-w", required=True, help="Wallet address")
    ph_p.add_argument("--page", "-p", type=int, default=1, help="Page number")
    ph_p.add_argument("--size", "-s", type=int, default=20, help="Results per page")
    ph_p.add_argument("--type", "-t", help="Transaction type filter")

    ps_p = subparsers.add_parser("profile-settings", help="Get profile settings")
    ps_p.add_argument("--wallet", "-w", required=True, help="Wallet address")

    psu_p = subparsers.add_parser("profile-summary", help="Get profile summary")
    psu_p.add_argument("--wallet", "-w", required=True, help="Wallet address")

    # --- Cashback ---
    ci_p = subparsers.add_parser("cashback-info", help="Get cashback info")
    ci_p.add_argument("--wallet", "-w", required=True, help="Wallet address")

    cr_p = subparsers.add_parser("cashback-rewards", help="Get cashback rewards")
    cr_p.add_argument("--wallet", "-w", required=True, help="Wallet address")

    ch_p = subparsers.add_parser("cashback-history", help="Get cashback history")
    ch_p.add_argument("--wallet", "-w", required=True, help="Wallet address")
    ch_p.add_argument("--page", "-p", type=int, default=1, help="Page number")
    ch_p.add_argument("--size", "-s", type=int, default=20, help="Results per page")

    # --- Claim ---
    cls_p = subparsers.add_parser("claim-stats", help="Get claim statistics")
    cls_p.add_argument("--wallet", "-w", required=True, help="Wallet address")

    cla_p = subparsers.add_parser("claim-available", help="Get available claims")
    cla_p.add_argument("--wallet", "-w", required=True, help="Wallet address")

    cl_p = subparsers.add_parser("claim", help="Claim tokens")
    cl_p.add_argument("--wallet", "-w", required=True, help="Wallet address")
    cl_p.add_argument("--claim-id", help="Specific claim ID")
    cl_p.add_argument("--all", action="store_true", help="Claim all available")

    # --- Referral ---
    ri_p = subparsers.add_parser("referral-info", help="Get referral info")
    ri_p.add_argument("--wallet", "-w", required=True, help="Wallet address")

    rs_p = subparsers.add_parser("referral-stats", help="Get referral stats")
    rs_p.add_argument("--wallet", "-w", required=True, help="Wallet address")

    rr_p = subparsers.add_parser("referral-rewards", help="Get referral rewards")
    rr_p.add_argument("--wallet", "-w", required=True, help="Wallet address")

    rb_p = subparsers.add_parser("referral-bind", help="Bind referral code")
    rb_p.add_argument("--wallet", "-w", required=True, help="Wallet address")
    rb_p.add_argument("--code", "-c", required=True, help="Referral code")

    ral_p = subparsers.add_parser("referral-aliases", help="Get referral aliases")
    ral_p.add_argument("--wallet", "-w", required=True, help="Wallet address")

    rac_p = subparsers.add_parser("referral-alias-create", help="Create referral alias")
    rac_p.add_argument("--wallet", "-w", required=True, help="Wallet address")
    rac_p.add_argument("--alias", "-a", required=True, help="Alias to create")

    rad_p = subparsers.add_parser("referral-alias-delete", help="Delete referral alias")
    rad_p.add_argument("--wallet", "-w", required=True, help="Wallet address")
    rad_p.add_argument("--alias", "-a", required=True, help="Alias to delete")

    # --- Statistics ---
    st_p = subparsers.add_parser("stats", help="Get DEX statistics")

    stv_p = subparsers.add_parser("stats-volume", help="Get volume statistics")
    stv_p.add_argument("--period", "-p", default="24h", choices=["24h", "7d", "30d"])

    stt_p = subparsers.add_parser("stats-tokens", help="Get top tokens")
    stt_p.add_argument("--sort", "-s", default="volume", choices=["volume", "liquidity", "txs"])
    stt_p.add_argument("--limit", "-l", type=int, default=20, help="Number of tokens")

    # --- Contests ---
    ca_p = subparsers.add_parser("contests-active", help="Get active contests")

    cal_p = subparsers.add_parser("contests", help="Get all contests")
    cal_p.add_argument("--include-finished", action="store_true", help="Include finished")
    cal_p.add_argument("--page", "-p", type=int, default=1, help="Page number")
    cal_p.add_argument("--size", "-s", type=int, default=20, help="Results per page")

    co_p = subparsers.add_parser("contest", help="Get contest info")
    co_p.add_argument("--id", "-i", required=True, help="Contest ID")

    col_p = subparsers.add_parser("contest-leaderboard", help="Get contest leaderboard")
    col_p.add_argument("--id", "-i", required=True, help="Contest ID")
    col_p.add_argument("--page", "-p", type=int, default=1, help="Page number")
    col_p.add_argument("--size", "-s", type=int, default=50, help="Results per page")

    cop_p = subparsers.add_parser("contest-position", help="Get user contest position")
    cop_p.add_argument("--id", "-i", required=True, help="Contest ID")
    cop_p.add_argument("--wallet", "-w", required=True, help="Wallet address")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        # Profile
        if args.command == "profile-history":
            result = get_profile_history(
                wallet_address=args.wallet,
                page=args.page,
                size=args.size,
                tx_type=getattr(args, "type", None),
            )
        elif args.command == "profile-settings":
            result = get_profile_settings(wallet_address=args.wallet)
        elif args.command == "profile-summary":
            result = get_profile_summary(wallet_address=args.wallet)

        # Cashback
        elif args.command == "cashback-info":
            result = get_cashback_info(wallet_address=args.wallet)
        elif args.command == "cashback-rewards":
            result = get_cashback_rewards(wallet_address=args.wallet)
        elif args.command == "cashback-history":
            result = get_cashback_history(
                wallet_address=args.wallet,
                page=args.page,
                size=args.size,
            )

        # Claim
        elif args.command == "claim-stats":
            result = get_claim_stats(wallet_address=args.wallet)
        elif args.command == "claim-available":
            result = get_claim_available(wallet_address=args.wallet)
        elif args.command == "claim":
            result = claim_tokens(
                wallet_address=args.wallet,
                claim_id=getattr(args, "claim_id", None),
                claim_all=getattr(args, "all", False),
            )

        # Referral
        elif args.command == "referral-info":
            result = get_referral_info(wallet_address=args.wallet)
        elif args.command == "referral-stats":
            result = get_referral_stats(wallet_address=args.wallet)
        elif args.command == "referral-rewards":
            result = get_referral_rewards(wallet_address=args.wallet)
        elif args.command == "referral-bind":
            result = bind_referral(wallet_address=args.wallet, referral_code=args.code)
        elif args.command == "referral-aliases":
            result = get_referral_aliases(wallet_address=args.wallet)
        elif args.command == "referral-alias-create":
            result = create_referral_alias(wallet_address=args.wallet, alias=args.alias)
        elif args.command == "referral-alias-delete":
            result = delete_referral_alias(wallet_address=args.wallet, alias=args.alias)

        # Statistics
        elif args.command == "stats":
            result = get_dex_statistics()
        elif args.command == "stats-volume":
            result = get_statistics_volume(period=args.period)
        elif args.command == "stats-tokens":
            result = get_statistics_tokens(sort_by=args.sort, limit=args.limit)

        # Contests
        elif args.command == "contests-active":
            result = get_active_contests()
        elif args.command == "contests":
            result = get_all_contests(
                include_finished=getattr(args, "include_finished", False),
                page=args.page,
                size=args.size,
            )
        elif args.command == "contest":
            result = get_contest_info(contest_id=args.id)
        elif args.command == "contest-leaderboard":
            result = get_contest_leaderboard(
                contest_id=args.id,
                page=args.page,
                size=args.size,
            )
        elif args.command == "contest-position":
            result = get_contest_user_position(
                contest_id=args.id,
                wallet_address=args.wallet,
            )

        else:
            result = {"success": False, "error": f"Unknown command: {args.command}"}

        print(json.dumps(result, indent=2, ensure_ascii=False))

        if not result.get("success", True):
            sys.exit(1)

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
