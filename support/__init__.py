from .support import RedBotCogSupport


async def setup(bot):
    await bot.add_cog(RedBotCogSupport(bot))
