# utils/event_monitor.py - Monitor de Eventos do Discord

import discord
from database import Database
import logging

logger = logging.getLogger(__name__)

class EventMonitor:
    """Monitor de eventos agendados do Discord."""
    
    def __init__(self, db: Database):
        """
        Inicializa o monitor de eventos.
        
        Args:
            db: Instância do gerenciador de banco de dados
        """
        self.db = db
    
    async def on_scheduled_event_create(self, event: discord.ScheduledEvent):
        """
        Handler para criação de eventos.
        """
        try:
            await self._upsert_event(event)
            logger.info(f"📅 Evento criado: {event.name} (ID: {event.id})")
        except Exception as e:
            logger.error(f"❌ Erro ao registrar criação de evento {event.id}: {e}")

    async def on_scheduled_event_update(self, before: discord.ScheduledEvent, after: discord.ScheduledEvent):
        """
        Handler para atualização de eventos.
        """
        try:
            await self._upsert_event(after)
            logger.info(f"📅 Evento atualizado: {after.name} (ID: {after.id})")
        except Exception as e:
            logger.error(f"❌ Erro ao registrar atualização de evento {after.id}: {e}")

    async def on_scheduled_event_delete(self, event: discord.ScheduledEvent):
        """
        Handler para exclusão de eventos.
        """
        try:
            await self.db.update_event_status(event.id, "DELETED")
            logger.info(f"📅 Evento excluído: {event.name} (ID: {event.id})")
        except Exception as e:
            logger.error(f"❌ Erro ao registrar exclusão de evento {event.id}: {e}")

    async def on_scheduled_event_user_add(self, event: discord.ScheduledEvent, user: discord.User):
        """
        Handler para usuário entrando no evento (interessado).
        """
        try:
            await self.db.add_event_participant(event.id, user.id, "interested")
            logger.info(f"👤 {user.name} interessado no evento: {event.name}")
        except Exception as e:
            logger.error(f"❌ Erro ao registrar participante {user.id} no evento {event.id}: {e}")

    async def on_scheduled_event_user_remove(self, event: discord.ScheduledEvent, user: discord.User):
        """
        Handler para usuário saindo do evento.
        """
        try:
            await self.db.remove_event_participant(event.id, user.id)
            logger.info(f"👤 {user.name} removeu interesse do evento: {event.name}")
        except Exception as e:
            logger.error(f"❌ Erro ao remover participante {user.id} do evento {event.id}: {e}")

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
