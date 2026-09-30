# utils/ai_tools.py - Ferramentas de Consulta para o Agente BMIA (Function Calling)

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class AIToolkit:
    """Conjunto de ferramentas do agente BMIA para consultar dados e executar ações no servidor."""

    def __init__(self, db, guild_id: int, gif_client=None, tenor_client=None, current_message=None, client=None, telegram=None):
        self.db = db
        self.guild_id = guild_id
        self.gif_client = gif_client or tenor_client
        self.current_message = current_message
        self.client = client
        self.telegram = telegram
        self.last_gif_url: Optional[str] = None

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

    async def get_tournament_history(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Retorna o histórico dos torneios e campeonatos realizados no servidor, incluindo vencedores e jogos.

        Args:
            limit: Quantidade máxima de torneios a listar (padrão: 5).
        """
        try:
            limit = max(1, min(int(limit), 10))
            tourneys = await self.db.get_recent_tournaments(self.guild_id, limit=limit)
            if not tourneys:
                return [{"mensagem": "Nenhum torneio registrado neste servidor ainda."}]

            return [
                {
                    "torneio_id": t["id"],
                    "nome": t["name"],
                    "jogo": t["game_name"],
                    "status": t["status"],
                    "campeao": t.get("winner_name") or "Ainda não definido",
                    "participantes": t.get("participant_count", 0),
                    "premio": t.get("prize") or "Sem prêmio registrado"
                }
                for t in tourneys
            ]
        except Exception as e:
            logger.error(f"Erro ao executar tool get_tournament_history: {e}")
            return [{"erro": "Falha ao consultar histórico de torneios."}]

    async def get_tournament_hall_of_fame(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Retorna o Hall da Fama dos membros com maior número de títulos em torneios e campeonatos do servidor.

        Args:
            limit: Quantidade máxima de campeões a retornar (padrão: 5).
        """
        try:
            limit = max(1, min(int(limit), 10))
            champions = await self.db.get_tournament_hall_of_fame(self.guild_id, limit=limit)
            if not champions:
                return [{"mensagem": "Nenhum campeão registrado no Hall da Fama ainda."}]

            result = []
            current_rank = 0
            prev_titles = None
            for c in champions:
                titles = c.get("titles_count", 1)
                if titles != prev_titles:
                    current_rank += 1
                    prev_titles = titles

                tourneys = c.get("tournaments") or []
                if isinstance(tourneys, str):
                    try:
                        import json
                        tourneys = json.loads(tourneys)
                    except Exception:
                        tourneys = []

                tourney_list = [f"{t.get('name')} ({t.get('game_name')})" for t in tourneys if isinstance(t, dict)]

                result.append({
                    "posicao": current_rank,
                    "usuario": c.get("username", "Desconhecido"),
                    "titulos": titles,
                    "jogos": c.get("games") or [],
                    "torneios": tourney_list or c.get("games") or []
                })
            return result
        except Exception as e:
            logger.error(f"Erro ao executar tool get_tournament_hall_of_fame: {e}")
            return [{"erro": "Falha ao consultar Hall da Fama de torneios."}]

    async def buscar_gif(self, tema: str) -> Dict[str, Any]:
        """Busca um GIF animado no GIPHY para reagir a uma conversa, piada, vitória, derrota, comemoração, ironia ou momento engraçado.
        Como você é uma IA/robô, dê preferência a pesquisar termos que tragam robôs, andróides ou IAs expressando reações (ex: 'robot i robot reaction', 'robot laughing', 'sonny i robot', 'robot confused', 'robot shocked', 'terminator thumbs up', 'glitch robot', 'cyborg facepalm', etc.), ou outros memes relevantes.

        Args:
            tema: Termo de busca em português ou inglês para encontrar o GIF (ex: 'robot i robot', 'robot laughing', 'risada meme', 'terminator thumbs up', 'bmia dança').
        """
        try:
            tema_clean = (tema or "").strip().lower()
            if any(k in tema_clean for k in ["bmia", "danca do bmia", "dança do bmia", "dança bmia", "danca bmia"]):
                from config import BMIA_DANCE_GIF_URL
                self.last_gif_url = BMIA_DANCE_GIF_URL
                return {
                    "gif_url": BMIA_DANCE_GIF_URL,
                    "tema": tema,
                    "instrucao": (
                        "O GIF oficial da dança do BMIA foi selecionado e será anexado visualmente à sua resposta pelo sistema! "
                        "Comemore com simpatia, entusiasmo e bom humor. NÃO escreva links, URLs ou colchetes markdown []() na sua resposta de texto."
                    )
                }

            client = self.gif_client
            if client is None:
                from utils.giphy_client import GiphyClient
                client = GiphyClient()
            gif_url = await client.search_gif_url(tema)
            if not gif_url:
                return {"mensagem": f"Nenhum GIF encontrado para o tema '{tema}'."}
            self.last_gif_url = gif_url
            return {
                "gif_url": gif_url,
                "tema": tema,
                "instrucao": (
                    "O GIF foi selecionado e será anexado visualmente à sua resposta pelo sistema. "
                    "Responda ao usuário com simpatia e bom humor. NÃO escreva links, URLs ou colchetes markdown []() na sua resposta de texto."
                )
            }
        except Exception as e:
            logger.error(f"Erro ao executar tool buscar_gif: {e}")
            return {"erro": "Falha ao buscar GIF no GIPHY."}

    async def reportar_mensagem(
        self,
        usuario_alvo_id: Any,
        motivo: str,
        categoria: str = "comportamento_inadequado",
        conteudo_mensagem: Optional[str] = None,
        mensagem_id: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Reporta/denuncia uma mensagem ou usuário à moderação humana do servidor quando há ofensa, assédio, toxicidade extrema, discurso proibido ou quando um usuário solicita ajuda/reclama de uma mensagem que violou as regras.

        Args:
            usuario_alvo_id: O ID numérico do Discord do usuário que cometeu a infração (ex: 443557642670178334) ou seu nome de usuário.
            motivo: Descrição clara do motivo da denúncia e resumo do ocorrido para a moderação humana.
            categoria: Categoria da infração (ex: 'ofensa', 'toxicidade', 'assedio', 'spam', 'comportamento_inadequado').
            conteudo_mensagem: O texto exato da mensagem ofensiva analisada (se disponível no histórico ou contexto).
            mensagem_id: O ID numérico da mensagem ofensiva (se disponível no histórico ou contexto).
        """
        try:
            reporter_id = 0
            channel_id = None
            guild = None
            if self.current_message:
                reporter_id = getattr(self.current_message.author, "id", 0)
                channel_id = getattr(self.current_message.channel, "id", None)
                guild = getattr(self.current_message, "guild", None)
            if not reporter_id and self.client and self.client.user:
                reporter_id = self.client.user.id
            if not guild and self.client:
                guild = self.client.get_guild(self.guild_id)

            # Resolução resiliente do ID do usuário alvo
            target_id = 0
            try:
                if isinstance(usuario_alvo_id, int) and usuario_alvo_id > 1:
                    target_id = usuario_alvo_id
                elif isinstance(usuario_alvo_id, str) and usuario_alvo_id.strip().isdigit() and int(usuario_alvo_id.strip()) > 1:
                    target_id = int(usuario_alvo_id.strip())
            except Exception:
                pass

            # Resolução resiliente do ID da mensagem
            msg_id = None
            try:
                if isinstance(mensagem_id, int) and mensagem_id > 1:
                    msg_id = mensagem_id
                elif isinstance(mensagem_id, str) and mensagem_id.strip().isdigit() and int(mensagem_id.strip()) > 1:
                    msg_id = int(mensagem_id.strip())
            except Exception:
                pass

            # Se target_id ou msg_id não estiverem definidos, buscar no histórico recente do canal
            target_name = str(usuario_alvo_id or "").strip()
            if self.current_message and self.current_message.channel:
                try:
                    async for hist_msg in self.current_message.channel.history(limit=25):
                        if hist_msg.id == self.current_message.id:
                            continue
                        author = hist_msg.author
                        if author.bot:
                            continue

                        # Se target_id já é conhecido e bate com o autor
                        if target_id and author.id == target_id:
                            if not msg_id:
                                msg_id = hist_msg.id
                            if not conteudo_mensagem:
                                conteudo_mensagem = hist_msg.content
                            break

                        # Se target_name bate com o nome ou display_name do autor
                        author_names = [author.name.lower(), getattr(author, "display_name", "").lower(), str(author).lower()]
                        if target_name and any(target_name.lower() in an for an in author_names):
                            target_id = author.id
                            if not msg_id:
                                msg_id = hist_msg.id
                            if not conteudo_mensagem:
                                conteudo_mensagem = hist_msg.content
                            break

                        # Se conteudo_mensagem foi fornecido e bate com o conteúdo desta mensagem
                        if conteudo_mensagem and (hist_msg.content in conteudo_mensagem or conteudo_mensagem in hist_msg.content):
                            target_id = author.id
                            msg_id = hist_msg.id
                            break
                except Exception as hist_err:
                    logger.warning(f"Erro ao buscar histórico recente para identificar denúncia: {hist_err}")

            # Se ainda não encontrou target_id, tenta buscar no guild
            if not target_id and guild and target_name:
                import discord
                member = discord.utils.find(
                    lambda m: target_name.lower() in m.name.lower() or target_name.lower() in getattr(m, "display_name", "").lower(),
                    guild.members
                )
                if member:
                    target_id = member.id

            report_id = await self.db.create_user_report(
                guild_id=self.guild_id,
                target_user_id=target_id,
                reporter_user_id=reporter_id,
                category=(categoria or "comportamento_inadequado").strip().lower(),
                reason=motivo.strip() if motivo else "Denúncia encaminhada via BMIA",
                message_content=conteudo_mensagem,
                message_id=msg_id,
                channel_id=channel_id,
                attachment_urls=[]
            )

            # Notificar canal de moderação / anúncios se configurado
            try:
                import discord
                from datetime import datetime, timezone
                from commands.reputation_commands import ReportActionView

                guild_config = await self.db.get_guild_config(self.guild_id)
                ann_channel_id = guild_config.get("announcement_channel_id") if guild_config else None
                if ann_channel_id and guild:
                    mod_channel = guild.get_channel(ann_channel_id)
                    if mod_channel:
                        target_member = guild.get_member(target_id)
                        target_tag = f"<@{target_id}> (`{target_member.name}`)" if target_member else f"<@{target_id}> (`ID: {target_id}`)"
                        reporter_tag = f"<@{reporter_id}>" if reporter_id else "🤖 BMIA Auto"

                        embed = discord.Embed(
                            title=f"🚨 Denúncia Encaminhada por BMIA — #{report_id}",
                            description=f"**Acusado:** {target_tag}\n"
                                        f"**Origem/Denunciante:** {reporter_tag}\n"
                                        f"**Categoria:** `{categoria}`\n\n"
                                        f"**Motivo:**\n{motivo}",
                            color=0xEF4444,
                            timestamp=datetime.now(timezone.utc)
                        )
                        if conteudo_mensagem:
                            embed.add_field(name="💬 Mensagem Denunciada", value=conteudo_mensagem[:500], inline=False)

                        view = ReportActionView(self.db, report_id, target_id)
                        await mod_channel.send(embed=embed, view=view)
            except Exception as notify_err:
                logger.warning(f"Não foi possível enviar alerta de denúncia no canal de moderação: {notify_err}")

            # Notificar Telegram se configurado
            if self.telegram:
                try:
                    await self.telegram.log_report_created(
                        guild_id=self.guild_id,
                        report_id=report_id,
                        target_user_id=target_id,
                        reporter_user_id=reporter_id,
                        category=categoria,
                        reason=motivo
                    )
                except Exception as tg_err:
                    logger.warning(f"Não foi possível enviar notificação Telegram da denúncia #{report_id}: {tg_err}")

            return {
                "sucesso": True,
                "report_id": report_id,
                "mensagem": f"Denúncia #{report_id} criada e encaminhada com sucesso para a moderação humana."
            }
        except Exception as e:
            logger.error(f"Erro ao executar tool reportar_mensagem: {e}")
            return {"erro": f"Falha ao registrar denúncia: {e}"}

    def get_tool_callables(self) -> List[Any]:
        """Retorna a lista de métodos que podem ser passados diretamente para o Gemini como tools."""
        return [
            self.get_top_games,
            self.get_game_leaderboard,
            self.get_voice_leaderboard,
            self.get_messages_leaderboard,
            self.get_user_stats_summary,
            self.get_tournament_history,
            self.get_tournament_hall_of_fame,
            self.buscar_gif,
            self.reportar_mensagem,
        ]
