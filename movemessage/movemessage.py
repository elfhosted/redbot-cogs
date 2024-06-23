import discord
from redbot.core import commands
import re

# List of allowed role IDs
ALLOWED_ROLE_IDS = [1198381095553617922, 1252252269790105721]

class MoveMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_allowed(self, ctx):
        return any(role.id in ALLOWED_ROLE_IDS for role in ctx.author.roles)

    def extract_message_id(self, input_str):
        url_match = re.match(r'https:\/\/discord\.com\/channels\/\d+\/\d+\/(\d+)', input_str)
        if url_match:
            return int(url_match.group(1))
        elif re.match(r'^\d+$', input_str):
            return int(input_str)
        else:
            return None

    @commands.command(name="move")
    async def move_message(self, ctx, input_str: str, target_channel: discord.TextChannel):
        if not await self.is_allowed(ctx):
            return await ctx.send("You do not have the required role to use this command.")

        message_id = self.extract_message_id(input_str)

        if message_id is None:
            return await ctx.send("Invalid input. Please provide a valid message ID or URL.")

        try:
            message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            return await ctx.send("Message not found.")
        except discord.Forbidden:
            return await ctx.send("I do not have permission to access this message.")
        except discord.HTTPException as e:
            return await ctx.send(f"An error occurred while fetching the message: {e}")

        await self.move_and_notify(ctx, message, target_channel)

    @commands.command(name="movemany")
    async def move_many_messages(self, ctx, input_str: str, target_channel: discord.TextChannel):
        if not await self.is_allowed(ctx):
            return await ctx.send("You do not have the required role to use this command.")

        message_ids = self.extract_message_ids(input_str)

        if not message_ids:
            return await ctx.send("Invalid input. Please provide valid message IDs or URLs.")

        messages_to_move = []
        for message_id in message_ids:
            try:
                message = await ctx.channel.fetch_message(message_id)
                messages_to_move.append(message)
            except discord.NotFound:
                await ctx.send(f"Message with ID {message_id} not found.")
            except discord.Forbidden:
                await ctx.send(f"I do not have permission to access message with ID {message_id}.")
            except discord.HTTPException as e:
                await ctx.send(f"An error occurred while fetching the message with ID {message_id}: {e}")

        for message in messages_to_move:
            await self.move_and_notify(ctx, message, target_channel)

    def extract_message_ids(self, input_str):
        message_ids = []
        urls = re.findall(r'https:\/\/discord\.com\/channels\/\d+\/\d+\/(\d+)', input_str)
        ids = input_str.split(",")
        for id_str in ids:
            id_str = id_str.strip()
            if re.match(r'^\d+$', id_str):
                message_ids.append(int(id_str))
        message_ids.extend([int(url) for url in urls])
        return list(set(message_ids))  # Remove duplicates

    @commands.command(name="movefromuser")
    async def move_messages_from_user(self, ctx, user: discord.Member, num_messages: int, target_channel: discord.TextChannel):
        if not await self.is_allowed(ctx):
            return await ctx.send("You do not have the required role to use this command.")

        def check(msg):
            return msg.author == user

        messages_to_move = []
        async for message in ctx.channel.history(limit=200):
            if check(message):
                messages_to_move.append(message)
            if len(messages_to_move) >= num_messages:
                break

        if not messages_to_move:
            return await ctx.send("No messages found from the specified user.")
        elif len(messages_to_move) < num_messages:
            await ctx.send(f"Only found {len(messages_to_move)} messages from {user.display_name}.")

        for message in messages_to_move:
            await self.move_and_notify(ctx, message, target_channel)

    async def move_and_notify(self, ctx, message, target_channel):
        embed = discord.Embed(description=message.content, color=message.author.color)
        avatar_url = message.author.avatar.url if message.author.avatar else message.author.default_avatar.url
        embed.set_author(name=message.author.display_name, icon_url=avatar_url)
        embed.timestamp = message.created_at
        embed.add_field(name="Original Message", value=f"[Jump to message]({message.jump_url})")

        # Include images if present
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)

        try:
            moved_message = await target_channel.send(embed=embed)
        except discord.HTTPException as e:
            return await ctx.send(f"An error occurred while moving the message: {e}")

        note_embed = discord.Embed(
            description=f"Your message has been moved to {target_channel.mention} for reference:\n\n[Original Message]({moved_message.jump_url})",
            color=discord.Color.red()
        )
        note_embed.set_author(name=message.author.display_name, icon_url=avatar_url)

        try:
            await ctx.send(content=message.author.mention, embed=note_embed)
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred while notifying the user: {e}")

async def setup(bot):
    await bot.add_cog(MoveMessage(bot))
