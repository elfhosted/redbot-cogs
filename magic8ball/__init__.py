from .magic8ball import My8ball


async def setup(bot):
    await bot.add_cog(My8ball(bot))
