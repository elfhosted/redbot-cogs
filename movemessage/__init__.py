from .movemessage import MoveMessage

async def setup(bot):
    await bot.add_cog(MoveMessage(bot))