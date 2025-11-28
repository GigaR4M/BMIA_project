import discord
import logging
import json
from typing import Dict, Any, Optional
from database import Database

logger = logging.getLogger(__name__)

class EmbedSender:
    def __init__(self, db: Database):
        self.db = db

    async def process_pending_requests(self, client: discord.Client):
        """Busca e processa solicitações de embed pendentes."""
        try:
            pending_requests = await self.db.get_pending_embeds()
            
            for request in pending_requests:
                await self.process_request(client, request)
                
        except Exception as e:
            logger.error(f"Erro ao processar fila de embeds: {e}")

    async def process_request(self, client: discord.Client, request: Dict[str, Any]):
        """Processa uma única solicitação."""
        request_id = str(request['id'])
        guild_id = request['guild_id']
        channel_id = request['channel_id']
        
        try:
            # Parse message data if it's a string, otherwise use as is
            message_data = request['message_data']
            if isinstance(message_data, str):
                message_data = json.loads(message_data)

            guild = client.get_guild(guild_id)
            if not guild:
                await self.db.update_embed_status(request_id, 'failed', 'Guild not found')
                return

            channel = guild.get_channel(channel_id)
            if not channel:
                await self.db.update_embed_status(request_id, 'failed', 'Channel not found')
                return

            # Construct Embed
            embed = self._construct_embed(message_data)
            
            # Send message
            content = message_data.get('content', '')
            await channel.send(content=content, embed=embed)
            
            # Update status
            await self.db.update_embed_status(request_id, 'sent')
            logger.info(f"Embed enviado com sucesso: {request_id}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Falha ao enviar embed {request_id}: {error_msg}")
            await self.db.update_embed_status(request_id, 'failed', error_msg)

    def _construct_embed(self, data: Dict[str, Any]) -> discord.Embed:
        """Constrói um objeto discord.Embed a partir dos dados JSON."""
        
        # Color
        color_val = data.get('color', '#202225')
        if isinstance(color_val, str) and color_val.startswith('#'):
            color_val = int(color_val[1:], 16)
        
        embed = discord.Embed(
            title=data.get('title'),
            description=data.get('description'),
            url=data.get('url'),
            color=color_val
        )

        # Author
        author = data.get('author', {})
        if author.get('name'):
            embed.set_author(
                name=author.get('name'),
                url=author.get('url'),
                icon_url=author.get('icon_url')
            )

        # Footer
        footer = data.get('footer', {})
        if footer.get('text'):
            embed.set_footer(
                text=footer.get('text'),
                icon_url=footer.get('icon_url')
            )

        # Images
        if data.get('image_url'):
            embed.set_image(url=data.get('image_url'))
        
        if data.get('thumbnail_url'):
            embed.set_thumbnail(url=data.get('thumbnail_url'))

        # Fields
        for field in data.get('fields', []):
            if field.get('name') and field.get('value'):
                embed.add_field(
                    name=field.get('name'),
                    value=field.get('value'),
                    inline=field.get('inline', False)
                )
        
        # Timestamp
        if data.get('timestamp'):
            from datetime import datetime
            embed.timestamp = datetime.now()

        return embed
