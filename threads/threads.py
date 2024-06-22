import discord
import asyncio
import re
import logging
import tempfile
from datetime import datetime
from redbot.core import commands, app_commands

mylogger = logging.getLogger('threads')
mylogger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
mylogger.addHandler(handler)

class PrivateSupportReasonModal(discord.ui.Modal, title="Request Private Support"):
    reason = discord.ui.TextInput(label="Reason for requesting private support", style=discord.TextStyle.paragraph)

    def __init__(self, cog, interaction, *args, **kwargs):
        self.cog = cog
        self.interaction = interaction
        super().__init__(*args, **kwargs)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Private Support Request",
            description=f"{self.interaction.user.mention} is requesting private support for the following reason:\n\n"
                        f"{self.reason.value}\n\n"
                        "__**Notice: **__*Private mode bypasses community input, and is intended for the communication of sensitive details (credentials, tokens, etc), "
                        "and not as a path of escalation. As such, private mode will likely result in a slower response time*",
            color=0x437820
        )

        allowed_mentions = discord.AllowedMentions(roles=[discord.Object(id=self.cog.elf_venger)])

        await self.interaction.channel.send(content=f"<@&{self.cog.elf_venger}>", embed=embed, allowed_mentions=allowed_mentions)
        await self.interaction.response.send_message("Your request for private support has been sent.", ephemeral=True)
        await self.interaction.channel.send(view=PrivateRequestApprovalView(cog=self.cog))


class PrivateRequestApprovalView(discord.ui.View):
    def __init__(self, cog, *args, **kwargs):
        self.cog = cog
        super().__init__(*args, **kwargs)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, emoji="✅", custom_id="approve_request")
    async def approve_request(self, interaction: discord.Interaction, button: discord.ui.Button, **kwargs):
        member = interaction.guild.get_member(interaction.user.id)
        if any(role.id == self.cog.elf_venger for role in member.roles):
            await self.cog._make_private(interaction)
        else:
            await interaction.response.send_message("You don't have permission to use this button.", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, emoji="❌", custom_id="deny_request")
    async def deny_request(self, interaction: discord.Interaction, button: discord.ui.Button, **kwargs):
        member = interaction.guild.get_member(interaction.user.id)
        if any(role.id == self.cog.elf_venger for role in member.roles):
            embed = discord.Embed(
                title="Private Support Request Denied",
                description="Your request for private support has been denied. Please continue the conversation in this thread.",
                color=0xff0000
            )
            await interaction.channel.send(embed=embed)
            await interaction.response.send_message("You have denied the request for private support.", ephemeral=True)
        else:
            await interaction.response.send_message("You don't have permission to use this button.", ephemeral=True)


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
        member = interaction.guild.get_member(interaction.user.id)
        mylogger.info(f"Private button pressed by {interaction.user.name} (ID: {interaction.user.id})")

        if any(role.id == self.cog.elf_venger for role in member.roles):
            await self.cog._make_private(interaction)
        else:
            # Show a modal to get the reason for private support
            await interaction.response.send_modal(PrivateSupportReasonModal(cog=self.cog, interaction=interaction))



class Threads(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_name = bot.user.name
        self.bot_uid = bot.user.id
        self.setup_role_logic()

    def setup_role_logic(self):
        self.role1 = None
        self.elf_venger = None
        self.sponsor = None
        self.elf_friends = None
        self.public_forum_channel = None
        self.ticket_thread_channel = None
        self.private_ticket_transcripts = None
        self.private_ticket_notify_channel = None
        self.ticket_support = None
        self.elf_trainee_id = None

        if self.bot.user.id == 1250781032756674641:  # Sparky
            self.role1 = 1252431218025431041  # Test Priority Support
            self.elf_venger = 1252252269790105721  # Test-Elf-Venger
            self.sponsor = 1232124371901087764  # Test Sponsor
            self.elf_friends = 1253177629645865083  # #general
            self.public_forum_channel = 1252251752397537291  # #test-elf-support
            self.ticket_thread_channel = 1253177629645865083  # #general
            self.private_ticket_transcripts = 1253171050217476106  #
            self.private_ticket_notify_channel = 1253214649592315955
            self.elf_trainee_id = 720195752650997771
        elif self.bot.user.id == 1252847131476230194:  # Sparky Jr
            self.role1 = 1252431218025431041  # Test Priority Support
            self.elf_venger = 1252252269790105721  # Test-Elf-Venger
            self.sponsor = 1232124371901087764  # Test Sponsor
            self.elf_friends = 1253177629645865083  # #general
            self.public_forum_channel = 1252251752397537291  # #test-elf-support
            self.ticket_thread_channel = 1253177629645865083  # #general
            self.private_ticket_transcripts = 1253171050217476106  #
            self.private_ticket_notify_channel = 1253214649592315955
            self.elf_trainee_id = 720195752650997771
        elif self.bot.user.id == 1250431337156837428:  # Spanky
            self.role1 = 1198385945049825322  # Elf Trainees
            self.elf_venger = 1198381095553617922  # ElfVenger
            self.sponsor = 862041125706268702  # Sponsor - not used
            self.elf_friends = 1118645576884572303  # #elf-friends
            self.public_forum_channel = 1245513340176961606  # #elf-support
            self.ticket_thread_channel = 1253543483868971151  # #private-tickets
            self.private_ticket_transcripts = 1253542587613188216  # #elf-venger-transcripts
            self.private_ticket_notify_channel = 1253531682557001810  # #elf-venger-tix
            self.elf_trainee_id = 1198385945049825322 # Elf Trainee Role

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        if thread.parent_id != self.public_forum_channel:
            return

        author_name = f"{thread.owner.name}#{thread.owner.discriminator}" if thread.owner else "Unknown"
        guild_name = thread.guild.name if thread.guild else "Direct Message"
        channel_name = thread.parent.name if isinstance(thread.parent, discord.TextChannel) else "Direct Message"
        
        mylogger.info(f"Threads invoked by {author_name} in {guild_name}/{channel_name} (ID: {thread.guild.id if thread.guild else 'N/A'}/{thread.parent.id if thread.parent else 'N/A'})")
        mylogger.info(f"Processing message: {thread.id}")
        role1 = thread.guild.get_role(self.role1)
        elfvenger = thread.guild.get_role(self.elf_venger)

        if not role1:
            mylogger.error(f"role1: {self.role1} is missing. Someone may have removed the Test Priority Support role. Aborting now...")
            return

        if not elfvenger:
            mylogger.error(f"elfvenger: {self.elf_venger} is missing. Someone may have removed the Test Support role. Aborting now...")
            return
        
        bot_role = elfvenger

        await asyncio.sleep(2)
        thread_owner = thread.owner
        tags = []

        initial_message_content = str(thread)
        match = re.search(r'✋┆(.+)', thread.name)
        username = match.group(1) if match else thread_owner.name

        user = discord.utils.get(thread.guild.members, name=username)

        initial_mention = None
        user_id = None
        user_roles = []
        if user is not None:
            initial_mention = f"Welcome {user.mention}!\n\n"
            user_id = user.id
            user_roles = user.roles
        else:
            initial_mention = f"Welcome {thread_owner.mention}!\n\n"
            user_id = thread_owner.id
            user_roles = thread_owner.roles

        if hasattr(thread.parent, 'available_tags'):
            for tag in thread.parent.available_tags:
                if tag.name.lower() == "open":
                    tags.append(tag)
            try:
                await thread.edit(name=f"✋┆{username}", applied_tags=tags)
            except discord.Forbidden:
                mylogger.error("Missing permissions to edit thread tags.")

        try:
            welcome_embed = discord.Embed(
                title="Welcome to the Support Thread!",
                description=(
                    f"{initial_mention}This thread is primarily for community support from your fellow elves, "
                    f"but the <@&{self.elf_venger}>s have been pinged and may assist when they are available.\n\n"
                    f"Please ensure you've reviewed the troubleshooting guide - this is a requirement for subsequent support in this thread. "
                    f"Type `/private` or press the button below if you want to switch this topic to private mode."
                ),
                color=0x437820
            )
            welcome_embed.set_thumbnail(url="https://elfhosted.com/images/logo-green-text.jpg")
            await thread.send(embed=welcome_embed, view=Buttons(self, bot_role.id, user_id))

            close_embed = discord.Embed(
                title="Close Ticket",
                description="You can press the \"Close Post\" button above or type `/close` at any time to close this post.",
                color=0x437820
            )
            message = await thread.send(embed=close_embed)
            await thread.send(
                content=f"<@&{self.elf_venger}> <@&{self.elf_trainee_id}>",
                allowed_mentions=discord.AllowedMentions(roles=[thread.guild.get_role(self.elf_venger), thread.guild.get_role(self.elf_trainee_id)])
            )

            try:
                await message.pin(reason="Makes it easier to close the post.")
            except discord.Forbidden:
                mylogger.error("Missing permissions to pin messages.")
        except discord.Forbidden:
            mylogger.error("Missing permissions to send messages in the thread.")

    @app_commands.command(name="close")
    async def close(self, interaction: discord.Interaction):
        elfvenger = interaction.guild.get_role(self.elf_venger)
        mylogger.info(f"close command invoked by {interaction.user.name} with roles: {[role.id for role in interaction.user.roles]}")
        if elfvenger not in interaction.user.roles:
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

            match = re.search(r'✋┆(.+)', channel.name)
            username = match.group(1) if match else channel_owner.name
            new_thread_name = f"👍┆{username}"

            user_that_needed_help_id = None

            if username != "U_n_k_n_o_w_n":
                user_obj = discord.utils.get(channel.guild.members, name=username)
                if user_obj:
                    user_that_needed_help_id = user_obj.id

            if channel.parent and (channel.parent.id == self.public_forum_channel or channel.parent.id == self.ticket_thread_channel):
                if member is None:
                    mylogger.error("Member information could not be found.")
                    await send(f"Sorry, I couldn't find your member information. Please try again later.", ephemeral=True)
                    return

                if member.id == channel.owner_id or member.guild_permissions.manage_threads or user_that_needed_help_id == member.id or self.elf_venger in [role.id for role in member.roles]:
                    try:
                        close_embed = discord.Embed(
                            title="Ticket Closed",
                            description=(
                                f"This post has been marked as Resolved and has now been closed.\n\n"
                                f"You cannot reopen this thread - you must create a new one or ask an ElfVenger to reopen it in <#{self.elf_friends}>."
                            ),
                            color=0xff0000
                        )
                        await send(embed=close_embed)

                        tags = [tag for tag in channel.parent.available_tags if tag.name.lower() == "closed"]

                        # Remove all participants from the thread
                        members = await channel.fetch_members()
                        for thread_member in members:
                            await channel.remove_user(thread_member)

                        # Archive and lock the thread
                        await channel.edit(name=new_thread_name, locked=True, archived=True, applied_tags=tags)
                    except Exception as e:
                        mylogger.exception("An error occurred while closing the thread", exc_info=e)
                        await send(f"An unexpected error occurred. Please try again later. {e}", ephemeral=True)
                else:
                    await send(
                        f"Hello {channel_owner.mention}, a user has suggested that this thread has been resolved and can be closed."
                        f"\n\nPlease confirm that you are happy to close this thread by typing `/close` or by pressing the Close Post button which is pinned to this thread."
                    )
            else:
                await send(f"This command can only be used in a thread.", ephemeral=True)
        else:
            await send(f"This command can only be used in a thread.", ephemeral=True)

    @app_commands.command()
    async def private(self, interaction: discord.Interaction):
        elfvenger = interaction.guild.get_role(self.elf_venger)
        ticketrole = interaction.guild.get_role(self.ticket_support)

        mylogger.info(f"private command invoked by {interaction.user.name} with roles: {[role.id for role in interaction.user.roles]}")
        
        if elfvenger not in interaction.user.roles:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return

        await self._make_private(interaction)

    async def _make_private(self, interaction):
        if isinstance(interaction.channel, discord.Thread):
            thread = interaction.channel
            match = re.search(r'✋┆(.+)', thread.name)
            username = match.group(1) if match else thread.owner.name
            new_thread_name = f"🔒┆{username}"

            user = None
            if thread.owner.id == self.bot_uid:
                async for message in thread.history(oldest_first=True, limit=1):
                    if message.content.startswith("@"):
                        user_mention = message.content.split()[0]
                        user_id = int(user_mention.strip('<@!>'))
                        user = interaction.guild.get_member(user_id)
                        break
            else:
                user = thread.owner

            if user is None:
                mylogger.error("User could not be determined.")
                await interaction.response.send_message("Could not determine the user to create the private thread for.", ephemeral=True)
                return

            elfvenger = thread.guild.get_role(self.elf_venger)
            private_channel = self.bot.get_channel(self.ticket_thread_channel)
            if not private_channel:
                mylogger.error("Private channel could not be found.")
                await interaction.response.send_message("Could not find the private channel.", ephemeral=True)
                return

            new_thread = await private_channel.create_thread(name=new_thread_name)
            new_thread_message = await new_thread.send(content=f"Private thread created for {user.mention}\n\nHere is the original thread: [Click Me]({thread.jump_url})")

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

            await thread.send(
                content=f"<@&{self.elf_venger}> <@&{self.elf_trainee_id}>",
                allowed_mentions=discord.AllowedMentions(roles=[thread.guild.get_role(self.elf_venger), thread.guild.get_role(self.elf_trainee_id)])
            )

            allowed_mentions = discord.AllowedMentions(roles=[discord.Object(id=self.elf_venger)])

            await new_thread.send(
                content=f"**Original Message:** {original_content}\n\n**Opened by:** {interaction.user.mention} <@&{self.elf_venger}>",
                allowed_mentions=allowed_mentions
            )

            try:
                notification_channel = self.bot.get_channel(self.private_ticket_notify_channel)
                if not notification_channel:
                    mylogger.error(f"Notification channel with ID {self.private_ticket_notify_channel} not found")
                if not self.elf_venger:
                    mylogger.error("Role ID for elf_venger is not set")
                else:
                    await notification_channel.send(f"", embed=discord.Embed(
                        title="New Private Ticket Opened",
                        description=(
                            f"**Original Title:** {thread.name}\n\n"
                            f"**Content:** {original_content}\n\n"
                            f"**Original Thread:** [View Thread]({thread.jump_url})\n"
                            f"**Private Thread:** [View Thread]({new_thread.jump_url})"
                        ),
                        color=0x437820
                    ), allowed_mentions=allowed_mentions)
            except Exception as e:
                mylogger.error(f"Failed to notify support: {e}")

            embed = discord.Embed(
                title="Thread Moved to Private Channel",
                description=f"The thread has been moved to a private channel: [Click here to view]({new_thread.jump_url})",
                color=0x437820
            )
            await interaction.channel.send(embed=embed)

            try:
                # Remove all participants from the thread except the original member
                members = await interaction.channel.fetch_members()
                for thread_member in members:
                    if thread_member.id != user.id:
                        await interaction.channel.remove_user(thread_member)

                # Archive and lock the thread
                closed_tag = next(tag for tag in interaction.channel.parent.available_tags if tag.name.lower() == "closed")
                await thread.edit(name=new_thread_name, locked=True, archived=True, applied_tags=[closed_tag])
            except StopIteration:
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
        try:
            mylogger.info(f"close_ticket command invoked by {interaction.user.name} with roles: {[role.id for role in interaction.user.roles]}")
            
            # Ensure the command is run in a thread within the specified parent or private channel
            if interaction.channel.type != discord.ChannelType.public_thread and interaction.channel.type != discord.ChannelType.private_thread:
                mylogger.error("Command used in an invalid channel type.")
                await interaction.response.send_message("This command can only be used in ticket threads.", ephemeral=True)
                return

            parent_channel = interaction.channel.parent_id
            if parent_channel != self.ticket_thread_channel:
                mylogger.error("Command used in a thread outside the specified parent or private channel.")
                await interaction.response.send_message("This command can only be used in ticket threads.", ephemeral=True)
                return

            # Extract the user mention from the opening message
            async for message in interaction.channel.history(oldest_first=True, limit=1):
                if message.content.startswith("Private thread created for"):
                    user_mention = message.content.split()[4]
                    user_id = int(user_mention.strip('<@!>'))
                    user = interaction.guild.get_member(user_id)
                    break

            review_message = "Thank you for contacting support! Please leave a review with `/review`."
            await interaction.channel.send(review_message)
            mylogger.info("Review message sent successfully.")

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

            transcript_channel = self.bot.get_channel(self.private_ticket_transcripts)
            if transcript_channel:
                await transcript_channel.send(
                    f"<@&{self.elf_venger}>", embed=discord.Embed(
                        title="Ticket Transcript",
                        description=(
                            f"Transcript for {interaction.channel.name}\n\n"
                            f"**Closed By:** {interaction.user.mention}\n"
                            f"**Closed At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            f"**Participants:** {', '.join([self.bot.get_user(member.id).mention for member in await interaction.channel.fetch_members()])}\n\n"
                            f"**Transcript:** [View Transcript](attachment://{tmp_file_path.split('/')[-1]})"
                        ),
                        color=0x437820
                    ), file=discord.File(tmp_file_path, filename=f"{interaction.channel.name}_transcript.html"),
                    allowed_mentions=discord.AllowedMentions(roles=[interaction.guild.get_role(self.elf_venger)])
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

            embed = discord.Embed(
                title="Ticket Closed",
                description=(
                    f"Your ticket was closed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.\n\n"
                    f"**Transcript:** [View Transcript](attachment://{tmp_file_path.split('/')[-1]})"
                ),
                color=0x437820
            )
            embed.add_field(name="Participants", value=", ".join([self.bot.get_user(member.id).mention for member in await interaction.channel.fetch_members()]), inline=False)
            embed.set_footer(text="Thank you for using our support service!")

            await interaction.channel.send(embed=embed)

            # Remove all participants from the thread except the original member
            members = await interaction.channel.fetch_members()
            for thread_member in members:
                if thread_member.id != user.id:
                    await interaction.channel.remove_user(thread_member)

            await interaction.channel.edit(archived=True, locked=True)

        except Exception as e:
            mylogger.exception("An error occurred in the close_ticket command", exc_info=e)
            try:
                await interaction.response.send_message("An unexpected error occurred. Please try again later.", ephemeral=True)
            except discord.errors.Forbidden:
                mylogger.error("Failed to send error message to user: Missing Access.")


async def setup(bot):
    await bot.add_cog(Threads(bot))
