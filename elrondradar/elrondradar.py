import logging
from typing import Optional, Tuple

import aiohttp
import discord
from redbot.core import Config, commands


log = logging.getLogger("red.elrondradar")

DEFAULT_ALLOWED_USER_IDS = [396052375409917952]
DEFAULT_ALLOWED_ROLE_IDS = [
    1198381095553617922,
    1252252269790105721,
    1247172016490938472,
]
SUPPORTED_EMOJIS = {"🚨", "👀", "🛠️", "🛠", "⏳", "✅", "📦", "🔁", "🔄"}


class ElrondRadar(commands.Cog):
    """Bridge staff reactions to Elrond support radar."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=2026051701, force_registration=True)
        self.config.register_global(
            enabled=False,
            endpoint_url="http://openclaw.openclaw:18789/elrond/support-radar/reaction",
            gateway_token="",
            guild_id=396055506072109067,
            allowed_user_ids=DEFAULT_ALLOWED_USER_IDS,
            allowed_role_ids=DEFAULT_ALLOWED_ROLE_IDS,
        )

    def _reactions_intent_state(self) -> str:
        intents = getattr(self.bot, "intents", None)
        if intents is None:
            return "unknown"
        if hasattr(intents, "reactions"):
            return str(getattr(intents, "reactions"))
        return str(getattr(intents, "guild_reactions", "unknown"))

    @commands.group(name="elrondradar")
    @commands.admin_or_permissions(manage_guild=True)
    async def elrondradar(self, ctx):
        """Configure the Elrond support radar bridge."""

    @elrondradar.command(name="enable")
    async def enable(self, ctx):
        """Enable reaction forwarding."""
        await self.config.enabled.set(True)
        await ctx.send("Elrond radar bridge enabled.")

    @elrondradar.command(name="disable")
    async def disable(self, ctx):
        """Disable reaction forwarding."""
        await self.config.enabled.set(False)
        await ctx.send("Elrond radar bridge disabled.")

    @elrondradar.command(name="setendpoint")
    async def setendpoint(self, ctx, endpoint_url: str):
        """Set the Elrond/OpenClaw webhook endpoint URL."""
        await self.config.endpoint_url.set(endpoint_url.strip())
        await ctx.send("Elrond radar endpoint updated.")

    @elrondradar.command(name="settoken")
    async def settoken(self, ctx, gateway_token: str):
        """Set the OpenClaw gateway token used for webhook auth."""
        await self.config.gateway_token.set(gateway_token.strip())
        await ctx.send("Elrond radar gateway token updated.")

    @elrondradar.command(name="status")
    async def status(self, ctx):
        """Show bridge status without revealing the token."""
        cfg = await self.config.all()
        token_state = "set" if cfg.get("gateway_token") else "missing"
        await ctx.send(
            "Elrond radar bridge:\n"
            f"- enabled: {cfg.get('enabled')}\n"
            f"- endpoint: {cfg.get('endpoint_url')}\n"
            f"- guild_id: {cfg.get('guild_id')}\n"
            f"- token: {token_state}\n"
            f"- reactions intent: {self._reactions_intent_state()}\n"
            f"- allowed users: {len(cfg.get('allowed_user_ids') or [])}\n"
            f"- allowed roles: {len(cfg.get('allowed_role_ids') or [])}"
        )

    @elrondradar.command(name="test")
    async def test(self, ctx, channel_id: int, message_id: int, emoji: str = "👀"):
        """Send a synthetic radar event for a specific Discord message."""
        if ctx.guild is None:
            await ctx.send("Run this in the configured guild.")
            return
        if ctx.guild.id != await self.config.guild_id():
            await ctx.send("This server is not the configured Elrond radar guild.")
            return
        if emoji not in SUPPORTED_EMOJIS:
            await ctx.send(f"Unsupported radar emoji: {emoji}")
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await ctx.guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                await ctx.send(f"Could not fetch channel {channel_id}: {type(exc).__name__}")
                return
        if not hasattr(channel, "fetch_message"):
            await ctx.send(f"Channel {channel_id} cannot fetch messages.")
            return

        try:
            message = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
            await ctx.send(f"Could not fetch message {message_id}: {type(exc).__name__}")
            return

        data = self._build_payload(
            action="added",
            guild_id=ctx.guild.id,
            channel_id=channel_id,
            message_id=message_id,
            emoji=emoji,
            staff_id=ctx.author.id,
            staff_display_name=getattr(ctx.author, "display_name", str(ctx.author)),
            message=message,
        )
        status, body = await self._post_to_elrond(data)
        if status is None:
            await ctx.send("Elrond radar test failed: endpoint or token is not configured.")
        elif status >= 300:
            await ctx.send(f"Elrond radar test failed: HTTP {status} {body[:300]}")
        else:
            await ctx.send(f"Elrond radar test accepted: HTTP {status}")

    async def _is_allowed_staff(self, guild: discord.Guild, user_id: int, member: Optional[discord.Member]) -> bool:
        allowed_user_ids = set(await self.config.allowed_user_ids())
        if user_id in allowed_user_ids:
            return True

        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return False

        allowed_role_ids = set(await self.config.allowed_role_ids())
        return any(role.id in allowed_role_ids for role in getattr(member, "roles", []))

    async def _fetch_message(self, payload: discord.RawReactionActionEvent) -> Optional[discord.Message]:
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
            if guild is not None:
                try:
                    channel = await guild.fetch_channel(payload.channel_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    return None
        if channel is None or not hasattr(channel, "fetch_message"):
            return None
        try:
            return await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    async def _post_to_elrond(self, data: dict) -> Tuple[Optional[int], str]:
        endpoint_url = (await self.config.endpoint_url()).strip()
        gateway_token = (await self.config.gateway_token()).strip()
        if not endpoint_url or not gateway_token:
            log.warning("Elrond radar endpoint or token is not configured")
            return None, "endpoint or token is not configured"

        headers = {
            "Authorization": f"Bearer {gateway_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint_url, json=data, headers=headers, timeout=10) as response:
                text = await response.text()
                if response.status >= 300:
                    log.warning("Elrond radar webhook failed: HTTP %s %s", response.status, text[:500])
                else:
                    log.info("Elrond radar webhook accepted: %s", text[:500])
                return response.status, text

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction(payload, action="added")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction(payload, action="removed")

    async def _handle_reaction(self, payload: discord.RawReactionActionEvent, action: str):
        if not await self.config.enabled():
            return
        if payload.guild_id is None:
            return
        if payload.guild_id != await self.config.guild_id():
            return

        emoji = str(payload.emoji)
        if emoji not in SUPPORTED_EMOJIS:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        member = payload.member if isinstance(payload.member, discord.Member) else None
        if not await self._is_allowed_staff(guild, payload.user_id, member):
            return

        message = await self._fetch_message(payload)
        data = self._build_payload(
            action=action,
            guild_id=payload.guild_id,
            channel_id=payload.channel_id,
            message_id=payload.message_id,
            emoji=emoji,
            staff_id=payload.user_id,
            staff_display_name=member.display_name if member is not None else str(payload.user_id),
            message=message,
        )
        log.info(
            "Elrond radar reaction accepted locally: action=%s emoji=%s channel=%s message=%s user=%s",
            action,
            emoji,
            payload.channel_id,
            payload.message_id,
            payload.user_id,
        )
        await self._post_to_elrond(data)

    def _build_payload(
        self,
        action: str,
        guild_id: int,
        channel_id: int,
        message_id: int,
        emoji: str,
        staff_id: int,
        staff_display_name: str,
        message: Optional[discord.Message],
    ) -> dict:
        channel = message.channel if message is not None else self.bot.get_channel(channel_id)
        channel_name = getattr(channel, "name", str(channel_id))
        message_author = message.author if message is not None else None
        jump_url = (
            message.jump_url
            if message is not None
            else f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
        )
        return {
            "action": action,
            "guild_id": str(guild_id),
            "channel_id": str(channel_id),
            "channel_name": channel_name,
            "message_id": str(message_id),
            "message_url": jump_url,
            "message_author_id": str(message_author.id) if message_author else "",
            "message_author_name": str(message_author) if message_author else "",
            "message_content": message.content if message is not None else "",
            "emoji": emoji,
            "staff_discord_id": str(staff_id),
            "staff_display_name": staff_display_name,
        }
