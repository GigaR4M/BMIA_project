# utils/level_manager.py - Sistema de Níveis e Cálculo de Progressão de XP

import math
from typing import Dict, Any, Tuple


def get_xp_needed_for_level_up(level: int) -> int:
    """
    Retorna a quantidade de XP necessária para avançar do nível `level` para `level + 1`.
    Fórmula: 5 * level^2 + 50 * level + 100
    """
    if level < 1:
        level = 1
    return 5 * (level ** 2) + 50 * level + 100


def get_total_xp_for_level(level: int) -> int:
    """
    Retorna a quantidade total acumulada de XP necessária para atingir um determinado `level`.
    Nível 1 = 0 XP acumulado.
    """
    if level <= 1:
        return 0
    total = 0
    for lvl in range(1, level):
        total += get_xp_needed_for_level_up(lvl)
    return total


def get_level_from_xp(total_xp: int) -> int:
    """
    Calcula o nível atual de um usuário com base no seu total acumulado de XP.
    """
    if total_xp <= 0:
        return 1

    level = 1
    accumulated = 0
    while True:
        needed = get_xp_needed_for_level_up(level)
        if accumulated + needed > total_xp:
            break
        accumulated += needed
        level += 1

    return level


def get_level_progress(total_xp: int) -> Dict[str, Any]:
    """
    Retorna detalhes completos do progresso de nível do usuário.
    """
    if total_xp < 0:
        total_xp = 0

    level = get_level_from_xp(total_xp)
    base_xp = get_total_xp_for_level(level)
    next_level_total_xp = get_total_xp_for_level(level + 1)

    xp_in_level = total_xp - base_xp
    xp_needed_in_level = next_level_total_xp - base_xp

    progress_pct = (xp_in_level / xp_needed_in_level * 100) if xp_needed_in_level > 0 else 0.0
    progress_pct = min(100.0, max(0.0, progress_pct))

    return {
        "level": level,
        "total_xp": total_xp,
        "base_xp": base_xp,
        "next_level_total_xp": next_level_total_xp,
        "xp_in_level": xp_in_level,
        "xp_needed_in_level": xp_needed_in_level,
        "progress_pct": round(progress_pct, 1)
    }
