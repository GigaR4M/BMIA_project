# commands/deals_commands.py - Comandos Slash para Promoções da Steam e Eventos Sazonais

import discord
from discord import app_commands
import logging
from typing import Optional, List
from datetime import datetime, timezone
import zoneinfo

from database import Database
from utils.gg_deals_client import GGDealsClient, extract_steam_appid

logger = logging.getLogger(__name__)
BRT = zoneinfo.ZoneInfo("America/Sao_Paulo")


def format_countdown(target_time: datetime, now_time: datetime) -> str:
    """Calcula e formata uma contagem regressiva amigável em português."""
    delta = target_time - now_time
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "agora"
    
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if days == 0 and minutes > 0:
        parts.append(f"{minutes}min")
    
    return " ".join(parts) if parts else "< 1min"


class SteamCommands(app_commands.Group):
    """Grupo de comandos de eventos sazonais e promoções da Steam."""

    def __init__(self, db: Database):
        super().__init__(name="steam", description="Eventos e promoções sazonais da Steam")
        self.db = db

    @app_commands.command(name="eventos", description="Exibe o calendário dos próximos eventos e promoções sazonais da Steam")
    @app_commands.describe(limite="Quantidade de eventos para listar (1 a 10, padrão: 5)")
    async def list_events(self, interaction: discord.Interaction, limite: int = 5):
        await interaction.response.defer()
        limite = max(1, min(limite, 10))

        events = await self.db.get_upcoming_steam_events(limit=limite)
        if not events:
            await interaction.followup.send("ℹ️ Nenhum evento futuro cadastrado no momento.", ephemeral=True)
            return

        now = datetime.now(timezone.utc)

        embed = discord.Embed(
            title="📅 Calendário Oficial de Promoções e Festivais da Steam",
            description="Datas oficiais e fuso horário de início/término: **14:00 BRT** (10:00 AM PT).",
            color=discord.Color.from_rgb(26, 61, 92)  # Steam Navy Blue
        )

        featured_banner = None

        for ev in events:
            start_dt = ev["start_time"]
            end_dt = ev["end_time"]
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)

            start_brt = start_dt.astimezone(BRT).strftime("%d/%m/%Y às %H:%M BRT")
            end_brt = end_dt.astimezone(BRT).strftime("%d/%m/%Y às %H:%M BRT")

            type_emoji = {
                "major_sale": "🔥 **Grande Promoção Sazonal**",
                "themed_fest": "🎉 **Festival Temático**",
                "next_fest": "🎮 **Steam Vem Aí (Next Fest)**"
            }.get(ev.get("event_type", ""), "🏷️ **Evento Steam**")

            # Status e contagem
            if start_dt <= now < end_dt:
                status_str = f"🔴 **EM ANDAMENTO AGORA!** (Termina em {format_countdown(end_dt, now)})"
                if not featured_banner and ev.get("banner_url"):
                    featured_banner = ev["banner_url"]
            elif now < start_dt:
                status_str = f"⏳ **Começa em:** {format_countdown(start_dt, now)}"
                if not featured_banner and ev.get("banner_url"):
                    featured_banner = ev["banner_url"]
            else:
                status_str = "Concluído"

            field_val = (
                f"{type_emoji}\n"
                f"📆 **Período:** {start_brt} até {end_brt}\n"
                f"{status_str}\n"
            )
            if ev.get("description"):
                field_val += f"_{ev['description']}_\n"

            embed.add_field(
                name=f"📌 {ev['event_name']}",
                value=field_val,
                inline=False
            )

        if featured_banner:
            embed.set_image(url=featured_banner)

        embed.set_footer(text="Dados sincronizados com o calendário oficial da Valve Steamworks")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="evento_banner", description="[Admin] Atualiza a URL do banner para um evento da Steam")
    @app_commands.describe(
        evento_slug="Slug identificador do evento",
        banner_url="Link direto da imagem do banner (deixe vazio para remover)"
    )
    @app_commands.default_permissions(administrator=True)
    async def set_banner(self, interaction: discord.Interaction, evento_slug: str, banner_url: Optional[str] = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem atualizar banners de eventos.", ephemeral=True)
            return

        success = await self.db.update_steam_event_banner(evento_slug, banner_url.strip() if banner_url else None)
        if success:
            await interaction.response.send_message(f"✅ Banner do evento `{evento_slug}` atualizado com sucesso!", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Evento com slug `{evento_slug}` não encontrado.", ephemeral=True)

    @set_banner.autocomplete("evento_slug")
    async def event_slug_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        events = await self.db.get_upcoming_steam_events(limit=25)
        choices = []
        for ev in events:
            slug = ev["event_slug"]
            name = ev["event_name"]
            if current.lower() in slug.lower() or current.lower() in name.lower():
                display = f"{name[:60]} ({slug})" if len(name) > 60 else f"{name} ({slug})"
                choices.append(app_commands.Choice(name=display[:100], value=slug))
        return choices[:25]


class TrackedGamesCommands(app_commands.Group):
    """Grupo de comandos de monitoramento de jogos e ofertas da comunidade."""

    def __init__(self, db: Database, gg_client: Optional[GGDealsClient] = None):
        super().__init__(name="jogos", description="Monitoramento de jogos sugeridos e ofertas")
        self.db = db
        self.gg_client = gg_client or GGDealsClient()

    @app_commands.command(name="monitorados", description="Exibe os jogos monitorados pela comunidade e promoções ativas")
    async def list_games(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("Este comando só pode ser utilizado dentro de um servidor.", ephemeral=True)
            return

        games = await self.db.get_tracked_games(interaction.guild.id, is_active=True)
        if not games:
            await interaction.followup.send(
                "🎮 Nenhum jogo monitorado no momento.\nEnvie um link da Steam no canal de sugestões ou use `/jogos adicionar`!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎮 Lista de Desejos & Jogos Monitorados",
            description=f"Monitorando **{len(games)}** jogos sugeridos pela comunidade com checagem de descontos e menor preço histórico.",
            color=discord.Color.gold()
        )

        on_sale_count = 0
        for g in games[:15]:
            discount = g.get("discount_percent") or 0
            curr_price = float(g.get("current_price") or 0.0)
            base_price = float(g.get("base_price") or 0.0)
            hist_low = float(g.get("historical_low_price") or 0.0)
            store = g.get("best_store_name") or "Steam"
            store_url = g.get("best_store_url") or f"https://store.steampowered.com/app/{g['steam_appid']}/"

            if discount > 0:
                on_sale_count += 1
                status = f"🔥 **-{discount}% OFF** | **R$ {curr_price:.2f}** ~~(R$ {base_price:.2f})~~"
                store_info = f"🛒 Melhor oferta em: [{store}]({store_url})"
            elif curr_price == 0.0 and base_price == 0.0:
                status = "🆓 **Gratuito para Jogar**"
                store_info = f"🔗 [Página na Steam]({store_url})"
            else:
                status = f"💵 **R$ {curr_price:.2f}** (Sem desconto)"
                store_info = f"🔗 [Ver na Steam]({store_url})"

            if hist_low > 0 and curr_price <= hist_low and discount > 0:
                status += " ⭐ **MENOR PREÇO HISTÓRICO!**"

            embed.add_field(
                name=f"🕹️ {g['game_name']}",
                value=f"{status}\n{store_info}",
                inline=False
            )

        if len(games) > 15:
            embed.set_footer(text=f"Mostrando 15 de {len(games)} jogos monitorados. ({on_sale_count} em promoção agora)")
        else:
            embed.set_footer(text=f"Total: {len(games)} jogos monitorados ({on_sale_count} em promoção no momento)")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="adicionar", description="Adiciona um jogo da Steam à lista de monitoramento de ofertas")
    @app_commands.describe(link_ou_id="Link da página do jogo na Steam ou AppID numérico")
    async def add_game(self, interaction: discord.Interaction, link_ou_id: str):
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.followup.send("Comando exclusivo para servidores.", ephemeral=True)
            return

        appid = extract_steam_appid(link_ou_id)
        if not appid:
            await interaction.followup.send("❌ Link ou AppID inválido. Certifique-se de enviar uma URL da Steam (ex: `https://store.steampowered.com/app/2680010/`).", ephemeral=True)
            return

        info = await self.gg_client.get_game_info(appid)
        if not info:
            await interaction.followup.send(f"❌ Não foi possível encontrar informações na Steam para o AppID `{appid}`.", ephemeral=True)
            return

        tracked = await self.db.add_tracked_game(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel_id,
            message_id=None,
            steam_appid=info["steam_appid"],
            game_name=info["game_name"],
            suggested_by_id=interaction.user.id,
            base_price=info["base_price"],
            current_price=info["current_price"],
            discount_percent=info["discount_percent"],
            historical_low_price=info["historical_low_price"],
            best_store_name=info["best_store_name"],
            best_store_url=info["best_store_url"],
            header_image_url=info["header_image_url"],
            gg_deals_url=info["gg_deals_url"]
        )

        embed = discord.Embed(
            title=f"✅ Jogo Adicionado ao Monitoramento!",
            description=f"**{info['game_name']}** agora será monitorado para promoções e quedas de preço.",
            color=discord.Color.green()
        )
        if info.get("header_image_url"):
            embed.set_thumbnail(url=info["header_image_url"])

        curr_p = info["current_price"]
        disc = info["discount_percent"]
        if disc > 0:
            price_text = f"🔥 **-{disc}% OFF**: **R$ {curr_p:.2f}** em [{info['best_store_name']}]({info['best_store_url']})"
        elif curr_p == 0.0 and info["base_price"] == 0.0:
            price_text = "🆓 **Gratuito**"
        else:
            price_text = f"💵 **R$ {curr_p:.2f}**"

        embed.add_field(name="Preço Atual", value=price_text, inline=True)
        if info["historical_low_price"] > 0:
            embed.add_field(name="Menor Histórico", value=f"R$ {info['historical_low_price']:.2f}", inline=True)

        embed.set_footer(text=f"Sugerido por {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="remover", description="[Admin] Remove um jogo da lista de monitoramento")
    @app_commands.describe(link_ou_id="Link da página do jogo na Steam ou AppID numérico")
    @app_commands.default_permissions(administrator=True)
    async def remove_game(self, interaction: discord.Interaction, link_ou_id: str):
        if not interaction.guild:
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem remover jogos do monitoramento.", ephemeral=True)
            return

        appid = extract_steam_appid(link_ou_id)
        if not appid:
            await interaction.response.send_message("❌ Link ou AppID inválido.", ephemeral=True)
            return

        success = await self.db.remove_tracked_game(interaction.guild.id, appid)
        if success:
            await interaction.response.send_message(f"✅ Jogo (AppID `{appid}`) removido do monitoramento.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Jogo (AppID `{appid}`) não estava na lista de monitoramento deste servidor.", ephemeral=True)

    @app_commands.command(name="verificar", description="[Admin] Força uma verificação imediata de preços em todos os jogos monitorados")
    @app_commands.default_permissions(administrator=True)
    async def verify_deals(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem executar esta verificação.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        games = await self.db.get_tracked_games(interaction.guild.id, is_active=True)
        if not games:
            await interaction.followup.send("Nenhum jogo monitorado no servidor.", ephemeral=True)
            return

        updated_count = 0
        deals_found = 0

        for g in games:
            appid = g["steam_appid"]
            try:
                info = await self.gg_client.get_game_info(appid)
                if info:
                    await self.db.update_tracked_game_price(
                        game_id=g["id"],
                        current_price=info["current_price"],
                        discount_percent=info["discount_percent"],
                        historical_low_price=info["historical_low_price"],
                        best_store_name=info["best_store_name"],
                        best_store_url=info["best_store_url"],
                        header_image_url=info["header_image_url"]
                    )
                    updated_count += 1
                    if info["discount_percent"] > 0:
                        deals_found += 1
            except Exception as e:
                logger.error(f"Erro ao verificar preço do jogo {appid}: {e}")

        await interaction.followup.send(
            f"✅ Verificação concluída!\n"
            f"📊 **{updated_count}** jogos atualizados.\n"
            f"🔥 **{deals_found}** jogos com promoção ativa encontrada.",
            ephemeral=True
        )
