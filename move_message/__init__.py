from .move_message import MoveMessage

async def setup(bot):
    await bot.add_cog(MoveMessage(bot))