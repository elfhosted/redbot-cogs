from .validate import RedBotCogValidate


async def setup(bot):
    await bot.add_cog(RedBotCogValidate(bot))
