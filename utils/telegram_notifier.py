# utils/telegram_notifier.py
import aiohttp
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.enabled = bool(self.token and self.chat_id)

        if not self.enabled:
            logger.warning("TelegramNotifier: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados. Notificações desativadas.")

    async def send(self, message: str, parse_mode: str = "HTML"):
        """Envia mensagem para o Telegram."""
        if not self.enabled:
            return

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"Telegram error {resp.status}: {text}")
        except Exception as e:
            logger.error(f"TelegramNotifier send error: {e}")

    def _now(self):
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # ── MODERAÇÃO ──────────────────────────────────────────────────────────────

    async def log_message_deleted(self, guild, channel, author, content: str, reason: str = "IA"):
        """Notifica quando uma mensagem é deletada pela moderação."""
        safe_content = content[:200].replace("<", "&lt;").replace(">", "&gt;")
        msg = (
            f"🛡️ <b>Mensagem Deletada</b>\n"
            f"🏠 Servidor: {guild.name}\n"
            f"📢 Canal: #{channel.name}\n"
            f"👤 Autor: {author} (<code>{author.id}</code>)\n"
            f"📝 Conteúdo: <code>{safe_content}</code>\n"
            f"⚠️ Motivo: {reason}\n"
            f"🕒 {self._now()}"
        )
        await self.send(msg)

    async def log_user_warned(self, guild, user, reason: str):
        """Notifica quando um usuário recebe um aviso."""
        msg = (
            f"⚠️ <b>Aviso Emitido</b>\n"
            f"🏠 Servidor: {guild.name}\n"
            f"👤 Usuário: {user} (<code>{user.id}</code>)\n"
            f"📋 Motivo: {reason}\n"
            f"🕒 {self._now()}"
        )
        await self.send(msg)

    # ── SORTEIOS ───────────────────────────────────────────────────────────────

    async def log_giveaway_created(self, guild, prize: str, duration: str, channel):
        """Notifica quando um sorteio é criado."""
        msg = (
            f"🎉 <b>Sorteio Criado</b>\n"
            f"🏠 Servidor: {guild.name}\n"
            f"🎁 Prêmio: {prize}\n"
            f"⏱️ Duração: {duration}\n"
            f"📢 Canal: #{channel.name}\n"
            f"🕒 {self._now()}"
        )
        await self.send(msg)

    async def log_giveaway_ended(self, guild, prize: str, winners: list):
        """Notifica quando um sorteio é encerrado com seus vencedores."""
        if winners:
            winners_str = ", ".join([str(w) for w in winners])
        else:
            winners_str = "Nenhum participante"

        msg = (
            f"🏆 <b>Sorteio Encerrado</b>\n"
            f"🏠 Servidor: {guild.name}\n"
            f"🎁 Prêmio: {prize}\n"
            f"🥇 Vencedor(es): {winners_str}\n"
            f"🕒 {self._now()}"
        )
        await self.send(msg)

    # ── MEMBROS ────────────────────────────────────────────────────────────────

    async def log_member_join(self, member):
        """Notifica quando um novo membro entra no servidor."""
        msg = (
            f"✅ <b>Novo Membro</b>\n"
            f"🏠 Servidor: {member.guild.name}\n"
            f"👤 Usuário: {member} (<code>{member.id}</code>)\n"
            f"📅 Conta criada em: {member.created_at.strftime('%d/%m/%Y')}\n"
            f"🕒 {self._now()}"
        )
        await self.send(msg)

    async def log_member_leave(self, member):
        """Notifica quando um membro sai do servidor."""
        msg = (
            f"❌ <b>Membro Saiu</b>\n"
            f"🏠 Servidor: {member.guild.name}\n"
            f"👤 Usuário: {member} (<code>{member.id}</code>)\n"
            f"🕒 {self._now()}"
        )
        await self.send(msg)

    # ── ESTATÍSTICAS ───────────────────────────────────────────────────────────

    async def log_stats_summary(self, guild, stats: dict):
        """Envia um resumo de atividade do servidor."""
        msg = (
            f"📊 <b>Resumo de Atividade</b>\n"
            f"🏠 Servidor: {guild.name}\n"
            f"💬 Mensagens (hoje): {stats.get('messages_today', 0)}\n"
            f"🎙️ Horas de voz: {stats.get('voice_hours', 0)}\n"
            f"👥 Membros ativos: {stats.get('active_members', 0)}\n"
            f"🏅 Top usuário: {stats.get('top_user', 'N/A')}\n"
            f"🕒 {self._now()}"
        )
        await self.send(msg)

    # ── BOT ────────────────────────────────────────────────────────────────────

    async def log_bot_ready(self, bot_name: str, guild_count: int):
        """Notifica quando o bot fica online."""
        msg = (
            f"🟢 <b>Bot Online</b>\n"
            f"🤖 Nome: {bot_name}\n"
            f"🏠 Servidores: {guild_count}\n"
            f"🕒 {self._now()}"
        )
        await self.send(msg)
