# events/discord_events.py — Handlers de Eventos do Discord
"""
Todos os event handlers extraídos do main.py.
Recebem as dependências via parâmetro (sem variáveis globais).
O módulo expõe `register_events(client, ctx)` que registra todos os handlers.
"""

import re
import logging
from datetime import datetime, timezone

import discord

from config import DEFAULT_ALLOWED_CHANNELS
from utils.ai_tools import AIToolkit

logger = logging.getLogger(__name__)


def resolve_mentions_in_text(text: str, guild: discord.Guild | None) -> str:
    """Substitui <@id> pelo display_name do membro na guild."""
    if not text or not guild:
        return text

    def replace(match: re.Match) -> str:
        uid = int(match.group(1))
        member = guild.get_member(uid)
        return f"@{member.display_name}" if member else f"@{uid}"

    return re.sub(r"<@!?(\d+)>", replace, text)


def register_events(client: discord.Client, ctx: "BotContext") -> None:  # type: ignore[name-defined]
    """
    Registra todos os event handlers no client.

    `ctx` é um objeto simples (namespace) que agrupa os managers,
    permitindo que os handlers acessem recursos sem globals.
    """

    # ── Eventos de Agendamento ─────────────────────────────────────────────────
    @client.event
    async def on_scheduled_event_create(event: discord.ScheduledEvent) -> None:
        if ctx.event_monitor:
            await ctx.event_monitor.on_scheduled_event_create(event)

    @client.event
    async def on_scheduled_event_update(
        before: discord.ScheduledEvent, after: discord.ScheduledEvent
    ) -> None:
        if ctx.event_monitor:
            await ctx.event_monitor.on_scheduled_event_update(before, after)

    @client.event
    async def on_scheduled_event_delete(event: discord.ScheduledEvent) -> None:
        if ctx.event_monitor:
            await ctx.event_monitor.on_scheduled_event_delete(event)

    @client.event
    async def on_scheduled_event_user_add(
        event: discord.ScheduledEvent, user: discord.User
    ) -> None:
        if ctx.event_monitor:
            await ctx.event_monitor.on_scheduled_event_user_add(event, user)

    @client.event
    async def on_scheduled_event_user_remove(
        event: discord.ScheduledEvent, user: discord.User
    ) -> None:
        if ctx.event_monitor:
            await ctx.event_monitor.on_scheduled_event_user_remove(event, user)

    # ── Entradas e Saídas de Membros ───────────────────────────────────────────
    @client.event
    async def on_member_join(member: discord.Member) -> None:
        await ctx.telegram.log_member_join(member)
        
        # Rastreia origem do convite
        if hasattr(ctx, 'invite_tracker') and ctx.invite_tracker and ctx.db:
            try:
                invite_code, inviter_id = await ctx.invite_tracker.find_used_invite(member)
                await ctx.db.record_member_join_source(
                    guild_id=member.guild.id,
                    user_id=member.id,
                    inviter_id=inviter_id,
                    invite_code=invite_code
                )
                logger.info(f"📥 Membro {member.name} entrou usando convite '{invite_code}' criado por {inviter_id}")
            except Exception as e:
                logger.warning(f"Erro ao rastrear convite de {member.name}: {e}")

    @client.event
    async def on_member_remove(member: discord.Member) -> None:
        await ctx.telegram.log_member_leave(member)

    @client.event
    async def on_member_update(before: discord.Member, after: discord.Member) -> None:
        # Detecta quando um membro entra de castigo (timeout)
        if not before.is_timed_out() and after.is_timed_out():
            if ctx.db and after.timed_out_until:
                try:
                    duration_sec = int((after.timed_out_until - datetime.now(timezone.utc)).total_seconds())
                    await ctx.db.add_user_infraction(
                        guild_id=after.guild.id,
                        user_id=after.id,
                        moderator_id=client.user.id if client.user else 0,
                        action_type="timeout",
                        reason="Castigo / Timeout aplicado no Discord",
                        duration_seconds=max(0, duration_sec)
                    )
                    logger.info(f"⛔ Castigo registrado para {after.name} ({duration_sec}s)")
                except Exception as e:
                    logger.error(f"Erro ao registrar timeout para {after.name}: {e}")

    @client.event
    async def on_invite_create(invite: discord.Invite) -> None:
        if hasattr(ctx, 'invite_tracker') and ctx.invite_tracker and invite.guild:
            await ctx.invite_tracker.update_guild_invites(invite.guild)

    @client.event
    async def on_invite_delete(invite: discord.Invite) -> None:
        if hasattr(ctx, 'invite_tracker') and ctx.invite_tracker and invite.guild:
            await ctx.invite_tracker.update_guild_invites(invite.guild)

    # ── Mensagens ──────────────────────────────────────────────────────────────
    @client.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return

        if ctx.spam_detector and ctx.spam_detector.is_spam(message.author.id):
            return

        # Resposta por menção ao bot
        if client.user and client.user.mentioned_in(message) and not message.mention_everyone:
            if ctx.chat_handler:
                async with message.channel.typing():
                    try:
                        resolved_content = resolve_mentions_in_text(
                            message.content, message.guild
                        )

                        history_msgs = [
                            msg async for msg in message.channel.history(
                                limit=10, before=message
                            )
                        ]
                        history_msgs.reverse()

                        for h_msg in history_msgs:
                            h_msg.content = resolve_mentions_in_text(
                                h_msg.content, message.guild
                            )

                        formatted_history = ctx.chat_handler.format_history(
                            history_msgs, client.user
                        )

                        system_instruction = "Você é o BMIA, um bot assistente."
                        toolkit = None
                        if message.guild and ctx.db:
                            toolkit = AIToolkit(
                                ctx.db,
                                message.guild.id,
                                tenor_client=ctx.tenor_client,
                            )

                        if ctx.memory_manager and message.guild:
                            context_block = await ctx.memory_manager.get_relevant_context(
                                message.guild,
                                message.author,
                                resolved_content,
                                mentions=message.mentions,
                            )
                            system_instruction = f"""
                            Você é o Bot Oficial do servidor {message.guild.name}.
                            Sua identidade é BMIA (Bot de Monitoramento e Inteligência Artificial).

                            {context_block}

                            DIRETRIZES DO AGENTE BMIA:
                            1. Personalidade: Responda como um membro participante e bem-humorado do servidor, descontraído e sagaz, nunca como um robô corporativo ou distante.
                            2. Uso de Ferramentas (Tools): Sempre que o usuário perguntar sobre estatísticas do servidor, rankings de jogos específicos (ex: Roblox, Valorant), tempo de voz, quantidade de mensagens ou dados de membros, USE as ferramentas disponíveis para obter os dados reais do banco de dados.
                            3. Fatos e Proibição de Alucinações: NUNCA invente números, horas jogadas ou posições de ranking que não estejam no contexto ou no resultado das ferramentas.
                            4. Proibição de Templates/Placeholders: NUNCA use marcações entre colchetes como '[Nome do usuário]' ou '[inserir número]'. Se não houver dados, diga a verdade de forma bem-humorada.
                            5. Conciso e Coloquial: Mantenha as respostas concisas e use o contexto/memórias do servidor para personalizar a interação.
                            """

                        # Contexto de reply se a mensagem for uma resposta a outra
                        reply_context = ""
                        if message.reference and message.reference.message_id:
                            try:
                                ref_msg = message.reference.resolved
                                if not ref_msg or not isinstance(ref_msg, discord.Message):
                                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                                if ref_msg and ref_msg.content:
                                    ref_author = getattr(ref_msg.author, "display_name", str(ref_msg.author))
                                    ref_text = resolve_mentions_in_text(ref_msg.content, message.guild)
                                    reply_context = f"[Respondendo à mensagem de {ref_author}: '{ref_text}']\n"
                            except Exception as ref_err:
                                logger.debug("Não foi possível obter mensagem de referência: %s", ref_err)

                        user_prompt = f"{reply_context}{message.author.display_name}: {resolved_content}"

                        response_text = await ctx.chat_handler.generate_response(
                            user_prompt,
                            history=formatted_history,
                            system_instruction=system_instruction,
                            toolkit=toolkit,
                        )

                        if ctx.memory_manager and message.guild:
                            client.loop.create_task(
                                ctx.memory_manager.process_message_for_memory(
                                    message.guild.id,
                                    message.author.id,
                                    resolved_content,
                                    response_text,
                                )
                            )

                        if len(response_text) > 2000:
                            chunks = [
                                response_text[i:i + 2000]
                                for i in range(0, len(response_text), 2000)
                            ]
                            for chunk in chunks:
                                await message.reply(chunk)
                        else:
                            await message.reply(response_text)

                    except Exception as exc:
                        logger.error("Erro no ChatHandler: %s", exc)
                        await message.reply("Desculpe, tive um problema ao tentar responder.")

        # Pontos por mensagem (canais permitidos)
        allowed = ctx.allowed_channels
        if ctx.points_manager and message.channel.id in allowed:
            points = 1
            interaction_type = "message"

            if len(message.content) <= 10:
                interaction_type = "message_short"
                if message.guild and ctx.db:
                    daily_points = await ctx.db.get_daily_points(
                        message.author.id, "message_short", message.guild.id
                    )
                    if daily_points >= 30:
                        points = 0
                        logger.debug(
                            "🚫 %s atingiu o limite diário de pontos por mensagens curtas.",
                            message.author.name,
                        )
            else:
                points = 2
                interaction_type = "message_long"

            if points > 0 and message.reference:
                try:
                    ref = message.reference.cached_message
                    if ref:
                        if ref.author.id != message.author.id and not ref.author.bot:
                            points += 1
                    else:
                        points += 1
                except Exception:
                    pass

            if points > 0 and message.guild:
                avatar_url = str(message.author.display_avatar.url) if hasattr(message.author, 'display_avatar') else None
                await ctx.points_manager.add_points(
                    message.author.id,
                    points,
                    interaction_type,
                    message.guild.id,
                    message.author.name,
                    message.author.discriminator,
                    avatar_url=avatar_url,
                    channel=message.channel,
                )

            # Verificação de Chat Revival (Reativação de canal inativo por >= 7 dias)
            if len(message.content.strip()) >= 10 and message.guild and ctx.db:
                try:
                    last_msg = await ctx.db.get_last_channel_message(message.channel.id, exclude_message_id=message.id)
                    if last_msg and last_msg.get("created_at"):
                        last_created = last_msg["created_at"]
                        now_dt = datetime.now(timezone.utc) if last_created.tzinfo else datetime.now()
                        delta = now_dt - last_created
                        if delta.total_seconds() >= 7 * 86400:  # 7 dias de inatividade
                            # Anti-abuso: autor não pode ser o mesmo da mensagem anterior
                            if last_msg.get("user_id") != message.author.id:
                                avatar_url = str(message.author.display_avatar.url) if hasattr(message.author, 'display_avatar') else None
                                await ctx.points_manager.add_points(
                                    message.author.id,
                                    15,
                                    "chat_revival",
                                    message.guild.id,
                                    message.author.name,
                                    message.author.discriminator,
                                    avatar_url=avatar_url,
                                    channel=message.channel,
                                )
                                logger.info(
                                    "🔥 Chat Revival: %s reanimou o canal %s após %.1f dias (+15 XP)",
                                    message.author.name,
                                    message.channel.name,
                                    delta.total_seconds() / 86400
                                )
                                try:
                                    await message.add_reaction("🔥")
                                except Exception:
                                    pass
                except Exception as e:
                    logger.warning("Erro ao verificar Chat Revival no canal %s: %s", message.channel.id, e)


        # Buffer de moderação
        ctx.buffer_mensagens.append(message)
        logger.debug(
            "Buffer de moderação: %d mensagens", len(ctx.buffer_mensagens)
        )

        # Coleta estatísticas
        if ctx.stats_collector:
            await ctx.stats_collector.on_message(message)

        # Gerenciamento de Mídias e Retrospectiva
        if ctx.media_manager:
            await ctx.media_manager.on_message(message)

    # ── Reações ────────────────────────────────────────────────────────────────
    @client.event
    async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
        if payload.member and payload.member.bot:
            return

        allowed = ctx.allowed_channels
        if ctx.points_manager and payload.channel_id in allowed:
            user_reactor = payload.member or client.get_user(payload.user_id)
            if user_reactor and payload.guild_id:
                avatar_url = str(user_reactor.display_avatar.url) if hasattr(user_reactor, 'display_avatar') else None
                await ctx.points_manager.add_points(
                    payload.user_id,
                    1,
                    "reaction_given",
                    payload.guild_id,
                    user_reactor.name,
                    user_reactor.discriminator,
                    avatar_url=avatar_url,
                )

            try:
                channel = client.get_channel(payload.channel_id)
                if channel:
                    msg = await channel.fetch_message(payload.message_id)
                    if msg.author.id != payload.user_id and payload.guild_id:
                        msg_avatar = str(msg.author.display_avatar.url) if hasattr(msg.author, 'display_avatar') else None
                        await ctx.points_manager.add_points(
                            msg.author.id,
                            1,
                            "reaction_received",
                            payload.guild_id,
                            msg.author.name,
                            msg.author.discriminator,
                            msg.author.bot,
                            avatar_url=msg_avatar,
                        )
            except Exception as exc:
                logger.error("Erro ao dar ponto de reação para autor: %s", exc)

        if ctx.giveaway_manager:
            try:
                channel = client.get_channel(payload.channel_id)
                if channel:
                    msg = await channel.fetch_message(payload.message_id)
                    reaction = discord.utils.get(msg.reactions, emoji=payload.emoji.name)
                    if reaction:
                        await ctx.giveaway_manager.on_reaction_add(reaction, payload.member)
            except Exception as exc:
                logger.error("❌ Erro ao processar reação: %s", exc)

        if ctx.media_manager:
            await ctx.media_manager.on_raw_reaction_add(payload, client)

    @client.event
    async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent) -> None:
        if ctx.media_manager:
            await ctx.media_manager.on_raw_reaction_remove(payload, client)

    @client.event
    async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent) -> None:
        if ctx.media_manager:
            await ctx.media_manager.on_raw_message_delete(payload)

    # ── Presença / Atividades ──────────────────────────────────────────────────
    @client.event
    async def on_presence_update(
        before: discord.Member, after: discord.Member
    ) -> None:
        if ctx.activity_tracker:
            await ctx.activity_tracker.on_presence_update(before, after)

    # ── Voz ───────────────────────────────────────────────────────────────────
    @client.event
    async def on_voice_state_update(
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if ctx.stats_collector:
            await ctx.stats_collector.on_voice_state_update(member, before, after)
        if ctx.activity_tracker:
            await ctx.activity_tracker.on_voice_state_update(member, before, after)


class BotContext:
    """
    Agrupa todos os managers/singletons do bot.
    Passado para register_events() e para as background tasks.
    Evita o uso de variáveis globais no main.py.
    """

    __slots__ = (
        "db",
        "stats_collector",
        "role_manager",
        "giveaway_manager",
        "activity_tracker",
        "embed_sender",
        "points_manager",
        "spam_detector",
        "event_monitor",
        "leaderboard_updater",
        "chat_handler",
        "memory_manager",
        "stats_analyzer",
        "invite_tracker",
        "media_manager",
        "tenor_client",
        "telegram",
        "buffer_mensagens",
        "allowed_channels",
        "ignored_voice_channels",
        "dynamic_roles_config",
        "rawg_client",
    )

    def __init__(self) -> None:
        self.db = None
        self.stats_collector = None
        self.role_manager = None
        self.giveaway_manager = None
        self.activity_tracker = None
        self.embed_sender = None
        self.points_manager = None
        self.spam_detector = None
        self.event_monitor = None
        self.leaderboard_updater = None
        self.chat_handler = None
        self.memory_manager = None
        self.stats_analyzer = None
        self.invite_tracker = None
        self.media_manager = None
        self.tenor_client = None
        self.telegram = None
        self.rawg_client = None
        self.buffer_mensagens: list = []
        self.allowed_channels: list[int] = list(DEFAULT_ALLOWED_CHANNELS)
        self.ignored_voice_channels: list[int] = []
        self.dynamic_roles_config: dict = {}
