from .custom_embed import CustomEmbed

async def setup(bot):
    cog = CustomEmbed(bot)
    bot.add_cog(cog)
    bot.tree.add_command(cog.createembed)
    bot.tree.add_command(cog.setembedconfig)
    bot.tree.add_command(app_commands.ContextMenu(name="Create Embed from Message")(create_embed_from_message))
    await bot.tree.sync()

async def teardown(bot):
    bot.remove_cog("CustomEmbed")
    bot.tree.remove_command("createembed")
    bot.tree.remove_command("setembedconfig")
    bot.tree.remove_command("Create Embed from Message")
    await bot.tree.sync()
