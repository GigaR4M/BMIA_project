# utils/reputation_manager.py - Motor de Cálculo de Trust Score e Reputação

import discord
from datetime import datetime, timezone
from typing import Dict, Any, Optional

class ReputationManager:
    """Motor de análise e cálculo de reputação / Trust Score de membros."""

    @staticmethod
    def calculate_trust_score(
        account_age_days: int,
        server_membership_days: int,
        infractions_summary: Dict[str, Dict[str, Any]],
        reports_count: int = 0,
        approved_reports_count: int = 0,
        moderated_messages_count: int = 0,
        is_currently_timed_out: bool = False
    ) -> Dict[str, Any]:
        """
        Calcula o Trust Score de 0 a 100 baseado em múltiplos fatores de risco e histórico.
        
        Retorna:
            Dict com:
                - score (int 0-100)
                - tier (str: 'EXCELLENT', 'GOOD', 'OBSERVATION', 'HIGH_RISK')
                - color_hex (int: hex para Discord Embed)
                - label (str: texto em português)
                - penalties (lista de penalidades aplicadas)
                - bonuses (lista de bônus aplicados)
        """
        score = 100
        penalties = []
        bonuses = []

        # 1. Bônus por idade da conta
        if account_age_days > 1095:  # > 3 anos
            bonuses.append(("Conta veterana (> 3 anos)", 5))
        elif account_age_days > 365:  # > 1 ano
            bonuses.append(("Conta estabelecida (> 1 ano)", 3))
        elif account_age_days < 7:    # < 7 dias (Risco Alto de bot / raid)
            penalties.append(("Conta recém-criada (< 7 dias)", 25))
            score -= 25
        elif account_age_days < 30:   # < 30 dias
            penalties.append(("Conta recente (< 30 dias)", 10))
            score -= 10

        # 2. Bônus por tempo de casa no servidor sem problemas
        if server_membership_days > 180:
            bonuses.append(("Membro há mais de 6 meses", 5))
        elif server_membership_days > 60:
            bonuses.append(("Membro há mais de 2 meses", 2))

        # 3. Penalidades por infrações
        warns = infractions_summary.get("warn", {}).get("count", 0)
        if warns > 0:
            penalty = min(20, warns * 5)
            penalties.append((f"{warns}x Advertência(s)", penalty))
            score -= penalty

        timeouts = infractions_summary.get("timeout", {}).get("count", 0)
        if timeouts > 0:
            penalty = min(30, timeouts * 10)
            penalties.append((f"{timeouts}x Castigo/Timeout", penalty))
            score -= penalty

        mutes = infractions_summary.get("mute", {}).get("count", 0) + infractions_summary.get("hardmute", {}).get("count", 0)
        if mutes > 0:
            penalty = min(30, mutes * 15)
            penalties.append((f"{mutes}x Mute/Hardmute", penalty))
            score -= penalty

        kicks = infractions_summary.get("kick", {}).get("count", 0) + infractions_summary.get("softban", {}).get("count", 0)
        if kicks > 0:
            penalty = min(40, kicks * 25)
            penalties.append((f"{kicks}x Expulsão/Kick", penalty))
            score -= penalty

        bans = infractions_summary.get("ban", {}).get("count", 0) + infractions_summary.get("tempban", {}).get("count", 0)
        if bans > 0:
            penalty = min(50, bans * 40)
            penalties.append((f"{bans}x Ban/Tempban anterior", penalty))
            score -= penalty

        # 4. Mensagens deletadas por Moderação IA
        if moderated_messages_count > 0:
            penalty = min(20, moderated_messages_count * 4)
            penalties.append((f"{moderated_messages_count}x Mensagens Ofensivas (IA)", penalty))
            score -= penalty

        # 5. Denúncias Aprovadas
        if approved_reports_count > 0:
            penalty = min(30, approved_reports_count * 15)
            penalties.append((f"{approved_reports_count}x Denúncia(s) confirmada(s)", penalty))
            score -= penalty

        # 6. Status atual de castigo
        if is_currently_timed_out:
            penalties.append(("Atualmente em Castigo", 15))
            score -= 15

        # Aplica bônus (sem ultrapassar 100)
        total_bonus = sum(b[1] for b in bonuses)
        score = min(100, score + total_bonus)
        score = max(0, score)

        # Classificação por Faixas
        if score >= 90:
            tier = "EXCELLENT"
            label = "🟢 Confiável / Excelente"
            color_hex = 0x22C55E  # Verde
        elif score >= 70:
            tier = "GOOD"
            label = "🟡 Regular / Bom"
            color_hex = 0xEAB308  # Amarelo
        elif score >= 50:
            tier = "OBSERVATION"
            label = "🟠 Sob Observação"
            color_hex = 0xF97316  # Laranja
        else:
            tier = "HIGH_RISK"
            label = "🔴 Alto Risco / Suspeito"
            color_hex = 0xEF4444  # Vermelho

        return {
            "score": score,
            "tier": tier,
            "label": label,
            "color_hex": color_hex,
            "penalties": penalties,
            "bonuses": bonuses
        }
