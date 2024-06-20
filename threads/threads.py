import discord
import asyncio
import re
import logging
import tempfile 
from redbot.core import commands, app_commands

mylogger = logging.getLogger('threads')
mylogger.setLevel(logging.DEBUG)

class Buttons(discord.ui.View):
    def __init__(self, cog, bot_role_id, user_id, *, timeout=None):
        self.cog = cog
        self.bot_role_id = bot_role_id
        self.user_id = user_id
        super().__init__(timeout=timeout)

    @discord.ui.button(label="Close Post", style=discord.ButtonStyle.red, emoji="🔒", custom_id="Close Post")
    async def gray_button(self, interaction: discord.Interaction, button: discord.ui.Button, **kwargs):
        channel = interaction.channel
        if channel and isinstance(channel, discord.Thread):
            member = interaction.guild.get_member(interaction.user.id)
            mylogger.info(f"Close button pressed by {interaction.user.name} (ID: {interaction.user.id}) with roles: {[role.id for role in member.roles]}")
            mylogger.info(f"Required bot role ID: {self.bot_role_id}")
            if interaction.user.id == self.user_id or any(role.id == self.bot_role_id for role in member.roles):
                await self.cog._close(interaction)
            else:
                await interaction.response.send_message("You don't have permission to use this button.", ephemeral=True)

    @discord.ui.button(label="Private Mode", style=discord.ButtonStyle.green, emoji="🔒", custom_id="Private Mode")
    async def private_button(self, interaction: discord.Interaction, button: discord.ui.Button, **kwargs):
        await self.cog._make_private(interaction)

class Threads(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_name = bot.user.name
        self.bot_uid = bot.user.id
        self.setup_role_logic()

    def setup_role_logic(self):
        self.role1 = None
        self.role2 = None
        self.sponsor = None
        self.general_chat = None
        self.parent_channel_id = None
        self.private_channel_id = None
        self.transcript_channel_id = None
        self.ticket_support = None

        if self.bot.user.id == 1250781032756674641:  # Sparky
            self.role1 = 1252431218025431041  # Test Priority Support
            self.role2 = 1252252269790105721  # Test-Elf-Venger
            self.sponsor = 1232124371901087764  # Test Sponsor
            self.general_chat = 1253177629645865083  # #general
            self.parent_channel_id = 1252251752397537291  # #test-elf-support
            self.private_channel_id = 1253177629645865083  # #general
            self.transcript_channel_id = 1253171050217476106  #
            self.support_notify = 1253214649592315955
            self.ticket_support = 1252252269790105721
        elif self.bot.user.id == 1252847131476230194:  # Sparky Jr
            self.role1 = 1252431218025431041  # Test Priority Support
            self.role2 = 1252252269790105721  # Test-Elf-Venger
            self.sponsor = 1232124371901087764  # Test Sponsor
            self.general_chat = 1253177629645865083  # #general
            self.parent_channel_id = 1252251752397537291  # #test-elf-support
            self.private_channel_id = 1253177629645865083  # #general
            self.transcript_channel_id = 1253171050217476106  #
            self.support_notify = 1253214649592315955
            self.ticket_support = 1252252269790105721
        elif self.bot.user.id == 1250431337156837428:  # Spanky
            self.role1 = 1198385945049825322  # Elf Trainees
            self.role2 = 1198381095553617922  # ElfVenger
            self.sponsor = 862041125706268702  # Sponsor - not used
            self.general_chat = 1118645576884572303  # #elf-friends
            self.parent_channel_id = 1245513340176961606  # #elf-support
            self.private_channel_id = 1118645576884572303  # #elf-friends
            self.transcript_channel_id = 123456789012345678  # not setup
            self.support_notify = 123456789012345678  # not setup
            self.ticket_support = 1118863307084935259

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        if thread.parent_id != self.parent_channel_id:
            return

        author_name = f"{thread.owner.name}#{thread.owner.discriminator}" if thread.owner else "Unknown"
        guild_name = thread.guild.name if thread.guild else "Direct Message"
        channel_name = thread.parent.name if isinstance(thread.parent, discord.TextChannel) else "Direct Message"
        
        mylogger.info(f"Threads invoked by {author_name} in {guild_name}/{channel_name} (ID: {thread.guild.id if thread.guild else 'N/A'}/{thread.parent.id if thread.parent else 'N/A'})")
        mylogger.info(f"Processing message: {thread.id}")
        role1 = thread.guild.get_role(self.role1)
        role2 = thread.guild.get_role(self.role2)

        if not role1:
            mylogger.error(f"role1: {self.role1} is missing. Someone may have removed the Test Priority Support role. Aborting now...")
            return

        if not role2:
            mylogger.error(f"role2: {self.role2} is missing. Someone may have removed the Test Support role. Aborting now...")
            return
        
        bot_role = role2

        await asyncio.sleep(2)
        thread_owner = thread.owner
        tags = []

        initial_message_content = str(thread)
        match = re.search(r'✋ - (.+)', thread.name)
        username = match.group(1) if match else "U_n_k_n_o_w_n"

        user = discord.utils.get(thread.guild.members, name=username)

        initial_mention = None
        user_id = None
        user_roles = []
        if username != "U_n_k_n_o_w_n" and user is not None:
            initial_mention = f"Welcome {user.mention}!\n\n"
            user_id = user.id
            user_roles = user.roles
        else:
            initial_mention = f"Welcome {thread_owner.mention}!\n\n"
            user_id = thread_owner.id
            user_roles = thread_owner.roles

        # Ensure 'available_tags' exists before accessing it
        if hasattr(thread.parent, 'available_tags'):
            for tag in thread.parent.available_tags:
                if tag.name.lower() == "open":
                    tags.append(tag)
            try:
                await thread.edit(applied_tags=tags)
            except discord.Forbidden:
                mylogger.error("Missing permissions to edit thread tags.")

        try:
            await thread.send(
                f"{initial_mention}This thread is primarily for community support from your fellow elves, but the <@&{self.role2}>s have been pinged and may assist when they are available. \n\nPlease ensure you've reviewed the troubleshooting guide - this is a requirement for subsequent support in this thread. Type `/private` or press the button below if you want to switch this topic to private mode.",
                allowed_mentions=discord.AllowedMentions(roles=[role1, role2], users=[user] if user else []), view=Buttons(self, bot_role.id, user_id))
            message = await thread.send(
                "You can press the \"Close Post\" button above or type `/close` at any time to close this post.")
            try:
                await message.pin(reason="Makes it easier to close the post.")
            except discord.Forbidden:
                mylogger.error("Missing permissions to pin messages.")
        except discord.Forbidden:
            mylogger.error("Missing permissions to send messages in the thread.")

    @app_commands.command(name="close")
    async def close(self, interaction: discord.Interaction):
        role2 = interaction.guild.get_role(self.role2)
        mylogger.info(f"close command invoked by {interaction.user.name} with roles: {[role.id for role in interaction.user.roles]}")
        if role2 not in interaction.user.roles:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        await self._close(interaction)

    async def _close(self, ctx_or_interaction):
        if isinstance(ctx_or_interaction, commands.Context):
            channel = ctx_or_interaction.channel
            member = ctx_or_interaction.author
            send = ctx_or_interaction.send
        else:
            channel = ctx_or_interaction.channel
            member = ctx_or_interaction.user
            send = ctx_or_interaction.response.send_message

        if isinstance(channel, discord.Thread):
            channel_owner = channel.owner
            initial_message_content = str(channel)

            mylogger.info(f"initial_message_content: {initial_message_content}")

            match = re.search(r'✋ - (.+)', channel.name)
            username = match.group(1) if match else "U_n_k_n_o_w_n"
            new_thread_name = f"👍 - {username}"

            user_that_needed_help_id = None

            if username and username != "U_n_k_n_o_w_n":
                user_obj = discord.utils.get(channel.guild.members, name=username)
                if user_obj:
                    user_that_needed_help_id = user_obj.id

            mylogger.info(f"channel: {channel}")
            mylogger.info(f"channel_owner: {channel_owner}")
            mylogger.info(f"channel.parent: {channel.parent}")
            mylogger.info(f"channel.parent.id: {channel.parent.id}")
            mylogger.info(f"self.parent_channel_id: {self.parent_channel_id}")
            mylogger.info(f"user_that_needed_help: {username}")
            mylogger.info(f"user_that_needed_help_id: {user_that_needed_help_id}")
            mylogger.info(f"channel.owner_id: {channel.owner_id}")
            if channel.parent and (channel.parent.id == self.parent_channel_id or channel.parent.id == self.private_channel_id):
                mylogger.info(f"member.id: {member.id}")
                mylogger.info(f"member.guild_permissions.manage_threads: {member.guild_permissions.manage_threads}")
                mylogger.info(f"Member roles: {[role.id for role in member.roles]}")
                mylogger.info(f"Role2 ID: {self.role2}")
                if member is None:
                    await send(
                        f"Sorry, I couldn't find your member information. Please try again later.", ephemeral=True)
                    return

                if member.id == channel.owner_id or member.guild_permissions.manage_threads or user_that_needed_help_id == member.id or self.role2 in [role.id for role in member.roles]:
                    mylogger.info(f"User {member.name} has permissions to close the thread directly.")
                    try:
                        await send(
                            f"This post has been marked as Resolved and has now been closed."
                            f"\n\nYou cannot reopen this thread - you must create a new one or ask an ElfVenger to reopen it in <#{self.general_chat}>.",
                            ephemeral=False)
                        tags = [tag for tag in channel.parent.available_tags if tag.name.lower() == "closed"]
                        try:
                            await channel.edit(
                                name=new_thread_name,
                                locked=True,
                                archived=True,
                                applied_tags=tags
                            )
                        except discord.Forbidden:
                            mylogger.error("Missing permissions to edit thread tags.")
                    except Exception as e:
                        mylogger.exception("An error occurred while closing the thread", exc_info=e)
                        await send(
                            f"An unexpected error occurred. Please try again later. {e}", ephemeral=True)
                    except discord.Forbidden:
                        await send(
                            f"I don't have the necessary permissions to close and lock the thread.", ephemeral=True)
                    except discord.HTTPException:
                        await send(
                            f"An error occurred while attempting to close and lock the thread.", ephemeral=True)
                else:
                    mylogger.info(f"User {member.name} does not have the required permissions to close the thread directly.")
                    await send(
                        f"Hello {channel_owner.mention}, a user has suggested that this thread has been resolved and can be closed."
                        f"\n\nPlease confirm that you are happy to close this thread by typing `/close` or by pressing the Close Post button which is pinned to this thread.")
            else:
                await send(f"This command can only be used in a thread.", ephemeral=True)
        else:
            await send(f"This command can only be used in a thread.", ephemeral=True)


    @app_commands.command()
    async def private(self, interaction: discord.Interaction):
        role2 = interaction.guild.get_role(self.role2)
        ticketrole = interaction.guild.get_role(self.ticket_support)
        
        if role2 not in interaction.user.roles:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return

        await self._make_private(interaction)

    async def _make_private(self, interaction):
        if isinstance(interaction.channel, discord.Thread):
            thread = interaction.channel
            match = re.search(r'✋ - (.+)', thread.name)
            username = match.group(1) if match else "U_n_k_n_o_w_n"
            new_thread_name = f"🔒 - {username}"

            if thread.owner.id == self.bot_uid:
                author_name = match.group(1) if match else "Unknown"
                user = discord.utils.get(thread.guild.members, name=author_name)
            else:
                user = thread.owner
                author_name = user.name

            role2 = thread.guild.get_role(self.role2)
            ticketrole = thread.guild.get_role(self.ticket_support)

            private_channel = self.bot.get_channel(self.private_channel_id)
            if not private_channel:
                await interaction.response.send_message("Could not find the private channel.", ephemeral=True)
                return

            new_thread = await private_channel.create_thread(name=new_thread_name)
            new_thread_message = await new_thread.send(content=f"Private thread created for {user.mention if user else 'Unknown User'}\n\nHere is the original thread: {thread.jump_url}")

            original_content = "No original content found."
            if thread.owner.bot:
                async for message in thread.history(oldest_first=True):
                    if message.content.startswith("Content: "):
                        original_content = message.content[len("Content: "):]
                        break
            else:
                async for message in thread.history(oldest_first=True):
                    original_content = message.content
                    break

            await new_thread.send(content=f"Original Message: {original_content}\n\nOpened by {interaction.user.mention} <@&{self.role2}>")

            try:
                notification_channel = self.bot.get_channel(self.support_notify)
                if notification_channel:
                    await notification_channel.send(f"New private ticket opened: {new_thread.jump_url}", allowed_mentions=discord.AllowedMentions(roles=[ticketrole]))
            except Exception as e:
                mylogger.error(f"Failed to notify support: {e}")

            await interaction.channel.send(f"The thread has been moved to a private channel: {new_thread_message.jump_url}")

            try:
                await thread.edit(name=new_thread_name, locked=True, archived=True)
            except discord.Forbidden:
                mylogger.error("Missing permissions to lock and archive the thread.")
                await interaction.response.send_message("I don't have the necessary permissions to lock and archive the thread.", ephemeral=True)
        else:
            await interaction.response.send_message("This command can only be used in a thread.", ephemeral=True)

    @app_commands.command(name="close-ticket")
    @commands.has_permissions(manage_channels=True)
    async def close_ticket(self, interaction: discord.Interaction):
        """Close a ticket, send a review message, and create a transcript."""
        
        # Ensure the command is run in a thread within the specified parent or private channel
        if interaction.channel.type != discord.ChannelType.public_thread and interaction.channel.type != discord.ChannelType.private_thread:
            await interaction.response.send_message("This command can only be used in ticket threads.", ephemeral=True)
            return

        parent_channel = interaction.channel.parent_id
        if parent_channel != self.private_channel_id:
            await interaction.response.send_message("This command can only be used in ticket threads.", ephemeral=True)
            return

        # Send a review message
        review_message = "Thank you for contacting support! Please leave a review with `/review`."
        await interaction.channel.send(review_message)

        # Create a transcript
        transcript = []
        async for message in interaction.channel.history(limit=None, oldest_first=True):
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            transcript.append(f"<div class='message'><div class='message-author'>{message.author.name}</div><div class='message-timestamp'>{timestamp}</div><div class='message-content'>{message.content}</div></div>")
        transcript_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Transcript</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    background-color: #f4f4f4;
                }}
                .transcript-container {{
                    background-color: #fff;
                    border-radius: 5px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                    padding: 20px;
                }}
                .message {{
                    border-bottom: 1px solid #ddd;
                    padding: 10px 0;
                }}
                .message:last-child {{
                    border-bottom: none;
                }}
                .message-author {{
                    font-weight: bold;
                }}
                .message-timestamp {{
                    color: #888;
                    font-size: 0.9em;
                }}
                .message-content {{
                    margin-top: 5px;
                }}
            </style>
        </head>
        <body>
            <div class="transcript-container">
                {''.join(transcript)}
            </div>
        </body>
        </html>
        """

    
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html') as tmp_file:
            tmp_file.write(transcript_html)
            tmp_file_path = tmp_file.name

        transcript_channel = self.bot.get_channel(self.transcript_channel_id)
        if transcript_channel:
            await transcript_channel.send(
                f"Transcript for {interaction.channel.name}",
                file=discord.File(tmp_file_path, filename=f"{interaction.channel.name}_transcript.html")
            )

        try:
            user_mention = re.search(r"<@!?(\d+)>", interaction.channel.name)
            if user_mention:
                user_id = int(user_mention.group(1))
                user = interaction.guild.get_member(user_id)
                if user:
                    await user.send(
                        f"Here is the transcript for your ticket: {interaction.channel.name}",
                        file=discord.File(tmp_file_path, filename=f"{interaction.channel.name}_transcript.html")
                    )
        except Exception as e:
            mylogger.error(f"Failed to send transcript to user: {e}")

        await interaction.channel.edit(archived=True, locked=True)
        await interaction.channel.send("This ticket has been closed and the channel has been archived.")

async def setup(bot):
    await bot.add_cog(Threads(bot))
