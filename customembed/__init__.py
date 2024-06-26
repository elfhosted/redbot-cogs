from .customembed import CustomEmbed

async def setup(bot):
    await bot.add_cog(CustomEmbed(bot))
