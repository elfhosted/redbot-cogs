import discord
from redbot.core import commands, app_commands, Config
from discord import ui
from datetime import datetime
import logging

logger = logging.getLogger("custom_embed")

ALLOWED_ROLE_IDS = [1198381095553617922, 1252252269790105721]
COLOR_CHOICES = {
    "Red": 0xFF0000,
    "Green": 0x00FF00,
    "Blue": 0x0000FF,
    "Yellow": 0xFFFF00,
    "Default": 0x437820
}

class CustomEmbedModal(ui.Modal, title="Create Custom Embed"):
    title_input = ui.TextInput(label="Title", placeholder="Enter the embed title here", required=True)
    description_input = ui.TextInput(label="Description", style=discord.TextStyle.long, placeholder="Enter the embed description here", required=True)
    author_input = ui.TextInput(label="Author", placeholder="Enter the author name", required=False)
    footer_input = ui.TextInput(label="Footer", placeholder="Enter the footer text", required=False)
    thumbnail_input = ui.TextInput(label="Thumbnail URL", placeholder="Enter the thumbnail URL", required=False)
    image_input = ui.TextInput(label="Image URL", placeholder="Enter the image URL", required=False)
    color_input = ui.TextInput(label="Color (hex code)", placeholder="Enter the hex color code (e.g., FF0000 for Red)", required=False)

    def __init__(self, bot, guild_config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.guild_config = guild_config

    async def on_submit(self, interaction: discord.Interaction):
        try:
            color = int(self.color_input.value, 16) if self.color_input.value else self.guild_config["default_color"]
        except ValueError:
            color = self.guild_config["default_color"]

        embed = discord.Embed(
            title=self.title_input.value,
            description=self.description_input.value,
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.set_image(url=self.image_input.value or self.guild_config["default_image"])

        if self.author_input.value:
            embed.set_author(name=self.author_input.value)
        if self.footer_input.value:
            embed.set_footer(text=self.footer_input.value)
        if self.thumbnail_input.value:
            embed.set_thumbnail(url=self.thumbnail_input.value)

        await interaction.response.send_message(embed=embed)

class CustomEmbed(commands.Cog):
    """A cog to create custom embeds with modals."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_guild = {
            "default_color": 0x437820,
            "default_image": "https://elfhosted.com/images/logo-green-text.jpg"
        }
        self.config.register_guild(**default_guild)

    @app_commands.command()
    @app_commands.guild_only()
    async def createembed(self, interaction: discord.Interaction):
        """Create a custom embed."""
        try:
            if not any(role.id in ALLOWED_ROLE_IDS for role in interaction.user.roles):
                return await interaction.response.send_message("You do not have the required roles to use this command.", ephemeral=True)

            guild_config = await self.config.guild(interaction.guild).all()
            modal = CustomEmbedModal(self.bot, guild_config)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"Error creating embed: {e}")
            await interaction.response.send_message("An error occurred while creating the embed.", ephemeral=True)

    @app_commands.command()
    @app_commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def setembedconfig(self, interaction: discord.Interaction, color: str, image_url: str):
        """Set the default embed color and image. Only for admins."""
        try:
            color = int(color, 16)
            await self.config.guild(interaction.guild).default_color.set(color)
            await self.config.guild(interaction.guild).default_image.set(image_url)
            await interaction.response.send_message("Default embed color and image have been updated.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Invalid color format. Please use a hexadecimal value.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error setting embed config: {e}")
            await interaction.response.send_message("An error occurred while setting the embed config.", ephemeral=True)

async def create_embed_from_message(interaction: discord.Interaction, message: discord.Message):
    """Create an embed using a message content."""
    try:
        if not any(role.id in ALLOWED_ROLE_IDS for role in interaction.user.roles):
            return await interaction.response.send_message("You do not have the required roles to use this command.", ephemeral=True)

        guild_config = await interaction.client.get_cog("CustomEmbed").config.guild(interaction.guild).all()

        embed = discord.Embed(
            title="Embed from Message",
            description=message.content,
            color=guild_config["default_color"],
            timestamp=datetime.utcnow()
        )
        embed.set_image(url=guild_config["default_image"])

        await interaction.response.send_message(embed=embed)
    except Exception as e:
        logger.error(f"Error creating embed from message: {e}")
        await interaction.response.send_message("An error occurred while creating the embed from the message.", ephemeral=True)

async def setup(bot):
    cog = CustomEmbed(bot)
    bot.add_cog(cog)
    bot.tree.add_command(cog.createembed)
    bot.tree.add_command(cog.setembedconfig)
    bot.tree.add_command(app_commands.ContextMenu(name="Create Embed from Message")(create_embed_from_message))
    await bot.tree.sync()
