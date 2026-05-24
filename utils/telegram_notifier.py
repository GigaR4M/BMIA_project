# utils/telegram_notifier.py
import aiohttp
import logging
import os
from datetime import datetime
from config import now_brt


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
        return now_brt().strftime("%d/%m/%Y %H:%M:%S")


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

    # ── CARGOS POR TEMPO ───────────────────────────────────────────────────────

    async def log_role_assigned(self, member, role_name: str, days_in_server: int):
        """Notifica quando um cargo por tempo é atribuído a um membro."""
        msg = (
            f"🏅 <b>Cargo Atribuído (Tempo)</b>\n"
            f"🏠 Servidor: {member.guild.name}\n"
            f"👤 Membro: {member} (<code>{member.id}</code>)\n"
            f"🎖️ Cargo: {role_name}\n"
            f"📅 Tempo no servidor: {days_in_server} dias\n"
            f"🕒 {self._now()}"
        )
        await self.send(msg)

    async def log_role_removed(self, member, role_name: str, reason: str = "Promoção"):
        """Notifica quando um cargo por tempo é removido de um membro."""
        msg = (
            f"🔽 <b>Cargo Removido (Tempo)</b>\n"
            f"🏠 Servidor: {member.guild.name}\n"
            f"👤 Membro: {member} (<code>{member.id}</code>)\n"
            f"🎖️ Cargo removido: {role_name}\n"
            f"📋 Motivo: {reason}\n"
            f"🕒 {self._now()}"
        )
        await self.send(msg)

    # ── CARGOS DINÂMICOS ───────────────────────────────────────────────────────

    async def log_dynamic_role_assigned(self, member, role_name: str, category: str):
        """Notifica quando um cargo dinâmico (por estatísticas) é atribuído."""
        category_labels = {
            'top_1':       '🥇 Top 1 Absoluto',
            'top_2':       '🥈 Top 2 Absoluto',
            'top_3':       '🥉 Top 3 Absoluto',
            'voz':         '🎙️ Voz do Servidor',
            'streamer':    '📺 Streamer',
            'mensagens':   '💬 Mestre da Conversa',
            'toxico':      '☠️ Boca Suja',
            'gamer':       '🎮 Top Player',
            'camaleao':    '🦎 Camaleão',
            'maratonista': '🏃 Maratonista',
        }
        label = category_labels.get(category, category)
        msg = (
            f"⭐ <b>Cargo Dinâmico Atribuído</b>\n"
            f"🏠 Servidor: {member.guild.name}\n"
            f"👤 Membro: {member} (<code>{member.id}</code>)\n"
            f"🎖️ Cargo: {role_name}\n"
            f"📊 Categoria: {label}\n"
            f"🕒 {self._now()}"
        )
        await self.send(msg)

    async def log_dynamic_role_removed(self, member, role_name: str, category: str):
        """Notifica quando um cargo dinâmico é removido."""
        msg = (
            f"🔄 <b>Cargo Dinâmico Removido</b>\n"
            f"🏠 Servidor: {member.guild.name}\n"
            f"👤 Membro: {member} (<code>{member.id}</code>)\n"
            f"🎖️ Cargo: {role_name}\n"
            f"📋 Motivo: Perdeu o posto ({category})\n"
            f"🕒 {self._now()}"
        )
        await self.send(msg)

    # ── ATIVIDADES / JOGOS ────────────────────────────────────────────────────

    async def log_top_games(self, guild, games: list, period_days: int = 7):
        """Envia ranking dos jogos mais jogados no período."""
        if not games:
            return

        lines = ""
        medals = ["🥇", "🥈", "🥉"]
        for i, g in enumerate(games[:5]):
            icon = medals[i] if i < 3 else f"{i+1}."
            hours = (g.get('total_seconds') or 0) // 3600
            players = g.get('unique_users', 0)
            name = g.get('activity_name', 'Desconhecido')
            lines += f"{icon} <b>{name}</b> — {hours}h | {players} jogador(es)\n"

        msg = (
            f"🎮 <b>Top Jogos — Últimos {period_days} dias</b>\n"
            f"🏠 {guild.name}\n\n"
            f"{lines.strip()}\n"
            f"🕒 {self._now()}"
        )
        await self.send(msg)

    async def log_activity_milestone(self, member, game_name: str, total_hours: int):
        """Notifica quando um membro atinge um marco de horas em um jogo."""
        msg = (
            f"🏆 <b>Marco de Jogo Atingido!</b>\n"
            f"🏠 Servidor: {member.guild.name}\n"
            f"👤 Membro: {member}\n"
            f"🎮 Jogo: {game_name}\n"
            f"⏱️ Total: {total_hours}h jogadas\n"
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
