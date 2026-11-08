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

    async def _resolve_member_and_user(self, identifier: Any) -> tuple[Optional[Any], Optional[Dict[str, Any]]]:
        """
        Resolve de forma resiliente um membro do Discord e seu registro na tabela `users`
        a partir de ID numérico, menção <@id>, display_name (incluindo sufixos de streak como '| 🔥 1') ou username.
        Retorna (discord_member, db_user_dict).
        """
        import re

        raw = str(identifier or "").strip()
        if not raw:
            return None, None

        guild = None
        if self.current_message and getattr(self.current_message, "guild", None):
            guild = self.current_message.guild
        elif self.client:
            guild = self.client.get_guild(self.guild_id)

        # Limpa prefixo @, menção <@!123> e sufixos de streak como '| 🔥 1'
        id_match = re.search(r"<@!?(\d+)>", raw)
        extracted_id: Optional[int] = None
        if id_match:
            extracted_id = int(id_match.group(1))
        elif raw.isdigit() and int(raw) > 1000:
            extracted_id = int(raw)

        cleaned = re.sub(r"<@!?\d+>", "", raw).lstrip("@").strip()
        # Remove sufixo de streak (ex: ' | 🔥 12' ou '| 🔥 1')
        cleaned_no_streak = re.sub(r"\s*\|\s*🔥\s*\d+.*$", "", cleaned).strip()

        member = None
        # 1. Busca por ID extraído
        if extracted_id and guild:
            member = guild.get_member(extracted_id)

        # 2. Busca nas menções da mensagem atual
        if not member and self.current_message and getattr(self.current_message, "mentions", None):
            for m in self.current_message.mentions:
                if getattr(m, "bot", False):
                    continue
                if extracted_id and m.id == extracted_id:
                    member = m
                    break
                m_names = [
                    getattr(m, "name", "").lower(),
                    getattr(m, "display_name", "").lower(),
                    getattr(m, "global_name", "" or "").lower(),
                    re.sub(r"\s*\|\s*🔥\s*\d+.*$", "", getattr(m, "display_name", "")).strip().lower(),
                ]
                for q in (cleaned.lower(), cleaned_no_streak.lower()):
                    if q and any(q == n or q in n or (n and n in q) for n in m_names if n):
                        member = m
                        break
                if member:
                    break

        # 3. Busca nos membros da guilda (exato primeiro, depois parcial)
        if not member and guild and getattr(guild, "members", None):
            queries = [q.lower() for q in (cleaned_no_streak, cleaned) if q]
            for q in queries:
                for m in guild.members:
                    if getattr(m, "bot", False):
                        continue
                    disp = getattr(m, "display_name", "") or ""
                    disp_clean = re.sub(r"\s*\|\s*🔥\s*\d+.*$", "", disp).strip().lower()
                    uname = (getattr(m, "name", "") or "").lower()
                    gname = (getattr(m, "global_name", "") or "").lower()
                    if q in (uname, disp.lower(), disp_clean, gname):
                        member = m
                        break
                if member:
                    break

            if not member:
                for q in queries:
                    for m in guild.members:
                        if getattr(m, "bot", False):
                            continue
                        disp = getattr(m, "display_name", "") or ""
                        disp_clean = re.sub(r"\s*\|\s*🔥\s*\d+.*$", "", disp).strip().lower()
                        uname = (getattr(m, "name", "") or "").lower()
                        gname = (getattr(m, "global_name", "") or "").lower()
                        if any(q in n for n in (uname, disp.lower(), disp_clean, gname) if n):
                            member = m
                            break
                    if member:
                        break

        # 4. Se encontrou member na guilda, monta/busca db_user
        if member:
            db_user = None
            if hasattr(self.db, "find_user_by_username") and getattr(member, "name", None):
                try:
                    db_user = await self.db.find_user_by_username(member.name)
                except Exception:
                    db_user = None
            if not db_user:
                db_user = {
                    "user_id": member.id,
                    "username": getattr(member, "name", None) or getattr(member, "display_name", str(member.id)),
                    "is_bot": getattr(member, "bot", False),
                }
            return member, db_user

        # 5. Fallback no banco de dados tentando cleaned_no_streak e cleaned
        for candidate_q in dict.fromkeys([cleaned_no_streak, cleaned, raw]):
            if not candidate_q:
                continue
            try:
                user = await self.db.find_user_by_username(candidate_q)
                if user:
                    if guild and user.get("user_id"):
                        member = guild.get_member(user["user_id"])
                    return member, user
            except Exception:
                pass

        if extracted_id:
            return None, {"user_id": extracted_id, "username": str(extracted_id), "is_bot": False}

        return None, None

    async def get_user_stats_summary(self, username: str, days: int = 30) -> Dict[str, Any]:
        """Busca o resumo de estatísticas (mensagens, voz, jogos) de um usuário específico do servidor.

        Args:
            username: Nome de usuário, apelido no servidor, menção ou ID da pessoa.
            days: Quantidade de dias para analisar o histórico (padrão: 30).
        """
        try:
            member, user = await self._resolve_member_and_user(username)
            if not user:
                return {"mensagem": f"Usuário '{username}' não foi encontrado na base de dados do servidor."}

            user_id = user["user_id"]
            stats = await self.db.get_detailed_user_stats(user_id, self.guild_id, days=days)
            display_label = getattr(member, "display_name", None) or user.get("username")
            return {
                "usuario": display_label,
                "username": user.get("username"),
                "user_id": user_id,
                "periodo_dias": days,
                "total_mensagens": stats.get("total_messages", 0),
                "horas_em_voz": round(stats.get("voice_minutes", 0) / 60, 1),
                "horas_em_jogos": round(stats.get("game_minutes", 0) / 60, 1),
                "pontos": stats.get("total_points", 0),
            }
        except Exception as e:
            logger.error(f"Erro ao executar tool get_user_stats_summary para {username}: {e}")
            return {"erro": f"Falha ao consultar estatísticas do usuário {username}."}

    async def get_user_reputation(self, usuario: str) -> Dict[str, Any]:
        """Consulta a Reputação, Trust Score (nota de confiança de 0 a 100), nível de risco, tempo de casa e histórico de infrações/moderação de um membro do servidor.

        Args:
            usuario: Nome de usuário, apelido no servidor (display_name), menção ou ID numérico do membro.
        """
        try:
            from datetime import datetime, timezone
            from utils.reputation_manager import ReputationManager

            member, user = await self._resolve_member_and_user(usuario)
            if not user and not member:
                return {"mensagem": f"Membro '{usuario}' não foi encontrado no servidor."}

            user_id = member.id if member else user["user_id"]
            username_str = getattr(member, "name", None) or (user.get("username") if user else str(user_id))
            display_name = getattr(member, "display_name", None) or username_str

            now = datetime.now(timezone.utc)
            account_age_days = 365
            server_membership_days = 90
            is_timed_out = False

            if member:
                created_at = getattr(member, "created_at", None)
                if isinstance(created_at, datetime):
                    account_age_days = max(0, (now - created_at).days)
                joined_at = getattr(member, "joined_at", None)
                if isinstance(joined_at, datetime):
                    server_membership_days = max(0, (now - joined_at).days)
                if hasattr(member, "is_timed_out") and callable(member.is_timed_out):
                    try:
                        is_timed_out = bool(member.is_timed_out())
                    except Exception:
                        is_timed_out = False

            dossier_data = await self.db.get_user_full_dossier(self.guild_id, user_id)
            infractions_summary = dossier_data.get("infractions_summary", {})
            reports = dossier_data.get("reports", [])
            approved_reports = [r for r in reports if r.get("status") == "approved"]
            moderated_messages = dossier_data.get("moderated_messages_count", 0)

            trust_info = ReputationManager.calculate_trust_score(
                account_age_days=account_age_days,
                server_membership_days=server_membership_days,
                infractions_summary=infractions_summary,
                reports_count=len(reports),
                approved_reports_count=len(approved_reports),
                moderated_messages_count=moderated_messages,
                is_currently_timed_out=is_timed_out,
            )

            warn_count = infractions_summary.get("warn", {}).get("count", 0)
            timeout_count = infractions_summary.get("timeout", {}).get("count", 0)
            mute_count = (
                infractions_summary.get("mute", {}).get("count", 0)
                + infractions_summary.get("hardmute", {}).get("count", 0)
            )
            kick_count = (
                infractions_summary.get("kick", {}).get("count", 0)
                + infractions_summary.get("softban", {}).get("count", 0)
            )
            ban_count = (
                infractions_summary.get("ban", {}).get("count", 0)
                + infractions_summary.get("tempban", {}).get("count", 0)
            )

            return {
                "usuario": display_name,
                "username": username_str,
                "user_id": user_id,
                "trust_score": trust_info["score"],
                "escala": "0 a 100",
                "classificacao": trust_info["label"],
                "tier": trust_info["tier"],
                "em_castigo_atualmente": is_timed_out,
                "idade_conta_dias": account_age_days,
                "tempo_no_servidor_dias": server_membership_days,
                "historico_infracoes": {
                    "advertencias": warn_count,
                    "castigos_timeouts": timeout_count,
                    "mutes": mute_count,
                    "expulsoes_kicks": kick_count,
                    "banimentos": ban_count,
                    "mensagens_moderadas_pela_ia": moderated_messages,
                    "denuncias_recebidas": len(reports),
                    "denuncias_aprovadas": len(approved_reports),
                },
                "bonus_aplicados": [f"{b[0]} (+{b[1]} pts)" for b in trust_info.get("bonuses", [])],
                "penalidades_aplicadas": [f"{p[0]} (-{p[1]} pts)" for p in trust_info.get("penalties", [])],
            }
        except Exception as e:
            logger.error(f"Erro ao executar tool get_user_reputation para {usuario}: {e}")
            return {"erro": f"Falha ao consultar a reputação do usuário {usuario}."}

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
                    guild_label = guild.name if guild else f"Servidor {self.guild_id}"
                    reporter_label = f"<@{reporter_id}>" if reporter_id else "🤖 BMIA Auto"
                    target_label = f"<@{target_id}>" if target_id else f"ID {usuario_alvo_id}"
                    await self.telegram.log_report_created(
                        report_id=report_id,
                        guild_name=guild_label,
                        reporter_name=reporter_label,
                        target_name=target_label,
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

    async def get_voice_peak_records(self) -> Dict[str, Any]:
        """Retorna os recordes históricos de quantidade máxima de usuários simultâneos conectados em canais de voz no servidor (recorde no mesmo canal único e recorde total somando todos os canais)."""
        try:
            records = await self.db.get_voice_peak_records(self.guild_id)
            return records
        except Exception as e:
            logger.error(f"Erro ao executar tool get_voice_peak_records: {e}")
            return {"erro": "Falha ao consultar recordes de usuários em voz."}

    async def get_xp_podium(self, mes: Optional[int] = None, ano: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Retorna o Pódio / Ranking de XP (pontos de atividade) dos membros mais ativos do servidor em um mês/ano específico ou no ano.

        Args:
            mes: Número do mês (1 a 12, ex: 10 para Outubro, 9 para Setembro). Opcional.
            ano: Ano da consulta (ex: 2026). Opcional (padrão: ano atual).
            limit: Quantidade máxima de membros no ranking (padrão: 10).
        """
        try:
            from datetime import datetime
            from config import BRT, now_brt

            now = now_brt()
            y = int(ano) if ano else now.year
            limit = max(1, min(int(limit), 15))

            if mes is not None:
                m = max(1, min(int(mes), 12))
                start_dt = datetime(y, m, 1, 0, 0, 0, tzinfo=BRT)
                if m == 12:
                    end_dt = datetime(y + 1, 1, 1, 0, 0, 0, tzinfo=BRT)
                else:
                    end_dt = datetime(y, m + 1, 1, 0, 0, 0, tzinfo=BRT)
            else:
                start_dt = datetime(y, 1, 1, 0, 0, 0, tzinfo=BRT)
                end_dt = datetime(y + 1, 1, 1, 0, 0, 0, tzinfo=BRT)

            rows = await self.db.get_top_users_date_range(self.guild_id, start_dt, end_dt, limit=limit)
            if not rows:
                return [{"mensagem": "Nenhum registro de pontuação encontrado para o período informado."}]

            guild = None
            if self.current_message and getattr(self.current_message, "guild", None):
                guild = self.current_message.guild
            elif self.client:
                guild = self.client.get_guild(self.guild_id)

            result = []
            for idx, r in enumerate(rows):
                uid = r.get("user_id")
                uname = r.get("username", "Desconhecido")
                display = uname
                if guild and uid:
                    member = guild.get_member(uid)
                    if member and member.display_name and member.display_name != uname:
                        display = f"{member.display_name} ({uname})"
                result.append({
                    "posicao": idx + 1,
                    "usuario": display,
                    "user_id": uid,
                    "xp": int(r.get("total_points", 0)),
                })
            return result
        except Exception as e:
            logger.error(f"Erro ao executar tool get_xp_podium: {e}")
            return [{"erro": "Falha ao consultar o pódio de XP."}]

    def get_tool_callables(self) -> List[Any]:
        """Retorna a lista de métodos que podem ser passados diretamente para o Gemini como tools."""
        return [
            self.get_top_games,
            self.get_game_leaderboard,
            self.get_voice_leaderboard,
            self.get_messages_leaderboard,
            self.get_user_stats_summary,
            self.get_user_reputation,
            self.get_tournament_history,
            self.get_tournament_hall_of_fame,
            self.buscar_gif,
            self.reportar_mensagem,
            self.get_voice_peak_records,
            self.get_xp_podium,
        ]
