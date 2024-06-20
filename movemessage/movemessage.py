import discord
from discord.ext import commands
from redbot.core import commands

# List of allowed role IDs
ALLOWED_ROLE_IDS = [1198381095553617922, 1252252269790105721]

class MoveMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_allowed(self, ctx):
        return any(role.id in ALLOWED_ROLE_IDS for role in ctx.author.roles)

    @commands.command(name="move")
    async def move_message(self, ctx, message_id: int, target_channel: discord.TextChannel):
        if not await self.is_allowed(ctx):
            return await ctx.send("You do not have the required role to use this command.")

        try:
            message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            return await ctx.send("Message not found.")

        await self.move_and_notify(ctx, message, target_channel)

    @commands.command(name="movemany")
    async def move_many_messages(self, ctx, start_message_id: int, end_message_id: int, target_channel: discord.TextChannel):
        if not await self.is_allowed(ctx):
            return await ctx.send("You do not have the required role to use this command.")

        messages_to_move = []
        async for message in ctx.channel.history(after=discord.Object(id=start_message_id), before=discord.Object(id=end_message_id), limit=None):
            messages_to_move.append(message)
        messages_to_move = sorted(messages_to_move, key=lambda m: m.id)

        for message in messages_to_move:
            await self.move_and_notify(ctx, message, target_channel)

    async def move_and_notify(self, ctx, message, target_channel):
        embed = discord.Embed(description=message.content, color=message.author.color)
        embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url)
        embed.timestamp = message.created_at
        embed.add_field(name="Original Message", value=f"[Jump to message]({message.jump_url})")

        moved_message = await target_channel.send(embed=embed)

        note = f"@{message.author.display_name}, your message has been moved here for reference:\n\n{message.content}\n\n[Original Message]({moved_message.jump_url})"
        await ctx.send(note)

        await message.delete()

async def setup(bot):
    await bot.add_cog(MoveMessage(bot))
