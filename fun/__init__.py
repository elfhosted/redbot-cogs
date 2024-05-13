from .fun import RedBotCogFun


async def setup(bot):
    await bot.add_cog(RedBotCogFun(bot))
