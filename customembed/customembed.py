import discord
from redbot.core import commands, app_commands, Config
from discord import ui

ALLOWED_ROLE_IDS = [1198381095553617922, 1252252269790105721]

class CustomEmbedModal(ui.Modal, title="Create Custom Embed"):
    title = ui.TextInput(label="Title", placeholder="Enter the embed title here", required=True)
    description = ui.TextInput(label="Description", style=discord.TextStyle.long, placeholder="Enter the embed description here", required=True)

    def __init__(self, bot, guild_config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.guild_config = guild_config

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=self.title.value,
            description=self.description.value,
            color=self.guild_config["default_color"]
        )
        embed.set_image(url=self.guild_config["default_image"])
        await interaction.response.send_message(embed=embed)

class CustomEmbed(commands.Cog):
    """A cog to create custom embeds with modals."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_guild = {
            "default_color": 0x437820,
            "default_image": "https://example.com/default_image.png"
        }
        self.config.register_guild(**default_guild)

    @app_commands.command()
    @app_commands.guild_only()
    async def createembed(self, interaction: discord.Interaction):
        """Create a custom embed."""
        if not any(role.id in ALLOWED_ROLE_IDS for role in interaction.user.roles):
            return await interaction.response.send_message("You do not have the required roles to use this command.", ephemeral=True)

        guild_config = await self.config.guild(interaction.guild).all()
        modal = CustomEmbedModal(self.bot, guild_config)
        await interaction.response.send_modal(modal)

    @app_commands.command()
    @app_commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def setembedconfig(self, interaction: discord.Interaction, color: str, image_url: str):
        """Set the default embed color and image. Only for admins."""
        try:
            color = int(color, 16)
        except ValueError:
            return await interaction.response.send_message("Invalid color format. Please use a hexadecimal value.", ephemeral=True)

        await self.config.guild(interaction.guild).default_color.set(color)
        await self.config.guild(interaction.guild).default_image.set(image_url)
        await interaction.response.send_message("Default embed color and image have been updated.", ephemeral=True)

async def setup(bot):
    cog = CustomEmbed(bot)
    bot.add_cog(cog)
    bot.tree.add_command(cog.createembed)
    bot.tree.add_command(cog.setembedconfig)

async def teardown(bot):
    bot.tree.remove_command("createembed")
    bot.tree.remove_command("setembedconfig")
