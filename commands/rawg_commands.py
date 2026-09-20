# commands/rawg_commands.py — Comandos Slash de Busca de Jogos (RAWG)
"""
Comando de barra /jogo com Autocomplete em tempo real via RAWG Video Games Database API,
filtros opcionais por plataforma e visualização detalhada ou resumida da ficha técnica.
"""

import logging
from typing import Optional
import discord
from discord import app_commands
from utils.rawg_client import (
    RawgClient,
    PARENT_PLATFORMS,
    clean_html,
    format_metacritic_badge,
    format_star_rating,
)

logger = logging.getLogger(__name__)

PLATFORM_CHOICES = [
    app_commands.Choice(name="🖥️ PC (Windows)", value="pc"),
    app_commands.Choice(name="🎮 PlayStation (PS4/PS5)", value="playstation"),
    app_commands.Choice(name="🟩 Xbox (One/Series)", value="xbox"),
    app_commands.Choice(name="🔴 Nintendo Switch", value="nintendo"),
    app_commands.Choice(name="📱 iOS (iPhone/iPad)", value="ios"),
    app_commands.Choice(name="🤖 Android", value="android"),
]


class GameLinksView(discord.ui.View):
    """View com botões de links rápidos (RAWG, Website Oficial, Lojas)."""

    def __init__(self, rawg_slug: str, website_url: Optional[str], stores: list[dict[str, str]]):
        super().__init__(timeout=180)

        # Botão para página do RAWG
        if rawg_slug:
            self.add_item(
                discord.ui.Button(
                    label="Página no RAWG",
                    style=discord.ButtonStyle.link,
                    url=f"https://rawg.io/games/{rawg_slug}",
                    emoji="🌐",
                )
            )

        # Botão para site oficial
        if website_url and website_url.startswith("http"):
            self.add_item(
                discord.ui.Button(
                    label="Site Oficial",
                    style=discord.ButtonStyle.link,
                    url=website_url,
                    emoji="🔗",
                )
            )

        # Adiciona até 3 botões de lojas mais populares
        added_stores = 0
        for s in stores:
            if added_stores >= 3:
                break
            url = s.get("url")
            name = s.get("name", "Loja")
            if url and url.startswith("http"):
                self.add_item(
                    discord.ui.Button(
                        label=name[:20],
                        style=discord.ButtonStyle.link,
                        url=url,
                        emoji="🛒",
                    )
                )
                added_stores += 1


class RawgCommands(app_commands.Group):
    """Grupo e comando de pesquisa de jogos via RAWG."""

    def __init__(self, rawg_client: RawgClient):
        super().__init__(name="gamesdb", description="Consulta ao banco de dados de jogos")
        self.rawg = rawg_client


def setup_rawg_slash_command(tree: app_commands.CommandTree, rawg_client: RawgClient):
    """Registra o comando raiz /jogo com autocomplete na CommandTree."""

    @tree.command(
        name="jogo",
        description="Pesquise jogos no banco de dados RAWG com busca em tempo real",
    )
    @app_commands.describe(
        nome="Digite as iniciais ou nome do jogo (use as sugestões do menu)",
        plataforma="Filtre os resultados por plataforma específica (opcional)",
        detalhes="Deseja ver a ficha técnica completa com requisitos e lojas? (opcional)",
    )
    @app_commands.choices(plataforma=PLATFORM_CHOICES)
    async def jogo_command(
        interaction: discord.Interaction,
        nome: str,
        plataforma: Optional[app_commands.Choice[str]] = None,
        detalhes: Optional[bool] = False,
    ):
        await interaction.response.defer()

        if not rawg_client.is_configured:
            embed_err = discord.Embed(
                title="⚙️ Integração RAWG não configurada",
                description=(
                    "A chave de API do **RAWG** (`RAWG_API_KEY`) não está definida no arquivo `.env`.\n\n"
                    "Crie uma conta gratuita em [rawg.io/apidocs](https://rawg.io/apidocs) para obter uma chave."
                ),
                color=discord.Color.orange(),
            )
            await interaction.followup.send(embed=embed_err, ephemeral=True)
            return

        try:
            target_id_or_slug = nome.strip()
            platform_filter = plataforma.value if plataforma else None

            # Tenta buscar diretamente pelo ID ou slug se o usuário selecionou uma opção do autocomplete
            game_data = None
            if target_id_or_slug.isdigit() or "-" in target_id_or_slug:
                game_data = await rawg_client.get_game_details(target_id_or_slug)

            # Se não encontrou por ID/slug direto, faz uma busca textual
            if not game_data:
                search_results = await rawg_client.search_games(
                    query=target_id_or_slug,
                    parent_platform=platform_filter,
                    page_size=1,
                )
                if search_results:
                    game_data = await rawg_client.get_game_details(search_results[0]["id"])

            if not game_data:
                embed_not_found = discord.Embed(
                    title="🔍 Jogo não encontrado",
                    description=f"Não encontramos nenhum jogo correspondente a **'{nome}'**.",
                    color=discord.Color.red(),
                )
                if platform_filter:
                    embed_not_found.description += f"\nFiltro de plataforma ativo: **{plataforma.name}**."
                await interaction.followup.send(embed=embed_not_found)
                return

            # Extração dos dados do jogo
            title = game_data.get("name", "Jogo Desconhecido")
            slug = game_data.get("slug", "")
            released = game_data.get("released") or "Data desconhecida"
            if released and len(released) == 10 and released.count("-") == 2:
                # Formata AAAA-MM-DD para DD/MM/AAAA
                y, m, d = released.split("-")
                released = f"{d}/{m}/{y}"

            metacritic = game_data.get("metacritic")
            rating = game_data.get("rating", 0.0)
            ratings_count = game_data.get("ratings_count", 0)
            cover_url = game_data.get("background_image")
            website_url = game_data.get("website")

            # Gêneros
            genres = [g.get("name") for g in (game_data.get("genres") or []) if g.get("name")]
            genres_str = ", ".join(genres) if genres else "Não especificado"

            # Plataformas
            parent_plats = game_data.get("parent_platforms", []) or []
            platform_names = []
            for p in parent_plats:
                plat_info = p.get("platform", {})
                if plat_info.get("name"):
                    platform_names.append(plat_info.get("name"))
            platforms_str = ", ".join(platform_names) if platform_names else "Multiplataforma"

            # Desenvolvedores e Publicadoras
            devs = [d.get("name") for d in (game_data.get("developers") or []) if d.get("name")]
            devs_str = ", ".join(devs) if devs else "N/A"

            publishers = [p.get("name") for p in (game_data.get("publishers") or []) if p.get("name")]
            pubs_str = ", ".join(publishers) if publishers else "N/A"

            # Descrição limpa
            desc_raw = game_data.get("description_raw") or game_data.get("description") or ""
            desc_clean = clean_html(desc_raw, max_len=600 if not detalhes else 900)

            # Cor do Embed baseada na nota do Metacritic
            embed_color = discord.Color.purple()
            if metacritic:
                if metacritic >= 75:
                    embed_color = discord.Color.green()
                elif metacritic >= 50:
                    embed_color = discord.Color.gold()
                else:
                    embed_color = discord.Color.red()

            embed = discord.Embed(
                title=f"🎮 {title}",
                description=desc_clean,
                color=embed_color,
            )

            if cover_url:
                embed.set_image(url=cover_url)

            # Avaliações e Metacritic
            embed.add_field(
                name="⭐ Avaliação",
                value=format_star_rating(rating, ratings_count),
                inline=True,
            )
            embed.add_field(
                name="🎯 Metacritic",
                value=format_metacritic_badge(metacritic),
                inline=True,
            )
            embed.add_field(
                name="📅 Lançamento",
                value=f"**{released}**",
                inline=True,
            )

            embed.add_field(
                name="🏷️ Gêneros",
                value=genres_str,
                inline=True,
            )
            embed.add_field(
                name="🕹️ Plataformas",
                value=platforms_str,
                inline=True,
            )
            embed.add_field(
                name="🏢 Criação",
                value=f"Dev: **{devs_str}**\nPub: **{pubs_str}**",
                inline=True,
            )

            stores = rawg_client.extract_stores(game_data)

            # Se pediu detalhes completos (Ficha Técnica Avançada)
            if detalhes:
                playtime = game_data.get("playtime", 0)
                if playtime:
                    embed.add_field(
                        name="⏱️ Tempo Médio de Jogo",
                        value=f"~{playtime} horas para zerar",
                        inline=True,
                    )

                esrb = game_data.get("esrb_rating")
                if esrb and esrb.get("name"):
                    embed.add_field(
                        name="🔞 Classificação Indicativa",
                        value=f"**{esrb.get('name')}**",
                        inline=True,
                    )

                # Requisitos de Sistema para PC
                pc_reqs = rawg_client.extract_pc_requirements(game_data)
                if pc_reqs["minimum"]:
                    embed.add_field(
                        name="💻 Requisitos Mínimos (PC)",
                        value=f"```{pc_reqs['minimum'][:400]}```",
                        inline=False,
                    )
                if pc_reqs["recommended"]:
                    embed.add_field(
                        name="⚡ Requisitos Recomendados (PC)",
                        value=f"```{pc_reqs['recommended'][:400]}```",
                        inline=False,
                    )

                # Lista de lojas
                if stores:
                    store_links_text = "\n".join(
                        f"• [{s['name']}]({s['url']})" for s in stores[:5]
                    )
                    embed.add_field(
                        name="🛒 Onde Comprar",
                        value=store_links_text,
                        inline=False,
                    )

            embed.set_footer(
                text="Dados fornecidos por RAWG Video Games Database • BMIA Bot",
                icon_url="https://rawg.io/assets/apple-touch-icon-180x180.png",
            )

            view = GameLinksView(rawg_slug=slug, website_url=website_url, stores=stores)
            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            logger.error("Erro ao executar comando /jogo: %s", e, exc_info=True)
            await interaction.followup.send(
                "❌ Ocorreu um erro ao consultar as informações do jogo. Tente novamente mais tarde.",
                ephemeral=True,
            )

    @jogo_command.autocomplete("nome")
    async def jogo_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete disparado em tempo real conforme o usuário digita as letras do jogo."""
        if not rawg_client.is_configured or not current.strip():
            return []

        try:
            # Obtém a plataforma selecionada se o usuário já preencheu esse campo
            selected_platform = None
            try:
                if hasattr(interaction, "namespace") and hasattr(interaction.namespace, "plataforma"):
                    selected_platform = interaction.namespace.plataforma
            except Exception:
                pass

            results = await rawg_client.search_games(
                query=current.strip(),
                parent_platform=selected_platform,
                page_size=8,
            )

            choices = []
            for game in results:
                name = game.get("name", "Jogo")
                released = game.get("released") or ""
                year = f" ({released[:4]})" if released and len(released) >= 4 else ""

                # Nome exibido no menu (máximo 100 caracteres permitido pelo Discord)
                display_name = f"🎮 {name}{year}"
                if len(display_name) > 100:
                    display_name = display_name[:97] + "…"

                # O valor enviado pode ser o ID do jogo para busca exata e rápida
                game_id = str(game.get("id", name))

                choices.append(app_commands.Choice(name=display_name, value=game_id))

            return choices

        except Exception as e:
            logger.warning("Erro no autocomplete do /jogo: %s", e)
            return []
