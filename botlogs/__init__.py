from .botlogs import BotLogs


async def setup(bot):
    await bot.add_cog(BotLogs(bot))