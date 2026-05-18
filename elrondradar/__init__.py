from .elrondradar import ElrondRadar


async def setup(bot):
    cog = ElrondRadar(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.usernote_slash)
    bot.tree.add_command(cog.usernote_add_slash)
    bot.tree.add_command(cog.usernote_list_slash)
    bot.tree.add_command(cog.usernote_delete_slash)
