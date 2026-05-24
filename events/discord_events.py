# events/discord_events.py — Handlers de Eventos do Discord
"""
Todos os event handlers extraídos do main.py.
Recebem as dependências via parâmetro (sem variáveis globais).
O módulo expõe `register_events(client, ctx)` que registra todos os handlers.
"""

import re
import logging

import discord

from config import DEFAULT_ALLOWED_CHANNELS

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

    @client.event
    async def on_member_remove(member: discord.Member) -> None:
        await ctx.telegram.log_member_leave(member)

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

                            INSTRUÇÕES GERAIS:
                            1. Responda como um membro participante do servidor, não como uma IA distante.
                            2. Use o contexto acima para personalizar sua resposta.
                            3. Não use respostas muito longas e procure manter um tom coloquial.
                            4. Se houver memórias relevantes, use-as se fizer sentido.
                            """

                        response_text = await ctx.chat_handler.generate_response(
                            resolved_content,
                            history=formatted_history,
                            system_instruction=system_instruction,
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
                await ctx.points_manager.add_points(
                    message.author.id,
                    points,
                    interaction_type,
                    message.guild.id,
                    message.author.name,
                    message.author.discriminator,
                )

        # Buffer de moderação
        ctx.buffer_mensagens.append(message)
        logger.debug(
            "Buffer de moderação: %d mensagens", len(ctx.buffer_mensagens)
        )

        # Coleta estatísticas
        if ctx.stats_collector:
            await ctx.stats_collector.on_message(message)

    # ── Reações ────────────────────────────────────────────────────────────────
    @client.event
    async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
        if payload.member and payload.member.bot:
            return

        allowed = ctx.allowed_channels
        if ctx.points_manager and payload.channel_id in allowed:
            user_reactor = client.get_user(payload.user_id)
            if user_reactor and payload.guild_id:
                await ctx.points_manager.add_points(
                    payload.user_id,
                    1,
                    "reaction_given",
                    payload.guild_id,
                    user_reactor.name,
                    user_reactor.discriminator,
                )

            try:
                channel = client.get_channel(payload.channel_id)
                if channel:
                    msg = await channel.fetch_message(payload.message_id)
                    if msg.author.id != payload.user_id and payload.guild_id:
                        await ctx.points_manager.add_points(
                            msg.author.id,
                            1,
                            "reaction_received",
                            payload.guild_id,
                            msg.author.name,
                            msg.author.discriminator,
                            msg.author.bot,
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
        "telegram",
        "buffer_mensagens",
        "allowed_channels",
        "ignored_voice_channels",
        "dynamic_roles_config",
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
        self.telegram = None
        self.buffer_mensagens: list = []
        self.allowed_channels: list[int] = list(DEFAULT_ALLOWED_CHANNELS)
        self.ignored_voice_channels: list[int] = []
        self.dynamic_roles_config: dict = {}
