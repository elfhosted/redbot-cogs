from .elrondradar import ElrondRadar


async def setup(bot):
    await bot.add_cog(ElrondRadar(bot))
