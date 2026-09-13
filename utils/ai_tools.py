# utils/ai_tools.py - Ferramentas de Consulta para o Agente BMIA (Function Calling)

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class AIToolkit:
    """Conjunto de ferramentas do agente BMIA para consultar dados do servidor."""

    def __init__(self, db, guild_id: int):
        self.db = db
        self.guild_id = guild_id

    async def get_top_games(self, days: int = 30, limit: int = 5) -> List[Dict[str, Any]]:
        """Retorna os jogos e atividades mais jogados no servidor Discord.

        Args:
            days: Quantidade de dias para analisar o histórico (padrão: 30).
            limit: Quantidade máxima de jogos a retornar (padrão: 5).
        """
        try:
            days = max(1, min(int(days), 365))
            limit = max(1, min(int(limit), 10))
            activities = await self.db.get_top_activities(self.guild_id, limit=limit, days=days)
            if not activities:
                return [{"mensagem": f"Nenhuma atividade de jogo registrada nos últimos {days} dias."}]

            return [
                {
                    "jogo": a.get("activity_name", "Desconhecido"),
                    "horas_totais": round(a.get("total_seconds", 0) / 3600, 1),
                    "jogadores_unicos": a.get("unique_users", 0),
                    "sessoes": a.get("session_count", 0),
                }
                for a in activities
            ]
        except Exception as e:
            logger.error(f"Erro ao executar tool get_top_games: {e}")
            return [{"erro": "Falha ao consultar jogos mais jogados."}]

    async def get_game_leaderboard(self, game_name: str, days: int = 30, limit: int = 5) -> List[Dict[str, Any]]:
        """Retorna o ranking dos membros do servidor que mais jogaram um jogo específico (ex: Roblox, Valorant, Minecraft, League of Legends, GTA).

        Args:
            game_name: Nome do jogo pesquisado (ex: 'Roblox', 'Valorant').
            days: Quantidade de dias para analisar o histórico (padrão: 30).
            limit: Quantidade máxima de membros a retornar (padrão: 5).
        """
        try:
            if not game_name or not game_name.strip():
                return [{"erro": "Nome do jogo não informado."}]

            days = max(1, min(int(days), 365))
            limit = max(1, min(int(limit), 10))
            users = await self.db.get_game_top_users(self.guild_id, game_name=game_name.strip(), limit=limit, days=days)
            if not users:
                return [{"mensagem": f"Nenhum membro encontrado jogando '{game_name}' nos últimos {days} dias."}]

            return [
                {
                    "posicao": idx + 1,
                    "usuario": u.get("username", "Desconhecido"),
                    "jogo": u.get("activity_name", game_name),
                    "horas_jogadas": round(u.get("total_seconds", 0) / 3600, 1),
                    "sessoes": u.get("session_count", 0),
                }
                for idx, u in enumerate(users)
            ]
        except Exception as e:
            logger.error(f"Erro ao executar tool get_game_leaderboard: {e}")
            return [{"erro": f"Falha ao consultar ranking do jogo {game_name}."}]

    async def get_voice_leaderboard(self, days: int = 30, limit: int = 5) -> List[Dict[str, Any]]:
        """Retorna o ranking dos membros com maior tempo de atividade em canais de voz no servidor.

        Args:
            days: Quantidade de dias para analisar o histórico (padrão: 30).
            limit: Quantidade máxima de membros a retornar (padrão: 5).
        """
        try:
            days = max(1, min(int(days), 365))
            limit = max(1, min(int(limit), 10))
            users = await self.db.get_top_users_by_voice(self.guild_id, limit=limit, days=days)
            if not users:
                return [{"mensagem": f"Nenhuma atividade de voz registrada nos últimos {days} dias."}]

            return [
                {
                    "posicao": idx + 1,
                    "usuario": u.get("username", "Desconhecido"),
                    "horas_em_voz": round(u.get("total_seconds", 0) / 3600, 1),
                }
                for idx, u in enumerate(users)
            ]
        except Exception as e:
            logger.error(f"Erro ao executar tool get_voice_leaderboard: {e}")
            return [{"erro": "Falha ao consultar ranking de voz."}]

    async def get_messages_leaderboard(self, days: int = 30, limit: int = 5) -> List[Dict[str, Any]]:
        """Retorna o ranking dos membros que mais enviaram mensagens de texto no servidor.

        Args:
            days: Quantidade de dias para analisar o histórico (padrão: 30).
            limit: Quantidade máxima de membros a retornar (padrão: 5).
        """
        try:
            days = max(1, min(int(days), 365))
            limit = max(1, min(int(limit), 10))
            users = await self.db.get_top_users_by_messages(self.guild_id, limit=limit, days=days)
            if not users:
                return [{"mensagem": f"Nenhuma mensagem registrada nos últimos {days} dias."}]

            return [
                {
                    "posicao": idx + 1,
                    "usuario": u.get("username", "Desconhecido"),
                    "quantidade_mensagens": u.get("message_count", 0),
                }
                for idx, u in enumerate(users)
            ]
        except Exception as e:
            logger.error(f"Erro ao executar tool get_messages_leaderboard: {e}")
            return [{"erro": "Falha ao consultar ranking de mensagens."}]

    async def get_user_stats_summary(self, username: str, days: int = 30) -> Dict[str, Any]:
        """Busca o resumo de estatísticas (mensagens, voz, jogos) de um usuário específico do servidor.

        Args:
            username: Nome de usuário ou menção aproximada da pessoa.
            days: Quantidade de dias para analisar o histórico (padrão: 30).
        """
        try:
            user = await self.db.find_user_by_username(username)
            if not user:
                return {"mensagem": f"Usuário '{username}' não foi encontrado na base de dados do servidor."}

            user_id = user["user_id"]
            stats = await self.db.get_detailed_user_stats(user_id, self.guild_id, days=days)
            return {
                "usuario": user.get("username"),
                "periodo_dias": days,
                "total_mensagens": stats.get("total_messages", 0),
                "horas_em_voz": round(stats.get("voice_minutes", 0) / 60, 1),
                "horas_em_jogos": round(stats.get("game_minutes", 0) / 60, 1),
                "pontos": stats.get("total_points", 0),
            }
        except Exception as e:
            logger.error(f"Erro ao executar tool get_user_stats_summary para {username}: {e}")
            return {"erro": f"Falha ao consultar estatísticas do usuário {username}."}

    def get_tool_callables(self) -> List[Any]:
        """Retorna a lista de métodos que podem ser passados diretamente para o Gemini como tools."""
        return [
            self.get_top_games,
            self.get_game_leaderboard,
            self.get_voice_leaderboard,
            self.get_messages_leaderboard,
            self.get_user_stats_summary,
        ]
