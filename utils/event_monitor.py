# utils/event_monitor.py - Monitor de Eventos do Discord e Presença em Eventos

import discord
from database import Database
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EventMonitor:
    """Monitor de eventos agendados do Discord com sincronização e presença real."""

    def __init__(self, db: Database):
        """
        Inicializa o monitor de eventos.

        Args:
            db: Instância do gerenciador de banco de dados
        """
        self.db = db

    async def on_scheduled_event_create(self, event: discord.ScheduledEvent):
        """Handler para criação de eventos."""
        try:
            await self.sync_event(event)
            logger.info(f"📅 Evento criado e sincronizado: {event.name} (ID: {event.id})")
        except Exception as e:
            logger.error(f"❌ Erro ao registrar criação de evento {event.id}: {e}")

    async def on_scheduled_event_update(self, before: discord.ScheduledEvent, after: discord.ScheduledEvent):
        """Handler para atualização de eventos."""
        try:
            await self.sync_event(after)
            logger.info(f"📅 Evento atualizado e sincronizado: {after.name} (ID: {after.id})")
        except Exception as e:
            logger.error(f"❌ Erro ao registrar atualização de evento {after.id}: {e}")

    async def on_scheduled_event_delete(self, event: discord.ScheduledEvent):
        """Handler para exclusão de eventos."""
        try:
            await self.db.update_event_status(event.id, "DELETED")
            logger.info(f"📅 Evento excluído: {event.name} (ID: {event.id})")
        except Exception as e:
            logger.error(f"❌ Erro ao registrar exclusão de evento {event.id}: {e}")

    async def on_scheduled_event_user_add(self, event: discord.ScheduledEvent, user: discord.User):
        """Handler para usuário entrando no evento (interessado)."""
        try:
            if not user.bot:
                await self.db.add_event_participant(event.id, user.id, "interested")
                logger.info(f"👤 {user.name} interessado no evento: {event.name}")
        except Exception as e:
            logger.error(f"❌ Erro ao registrar participante {user.id} no evento {event.id}: {e}")

    async def on_scheduled_event_user_remove(self, event: discord.ScheduledEvent, user: discord.User):
        """Handler para usuário saindo do evento."""
        try:
            await self.db.remove_event_participant(event.id, user.id)
            logger.info(f"👤 {user.name} removeu interesse do evento: {event.name}")
        except Exception as e:
            logger.error(f"❌ Erro ao remover participante {user.id} do evento {event.id}: {e}")

    async def sync_event(self, event: discord.ScheduledEvent):
        """Sincroniza metadados do evento, inscritos e presença em voz."""
        try:
            await self._upsert_event(event)
            await self.sync_event_subscribers(event)

            # Se o evento está em andamento (ACTIVE) ou já concluído (COMPLETED), sincroniza presença real
            status_str = str(event.status).lower()
            if "active" in status_str or "completed" in status_str or event.status == discord.EventStatus.active or event.status == discord.EventStatus.completed:
                await self.sync_voice_attendance(event)
        except Exception as e:
            logger.error(f"❌ Erro na sincronização do evento {event.id}: {e}")

    async def sync_event_subscribers(self, event: discord.ScheduledEvent):
        """Busca todos os usuários que clicaram em 'Interessado' no Discord."""
        try:
            async for user in event.fetch_users(limit=None):
                if not user.bot:
                    await self.db.add_event_participant(event.id, user.id, "interested")
        except Exception as e:
            logger.debug(f"Não foi possível buscar inscritos do evento {event.id}: {e}")

    async def sync_voice_attendance(self, event: discord.ScheduledEvent):
        """Registra presença real ('attended') para quem esteve no canal de voz do evento."""
        try:
            # 1. Se o canal estiver acessível e houver membros conectados agora
            channel = event.channel
            if channel and hasattr(channel, "members"):
                for member in channel.members:
                    if not member.bot:
                        await self.db.add_event_participant(event.id, member.id, "attended")
                        logger.info(f"🎙️ Presença confirmada em voz para {member.name} no evento {event.name}")

            # 2. Se houver channel_id, cruza com o histórico de voz registrado na tabela voice_activity
            if event.channel_id:
                await self.db.register_voice_attendance_for_event(
                    event.id,
                    event.channel_id,
                    event.start_time,
                    event.end_time
                )
        except Exception as e:
            logger.warning(f"⚠️ Erro ao sincronizar presença em voz para evento {event.id}: {e}")

    async def sync_all_guild_events(self, guild: discord.Guild):
        """Sincroniza todos os eventos agendados de um servidor."""
        try:
            events = guild.scheduled_events
            if not events:
                try:
                    events = await guild.fetch_scheduled_events()
                except Exception:
                    events = []

            for event in events:
                await self.sync_event(event)

            if events:
                logger.info(f"✅ Sincronizados {len(events)} eventos agendados para {guild.name}")
        except Exception as e:
            logger.error(f"❌ Erro ao sincronizar eventos da guilda {guild.id}: {e}")

    async def _upsert_event(self, event: discord.ScheduledEvent):
        """Helper para inserir/atualizar evento no banco."""
        creator_id = event.creator_id if event.creator_id else (event.creator.id if event.creator else None)

        await self.db.upsert_event(
            event_id=event.id,
            guild_id=event.guild.id,
            name=event.name,
            description=event.description,
            start_time=event.start_time,
            end_time=event.end_time,
            status=str(event.status),
            creator_id=creator_id,
            entity_type=str(event.entity_type),
            location=event.location
        )
