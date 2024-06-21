from .customembed import CustomEmbed

async def setup(bot):
    cog = CustomEmbed(bot)
    bot.add_cog(cog)
    bot.tree.add_command(cog.createembed)
    bot.tree.add_command(cog.setembedconfig)

async def teardown(bot):
    bot.tree.remove_command("createembed")
    bot.tree.remove_command("setembedconfig")
