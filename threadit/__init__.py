from .threadit import RedBotCogThreadit


async def setup(bot):
    await bot.add_cog(RedBotCogThreadit(bot))
