from .threads import Threads


async def setup(bot):
    await bot.add_cog(Threads(bot))