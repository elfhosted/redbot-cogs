from .fact import MyRandom


async def setup(bot):
    await bot.add_cog(MyRandom(bot))
