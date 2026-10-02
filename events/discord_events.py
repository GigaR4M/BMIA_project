# events/discord_events.py — Handlers de Eventos do Discord
"""
Todos os event handlers extraídos do main.py.
Recebem as dependências via parâmetro (sem variáveis globais).
O módulo expõe `register_events(client, ctx)` que registra todos os handlers.
"""

import re
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import discord

from config import (
    DEFAULT_ALLOWED_CHANNELS,
    DEFAULT_IGNORED_VOICE_CHANNELS,
    DEFAULT_DYNAMIC_ROLES_CONFIG,
    now_brt,
)
from utils.ai_tools import AIToolkit
from utils.giphy_client import to_direct_gif_url

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


def extract_and_clean_gif(text: str, fallback_gif_url: str | None = None) -> tuple[str | None, str]:
    """
    Remove URLs e marcações de GIF do texto para que nenhum link apareça,
    retornando (direct_gif_url, clean_text).
    """
    if not text:
        return (to_direct_gif_url(fallback_gif_url) if fallback_gif_url else None), text

    gif_url = None

    # Procura formato markdown [qualquer_coisa](url) ou [](url)
    md_pattern = r'\[[^\]]*\]\((https?://(?:media\d*\.giphy\.com/media/[^\s\)]+|giphy\.com/gifs/[^\s\)]+|media\.tenor\.com/[^\s\)]+|tenor\.com/view/[^\s\)]+))\)'
    match_md = re.search(md_pattern, text)
    if match_md:
        gif_url = match_md.group(1)
        text = re.sub(md_pattern, '', text).strip()

    # Procura URL solta
    raw_pattern = r'(https?://(?:media\d*\.giphy\.com/media/[^\s\)]+|giphy\.com/gifs/[^\s\)]+|media\.tenor\.com/[^\s\)]+|tenor\.com/view/[^\s\)]+))'
    match_raw = re.search(raw_pattern, text)
    if match_raw:
        if not gif_url:
            gif_url = match_raw.group(1)
        text = re.sub(raw_pattern, '', text).strip()

    # Remove qualquer colchete vazio residual como []() ou [​]()
    text = re.sub(r'\[[\s\u200b]*\]\([^\)]*\)', '', text).strip()

    final_url = gif_url or fallback_gif_url
    direct_url = to_direct_gif_url(final_url) if final_url else None
    return direct_url, text


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
                                gif_client=ctx.giphy_client or ctx.tenor_client,
                                current_message=message,
                                client=client,
                                telegram=getattr(ctx, "telegram", None),
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
                            1. Personalidade: Responda como um membro participante e bem-humorado do servidor, descontraído, zoeiro e sagaz, nunca como um robô corporativo ou distante.
                            2. Uso de Ferramentas (Tools): Sempre que o usuário perguntar sobre estatísticas do servidor, rankings de jogos específicos (ex: Roblox, Valorant), tempo de voz, quantidade de mensagens ou dados de membros, USE as ferramentas disponíveis para obter os dados reais do banco de dados.
                            3. Expressão com GIFs de Robô / IA: Por ser uma IA em um servidor descontraído e de zoeira, use a tool 'buscar_gif' para exprimir seus sentimentos, ironias ou reações visuais. Dê preferência a GIFs temáticos de robôs, andróides ou IAs (ex: Sonny do filme 'Eu, Robô', robôs rindo, confusos, com tela azul/glitch, robôs dançando, Terminator, Wall-E, etc.).
                            4. Respostas Apenas com GIF: Se um GIF expressar perfeitamente sua reação ao que o usuário disse (por exemplo, um robô chocado, dando joinha ou dando facepalm), você pode responder SOMENTE chamando a tool 'buscar_gif' e deixando o texto de resposta vazio ou mínimo. O sistema exibirá o GIF de forma limpa.
                            5. Moderação e Denúncias Proativas ('reportar_mensagem'): Se uma mensagem ofensiva/tóxica passou batido pela moderação automática, ou se um usuário reclamar que se sentiu ofendido ou perguntar se algo é permitido, você pode analisar as mensagens recentes do histórico e, a seu critério, acionar a tool 'reportar_mensagem' passando o ID do usuário autor da ofensa, o motivo e o conteúdo. Avise ao usuário com naturalidade que você reportou o caso para os moderadores humanos avaliarem.
                            6. Dança do BMIA: Você possui um GIF oficial dançando animado e engraçado (https://media.giphy.com/media/EU5BbihTxT1TyTfehh/giphy.gif). Use a tool 'buscar_gif' com tema 'bmia danca' quando pedirem para você dançar ou em momentos de comemoração especial!
                            7. Fatos e Proibição de Alucinações: NUNCA invente números, horas jogadas ou posições de ranking que não estejam no contexto ou no resultado das ferramentas.
                            8. Proibição de Templates/Placeholders: NUNCA use marcações entre colchetes como '[Nome do usuário]' ou '[inserir número]'. Se não houver dados, diga a verdade de forma bem-humorada.
                            9. Conciso e Coloquial: Mantenha as respostas concisas e use o contexto/memórias do servidor para personalizar a interação.
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

                        user_prompt = f"{reply_context}[Mensagem ID: {message.id} | Autor: {message.author.display_name} | ID_Usuario: {message.author.id}]: {resolved_content}"

                        response_text = await ctx.chat_handler.generate_response(
                            user_prompt,
                            history=formatted_history,
                            system_instruction=system_instruction,
                            toolkit=toolkit,
                        )

                        # Extrai o GIF e limpa totalmente qualquer link do corpo do texto
                        fallback_gif = getattr(toolkit, "last_gif_url", None) if toolkit else None
                        gif_url, clean_response_text = extract_and_clean_gif(
                            response_text, fallback_gif_url=fallback_gif
                        )

                        if ctx.memory_manager and message.guild:
                            client.loop.create_task(
                                ctx.memory_manager.process_message_for_memory(
                                    message.guild.id,
                                    message.author.id,
                                    resolved_content,
                                    clean_response_text or response_text,
                                )
                            )

                        embed = None
                        if gif_url:
                            embed = discord.Embed(color=0x2b2d31)
                            embed.set_image(url=gif_url)

                        if len(clean_response_text) > 2000:
                            chunks = [
                                clean_response_text[i:i + 2000]
                                for i in range(0, len(clean_response_text), 2000)
                            ]
                            for idx, chunk in enumerate(chunks):
                                if idx == len(chunks) - 1 and embed:
                                    await message.reply(chunk, embed=embed)
                                else:
                                    await message.reply(chunk)
                        elif clean_response_text:
                            if embed:
                                await message.reply(clean_response_text, embed=embed)
                            else:
                                await message.reply(clean_response_text)
                        elif embed:
                            await message.reply(embed=embed)

                    except Exception as exc:
                        logger.error("Erro no ChatHandler: %s", exc)
                        await message.reply("Desculpe, tive um problema ao tentar responder.")

        # Pontos por mensagem (canais permitidos no servidor atual)
        allowed = await ctx.get_allowed_channels(message.guild.id) if message.guild else ctx.allowed_channels
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

        # Rastreamento Automático de Jogos Sugeridos (Links da Steam)
        if message.guild and ctx.db and "store.steampowered.com/app/" in message.content:
            from utils.gg_deals_client import extract_steam_appid, GGDealsClient
            appid = extract_steam_appid(message.content)
            if appid:
                async def auto_track_game():
                    try:
                        # Validação de canal: canal de jogos configurado ou canais principais
                        deals_ch = await ctx.get_deals_channel(message.guild.id)
                        if deals_ch:
                            if message.channel.id != deals_ch:
                                return
                        else:
                            allowed_channels = await ctx.get_allowed_channels(message.guild.id)
                            if message.channel.id not in allowed_channels:
                                return

                        existing = await ctx.db.get_tracked_game(message.guild.id, appid)
                        if not existing:
                            gg_client = getattr(ctx, "gg_deals_client", None) or GGDealsClient()
                            info = await gg_client.get_game_info(appid)
                            if info:
                                await ctx.db.add_tracked_game(
                                    guild_id=message.guild.id,
                                    channel_id=message.channel.id,
                                    message_id=message.id,
                                    steam_appid=info["steam_appid"],
                                    game_name=info["game_name"],
                                    suggested_by_id=message.author.id,
                                    base_price=info["base_price"],
                                    current_price=info["current_price"],
                                    discount_percent=info["discount_percent"],
                                    historical_low_price=info["historical_low_price"],
                                    best_store_name=info["best_store_name"],
                                    best_store_url=info["best_store_url"],
                                    header_image_url=info["header_image_url"],
                                    gg_deals_url=info["gg_deals_url"]
                                )
                                logger.info(f"🎮 Jogo '{info['game_name']}' (AppID {appid}) registrado automaticamente para monitoramento de ofertas no canal #{message.channel.name}.")
                                try:
                                    await message.add_reaction("🎮")
                                except Exception:
                                    pass
                    except Exception as track_err:
                        logger.warning(f"Erro ao rastrear jogo sugerido automaticamente: {track_err}")
                
                client.loop.create_task(auto_track_game())

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

        # Rastreamento de estatísticas de GIFs para Retrospectiva
        if message.guild and ctx.db and not message.author.bot:
            gif_found = None
            if message.attachments:
                for att in message.attachments:
                    if (att.content_type and "gif" in att.content_type) or att.filename.lower().endswith(".gif"):
                        gif_found = att.url
                        break
            if not gif_found and message.content:
                g_match = re.search(r'(https?://(?:tenor\.com/view/[^\s]+|media\.tenor\.com/[^\s]+|giphy\.com/[^\s]+|media[0-9]*\.giphy\.com/[^\s]+|[^\s]+\.gif(?:\?[^\s]*)?))', message.content, re.IGNORECASE)
                if g_match:
                    gif_found = g_match.group(0)
            if gif_found:
                asyncio.create_task(ctx.db.increment_gif_usage(message.guild.id, gif_found, now_brt().year, message.jump_url))

    # ── Reações ────────────────────────────────────────────────────────────────
    @client.event
    async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
        if payload.member and payload.member.bot:
            return

        # Rastreamento global de emojis para Retrospectiva Anual
        if payload.guild_id and ctx.db:
            emoji_str = str(payload.emoji)
            is_custom = payload.emoji.is_custom_emoji()
            asyncio.create_task(ctx.db.increment_emoji_usage(payload.guild_id, emoji_str, is_custom, now_brt().year))

        allowed = await ctx.get_allowed_channels(payload.guild_id) if payload.guild_id else ctx.allowed_channels
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
    async def on_message_edit(before: discord.Message, after: discord.Message) -> None:
        """Notifica edições de mensagem via Telegram. Ignora bots e edições sem mudança de texto."""
        # Ignora bots e mudanças sem alteração de conteúdo de texto
        if before.author.bot:
            return
        before_text = before.content or ""
        after_text = after.content or ""
        if before_text == after_text:
            return
        # Ignora edições com conteúdo vazio em ambos os lados (ex: somente embed)
        if not before_text and not after_text:
            return

        if ctx.telegram and after.guild:
            try:
                msg_url = after.jump_url  # URL direta para a mensagem no Discord
                await ctx.telegram.log_message_edited(
                    guild=after.guild,
                    channel=after.channel,
                    author=after.author,
                    before_content=before_text,
                    after_content=after_text,
                    message_url=msg_url,
                )
            except Exception as exc:
                logger.error("Erro ao notificar edição de mensagem no Telegram: %s", exc)

    @client.event
    async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent) -> None:
        """Notifica deleções de mensagem via Telegram e repassa ao media_manager."""
        # Tenta recuperar dados do cache do discord.py (sem RAM extra)
        cached: discord.Message | None = payload.cached_message

        if ctx.telegram and payload.guild_id:
            guild = client.get_guild(payload.guild_id)
            channel = client.get_channel(payload.channel_id)
            if guild and channel:
                # Só notifica se tiver autor e se não for bot
                author = cached.author if cached else None
                content = cached.content if cached else ""
                if author is None or not author.bot:
                    try:
                        await ctx.telegram.log_message_deleted_event(
                            guild=guild,
                            channel=channel,
                            author=author,
                            content=content,
                        )
                    except Exception as exc:
                        logger.error("Erro ao notificar deleção de mensagem no Telegram: %s", exc)

        # Preserva repasse ao media_manager (zero regressão)
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
        "giphy_client",
        "tenor_client",
        "telegram",
        "buffer_mensagens",
        "allowed_channels",
        "ignored_voice_channels",
        "dynamic_roles_config",
        "rawg_client",
        "gg_deals_client",
        "_guild_configs",
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
        self.giphy_client = None
        self.tenor_client = None
        self.telegram = None
        self.rawg_client = None
        self.gg_deals_client = None
        self.buffer_mensagens: list = []
        self.allowed_channels: list[int] = list(DEFAULT_ALLOWED_CHANNELS)
        self.ignored_voice_channels: list[int] = []
        self.dynamic_roles_config: dict = {}
        self._guild_configs: dict[int, dict] = {}

    async def get_guild_config(self, guild_id: int, refresh: bool = False) -> dict:
        """Retorna as configurações do servidor a partir do cache ou do banco."""
        if not refresh and guild_id in self._guild_configs:
            return self._guild_configs[guild_id]
        if self.db:
            cfg = await self.db.get_guild_config(guild_id)
            self._guild_configs[guild_id] = cfg
            return cfg
        return {}

    def invalidate_guild_config(self, guild_id: int) -> None:
        """Invalida o cache de configurações do servidor para recarga."""
        self._guild_configs.pop(guild_id, None)

    async def get_allowed_channels(self, guild_id: int) -> list[int]:
        """Retorna os canais de texto permitidos para pontuação neste servidor."""
        cfg = await self.get_guild_config(guild_id)
        channels = cfg.get("allowed_channels")
        if channels is not None and len(channels) > 0:
            return channels
        return list(DEFAULT_ALLOWED_CHANNELS)

    async def get_ignored_voice_channels(self, guild_id: int) -> list[int]:
        """Retorna os canais de voz ignorados para pontuação neste servidor."""
        cfg = await self.get_guild_config(guild_id)
        channels = cfg.get("ignored_voice_channels")
        if channels is not None and len(channels) > 0:
            return channels
        return list(DEFAULT_IGNORED_VOICE_CHANNELS)

    async def get_deals_channel(self, guild_id: int) -> Optional[int]:
        """Retorna o canal de texto configurado para jogos e promoções Steam (se houver)."""
        cfg = await self.get_guild_config(guild_id)
        return cfg.get("deals_channel_id")

    async def get_dynamic_roles_config(self, guild_id: int) -> dict:
        """Retorna a configuração de cargos dinâmicos para este servidor."""
        cfg = await self.get_guild_config(guild_id)
        roles = cfg.get("dynamic_roles_config")
        if roles is not None and len(roles) > 0:
            return roles
        return dict(DEFAULT_DYNAMIC_ROLES_CONFIG)

