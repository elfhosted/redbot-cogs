import discord
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
    async def move_many_messages(self, ctx, message_ids: str, target_channel: discord.TextChannel):
        if not await self.is_allowed(ctx):
            return await ctx.send("You do not have the required role to use this command.")

        try:
            message_ids = [int(id_str.strip()) for id_str in message_ids.split(",")]
        except ValueError:
            return await ctx.send("Invalid message IDs. Please provide a comma-separated list of message IDs.")

        messages_to_move = []
        for message_id in message_ids:
            try:
                message = await ctx.channel.fetch_message(message_id)
                messages_to_move.append(message)
            except discord.NotFound:
                await ctx.send(f"Message with ID {message_id} not found.")

        for message in messages_to_move:
            await self.move_and_notify(ctx, message, target_channel)

    async def move_and_notify(self, ctx, message, target_channel):
        embed = discord.Embed(description=message.content, color=message.author.color)
        avatar_url = message.author.avatar.url if message.author.avatar else message.author.default_avatar.url
        embed.set_author(name=message.author.display_name, icon_url=avatar_url)
        embed.timestamp = message.created_at
        embed.add_field(name="Original Message", value=f"[Jump to message]({message.jump_url})")

        moved_message = await target_channel.send(embed=embed)

        note = (
            f"{message.author.mention}, your message has been moved to {target_channel.mention} for reference:\n\n"
            f"[Original Message]({moved_message.jump_url})"
        )

        await ctx.send(note)
        await ctx.send(message.author.mention)

async def setup(bot):
    await bot.add_cog(MoveMessage(bot))
