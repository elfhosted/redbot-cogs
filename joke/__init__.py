from .joke import MyJoke


async def setup(bot):
    await bot.add_cog(MyJoke(bot))
