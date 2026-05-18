import logging

import discord

from .elrondradar import ElrondRadar


log = logging.getLogger("red.elrondradar")
ELFHOSTED_GUILD_ID = 396055506072109067


async def setup(bot):
    await bot.add_cog(ElrondRadar(bot))
    try:
        await bot.tree.sync(guild=discord.Object(id=ELFHOSTED_GUILD_ID))
    except Exception:
        log.exception("Failed to sync Elrond radar guild slash commands")
