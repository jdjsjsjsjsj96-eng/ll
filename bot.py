import discord
from discord import app_commands
import os
import json
import time
import asyncio
from typing import Optional
from api import start_api_thread

# ─────────────────────────────────────────────
#  ENV CONFIG
# ─────────────────────────────────────────────

TOKEN             = os.environ["TOKEN"]
OWNER_ROLE_NAME   = os.environ.get("OWNER_ROLE", "Owner")
MOD_ROLE_NAME     = os.environ.get("MOD_ROLE", "Moderator")
WEBHOOK_URL       = os.environ.get("WEBHOOK_URL", "")

# ─────────────────────────────────────────────
#  DATA
# ─────────────────────────────────────────────

DATA_FILE = "minion_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "bans": {},
        "kicks": {},
        "warnings": {},
        "nicknames": {},
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ─────────────────────────────────────────────
#  WEBHOOK
# ─────────────────────────────────────────────

async def send_webhook(content: str = "", embeds: list = None):
    if not WEBHOOK_URL:
        return
    try:
        import aiohttp
        payload: dict = {}
        if content:
            payload["content"] = content
        if embeds:
            payload["embeds"] = embeds
        if not payload:
            return
        async with aiohttp.ClientSession() as session:
            await session.post(WEBHOOK_URL, json=payload, timeout=aiohttp.ClientTimeout(total=5))
    except Exception:
        pass

# ─────────────────────────────────────────────
#  ROLE CHECKS
# ─────────────────────────────────────────────

def has_owner_role(interaction: discord.Interaction) -> bool:
    return any(r.name == OWNER_ROLE_NAME for r in interaction.user.roles)

def has_mod_role(interaction: discord.Interaction) -> bool:
    return any(r.name in (OWNER_ROLE_NAME, MOD_ROLE_NAME) for r in interaction.user.roles)

async def deny(interaction: discord.Interaction, required: str = "Owner"):
    await interaction.response.send_message(
        f"❌ You need the **{required}** role to use this command.",
        ephemeral=True
    )

# ─────────────────────────────────────────────
#  CLIENT
# ─────────────────────────────────────────────

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    await tree.sync()
    print(f"Minion is online as {client.user}")
    start_api_thread()

# ─────────────────────────────────────────────
#  OWNER ONLY — BAN
# ─────────────────────────────────────────────

@tree.command(name="ban", description="Ban a member from the server")
@app_commands.describe(user="The member to ban", reason="Reason for the ban", delete_days="Days of messages to delete (0-7)")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided", delete_days: int = 0):
    if not has_owner_role(interaction):
        return await deny(interaction, "Owner")

    if user.top_role >= interaction.user.top_role:
        await interaction.response.send_message("❌ You can't ban someone with an equal or higher role.", ephemeral=True)
        return

    delete_days = max(0, min(7, delete_days))

    # DM the user before banning
    try:
        dm_embed = discord.Embed(
            title=f"🔨 You have been banned from {interaction.guild.name}",
            description=f"**Reason:** {reason}",
            color=0xFF2222
        )
        dm_embed.set_footer(text="Minion Bot")
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        pass

    await interaction.guild.ban(user, reason=reason, delete_message_days=delete_days)

    # Log it
    data = load_data()
    data.setdefault("bans", {})[str(user.id)] = {
        "reason": reason,
        "by": str(interaction.user.id),
        "at": int(time.time()),
    }
    save_data(data)

    embed = discord.Embed(
        title="🔨 Member Banned",
        description=f"{user.mention} has been banned.",
        color=0xFF2222
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Banned by", value=interaction.user.mention, inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text="Minion Bot")
    await interaction.response.send_message(embed=embed)

    asyncio.create_task(send_webhook(embeds=[{
        "title": "🔨 Member Banned",
        "color": 0xFF2222,
        "fields": [
            {"name": "User", "value": f"{user} ({user.id})", "inline": True},
            {"name": "Banned by", "value": str(interaction.user), "inline": True},
            {"name": "Reason", "value": reason, "inline": False},
        ],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }]))

# ─────────────────────────────────────────────
#  OWNER ONLY — UNBAN
# ─────────────────────────────────────────────

@tree.command(name="unban", description="Unban a user by their ID")
@app_commands.describe(user_id="The user ID to unban", reason="Reason for unban")
async def unban(interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
    if not has_owner_role(interaction):
        return await deny(interaction, "Owner")

    try:
        uid = int(user_id)
    except ValueError:
        await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)
        return

    try:
        user = await client.fetch_user(uid)
        await interaction.guild.unban(user, reason=reason)
        embed = discord.Embed(
            title="✅ Member Unbanned",
            description=f"{user.mention} has been unbanned.",
            color=0x00CC66
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Unbanned by", value=interaction.user.mention, inline=True)
        embed.set_footer(text="Minion Bot")
        await interaction.response.send_message(embed=embed)
    except discord.NotFound:
        await interaction.response.send_message("❌ That user is not banned.", ephemeral=True)

# ─────────────────────────────────────────────
#  MOD + OWNER — KICK
# ─────────────────────────────────────────────

@tree.command(name="kick", description="Kick a member from the server")
@app_commands.describe(user="The member to kick", reason="Reason for the kick")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    if not has_mod_role(interaction):
        return await deny(interaction, "Moderator or Owner")

    if user.top_role >= interaction.user.top_role:
        await interaction.response.send_message("❌ You can't kick someone with an equal or higher role.", ephemeral=True)
        return

    try:
        dm_embed = discord.Embed(
            title=f"👢 You have been kicked from {interaction.guild.name}",
            description=f"**Reason:** {reason}",
            color=0xFF8800
        )
        dm_embed.set_footer(text="Minion Bot")
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        pass

    await interaction.guild.kick(user, reason=reason)

    data = load_data()
    data.setdefault("kicks", {}).setdefault(str(user.id), []).append({
        "reason": reason,
        "by": str(interaction.user.id),
        "at": int(time.time()),
    })
    save_data(data)

    embed = discord.Embed(
        title="👢 Member Kicked",
        description=f"{user.mention} has been kicked.",
        color=0xFF8800
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Kicked by", value=interaction.user.mention, inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text="Minion Bot")
    await interaction.response.send_message(embed=embed)

    asyncio.create_task(send_webhook(embeds=[{
        "title": "👢 Member Kicked",
        "color": 0xFF8800,
        "fields": [
            {"name": "User", "value": f"{user} ({user.id})", "inline": True},
            {"name": "Kicked by", "value": str(interaction.user), "inline": True},
            {"name": "Reason", "value": reason, "inline": False},
        ],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }]))

# ─────────────────────────────────────────────
#  MOD + OWNER — TIMEOUT / MUTE
# ─────────────────────────────────────────────

@tree.command(name="timeout", description="Timeout (mute) a member for a duration")
@app_commands.describe(user="The member to timeout", minutes="Duration in minutes", reason="Reason")
async def timeout_cmd(interaction: discord.Interaction, user: discord.Member, minutes: int, reason: str = "No reason provided"):
    if not has_mod_role(interaction):
        return await deny(interaction, "Moderator or Owner")

    until = discord.utils.utcnow() + discord.timedelta(minutes=minutes)
    await user.timeout(until, reason=reason)

    embed = discord.Embed(
        title="🔇 Member Timed Out",
        description=f"{user.mention} has been timed out for **{minutes} minute(s)**.",
        color=0xFFAA00
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="By", value=interaction.user.mention, inline=True)
    embed.set_footer(text="Minion Bot")
    await interaction.response.send_message(embed=embed)

@tree.command(name="untimeout", description="Remove a timeout from a member")
@app_commands.describe(user="The member to untimeout")
async def untimeout_cmd(interaction: discord.Interaction, user: discord.Member):
    if not has_mod_role(interaction):
        return await deny(interaction, "Moderator or Owner")

    await user.timeout(None)
    embed = discord.Embed(
        title="🔊 Timeout Removed",
        description=f"{user.mention}'s timeout has been removed.",
        color=0x00CC66
    )
    embed.set_footer(text="Minion Bot")
    await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────────────
#  MOD + OWNER — WARN
# ─────────────────────────────────────────────

@tree.command(name="warn", description="Warn a member")
@app_commands.describe(user="The member to warn", reason="Reason for the warning")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not has_mod_role(interaction):
        return await deny(interaction, "Moderator or Owner")

    data = load_data()
    uid = str(user.id)
    data.setdefault("warnings", {}).setdefault(uid, []).append({
        "reason": reason,
        "by": str(interaction.user.id),
        "at": int(time.time()),
    })
    save_data(data)
    warn_count = len(data["warnings"][uid])

    try:
        dm_embed = discord.Embed(
            title="⚠️ You have been warned",
            description=f"**Reason:** {reason}",
            color=0xFFAA00
        )
        dm_embed.add_field(name="Total Warnings", value=str(warn_count), inline=True)
        dm_embed.set_footer(text="Minion Bot")
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        pass

    embed = discord.Embed(
        title="⚠️ Warning Issued",
        description=f"{user.mention} has been warned.",
        color=0xFFAA00
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Warned by", value=interaction.user.mention, inline=True)
    embed.add_field(name="Total Warnings", value=str(warn_count), inline=True)
    embed.set_footer(text="Minion Bot")
    await interaction.response.send_message(embed=embed)

@tree.command(name="warnings", description="Check warnings for a member")
@app_commands.describe(user="The member to check")
async def warnings(interaction: discord.Interaction, user: discord.Member):
    if not has_mod_role(interaction):
        return await deny(interaction, "Moderator or Owner")

    data = load_data()
    uid = str(user.id)
    warns = data.get("warnings", {}).get(uid, [])

    if not warns:
        await interaction.response.send_message(f"{user.mention} has no warnings.", ephemeral=True)
        return

    embed = discord.Embed(title=f"⚠️ Warnings for {user.display_name}", color=0xFFAA00)
    for i, w in enumerate(warns, 1):
        by = interaction.guild.get_member(int(w["by"]))
        by_str = by.mention if by else f"<@{w['by']}>"
        embed.add_field(
            name=f"Warning #{i}",
            value=f"**Reason:** {w['reason']}\n**By:** {by_str}\n**At:** <t:{w['at']}:R>",
            inline=False
        )
    embed.set_footer(text="Minion Bot")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="clearwarnings", description="Clear all warnings for a member")
@app_commands.describe(user="The member to clear warnings for")
async def clearwarnings(interaction: discord.Interaction, user: discord.Member):
    if not has_owner_role(interaction):
        return await deny(interaction, "Owner")

    data = load_data()
    uid = str(user.id)
    data.setdefault("warnings", {})[uid] = []
    save_data(data)
    await interaction.response.send_message(f"✅ Cleared all warnings for {user.mention}.", ephemeral=True)

# ─────────────────────────────────────────────
#  MOD + OWNER — PURGE
# ─────────────────────────────────────────────

@tree.command(name="purge", description="Delete a number of messages from this channel")
@app_commands.describe(amount="Number of messages to delete (1-100)")
async def purge(interaction: discord.Interaction, amount: int):
    if not has_mod_role(interaction):
        return await deny(interaction, "Moderator or Owner")

    amount = max(1, min(100, amount))
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🗑️ Deleted {len(deleted)} message(s).", ephemeral=True)

# ─────────────────────────────────────────────
#  EVERYONE — /view me
# ─────────────────────────────────────────────

@tree.command(name="view", description="View info about yourself or another member")
@app_commands.describe(user="The member to view (leave blank for yourself)")
async def view(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or interaction.user

    # Only mods can view others
    if user and user != interaction.user and not has_mod_role(interaction):
        return await deny(interaction, "Moderator or Owner")

    roles = [r.mention for r in reversed(target.roles) if r.name != "@everyone"]
    roles_str = " ".join(roles) if roles else "None"

    embed = discord.Embed(
        title=f"👤 {target.display_name}",
        color=target.color if target.color.value else 0x5080FF
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Username", value=str(target), inline=True)
    embed.add_field(name="Discord ID", value=f"`{target.id}`", inline=True)
    embed.add_field(name="Nickname", value=target.nick or "None", inline=True)
    embed.add_field(name="Account Created", value=f"<t:{int(target.created_at.timestamp())}:R>", inline=True)
    embed.add_field(name="Joined Server", value=f"<t:{int(target.joined_at.timestamp())}:R>" if target.joined_at else "Unknown", inline=True)
    embed.add_field(name="Bot", value="Yes" if target.bot else "No", inline=True)
    embed.add_field(name=f"Roles ({len(roles)})", value=roles_str[:1024], inline=False)

    # Profile picture link
    embed.add_field(
        name="Profile Picture",
        value=f"[Click to view]({target.display_avatar.url})",
        inline=False
    )

    embed.set_footer(text="Minion Bot")
    await interaction.response.send_message(embed=embed, ephemeral=(target == interaction.user))

# ─────────────────────────────────────────────
#  EVERYONE — /nickname
# ─────────────────────────────────────────────

@tree.command(name="nickname", description="Change your own nickname")
@app_commands.describe(nickname="Your new nickname (leave blank to reset)")
async def nickname(interaction: discord.Interaction, nickname: Optional[str] = None):
    try:
        await interaction.user.edit(nick=nickname)
        if nickname:
            await interaction.response.send_message(f"✅ Your nickname has been changed to **{nickname}**.", ephemeral=True)
        else:
            await interaction.response.send_message("✅ Your nickname has been reset.", ephemeral=True)

        # Log it
        data = load_data()
        data.setdefault("nicknames", {})[str(interaction.user.id)] = {
            "nickname": nickname,
            "at": int(time.time()),
        }
        save_data(data)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to change your nickname.", ephemeral=True)

# ─────────────────────────────────────────────
#  MOD + OWNER — FORCE NICKNAME
# ─────────────────────────────────────────────

@tree.command(name="setnick", description="Force set a member's nickname")
@app_commands.describe(user="The member", nickname="New nickname (leave blank to reset)")
async def setnick(interaction: discord.Interaction, user: discord.Member, nickname: Optional[str] = None):
    if not has_mod_role(interaction):
        return await deny(interaction, "Moderator or Owner")

    try:
        await user.edit(nick=nickname)
        msg = f"✅ Set {user.mention}'s nickname to **{nickname}**." if nickname else f"✅ Reset {user.mention}'s nickname."
        await interaction.response.send_message(msg, ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to change that member's nickname.", ephemeral=True)

# ─────────────────────────────────────────────
#  EVERYONE — /avatar
# ─────────────────────────────────────────────

@tree.command(name="avatar", description="Get a member's profile picture")
@app_commands.describe(user="The member (leave blank for yourself)")
async def avatar(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or interaction.user
    embed = discord.Embed(title=f"{target.display_name}'s Avatar", color=0x5080FF)
    embed.set_image(url=target.display_avatar.url)
    embed.add_field(name="Download", value=f"[PNG]({target.display_avatar.with_format('png').url}) | [JPG]({target.display_avatar.with_format('jpg').url}) | [WEBP]({target.display_avatar.with_format('webp').url})")
    embed.set_footer(text="Minion Bot")
    await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────────────
#  EVERYONE — /serverinfo
# ─────────────────────────────────────────────

@tree.command(name="serverinfo", description="View info about this server")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=guild.name, color=0x5080FF)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
    embed.add_field(name="Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
    embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
    embed.add_field(name="Boosts", value=str(guild.premium_subscription_count), inline=True)
    embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
    embed.set_footer(text=f"Server ID: {guild.id} • Minion Bot")
    await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────────────
#  EVERYONE — /ping
# ─────────────────────────────────────────────

@tree.command(name="ping", description="Check the bot's latency")
async def ping(interaction: discord.Interaction):
    latency = round(client.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: **{latency}ms**",
        color=0x00CC66 if latency < 100 else 0xFFAA00 if latency < 200 else 0xFF2222
    )
    embed.set_footer(text="Minion Bot")
    await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────────────
#  EVERYONE — /roleinfo
# ─────────────────────────────────────────────

@tree.command(name="roleinfo", description="Get info about a role")
@app_commands.describe(role="The role to inspect")
async def roleinfo(interaction: discord.Interaction, role: discord.Role):
    embed = discord.Embed(title=f"Role: {role.name}", color=role.color)
    embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
    embed.add_field(name="Color", value=str(role.color), inline=True)
    embed.add_field(name="Members", value=str(len(role.members)), inline=True)
    embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
    embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
    embed.add_field(name="Position", value=str(role.position), inline=True)
    embed.add_field(name="Created", value=f"<t:{int(role.created_at.timestamp())}:R>", inline=True)
    embed.set_footer(text="Minion Bot")
    await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────────────
#  EVERYONE — /membercount
# ─────────────────────────────────────────────

@tree.command(name="membercount", description="Show the server member count")
async def membercount(interaction: discord.Interaction):
    guild = interaction.guild
    humans = sum(1 for m in guild.members if not m.bot)
    bots = sum(1 for m in guild.members if m.bot)
    embed = discord.Embed(title=f"👥 {guild.name} Members", color=0x5080FF)
    embed.add_field(name="Total", value=str(guild.member_count), inline=True)
    embed.add_field(name="Humans", value=str(humans), inline=True)
    embed.add_field(name="Bots", value=str(bots), inline=True)
    embed.set_footer(text="Minion Bot")
    await interaction.response.send_message(embed=embed)

# ─────────────────────────────────────────────
#  EVERYONE — /say (owner only)
# ─────────────────────────────────────────────

@tree.command(name="say", description="Make the bot say something")
@app_commands.describe(message="What to say", channel="Channel to send in (defaults to current)")
async def say(interaction: discord.Interaction, message: str, channel: Optional[discord.TextChannel] = None):
    if not has_owner_role(interaction):
        return await deny(interaction, "Owner")

    target_channel = channel or interaction.channel
    await target_channel.send(message)
    await interaction.response.send_message("✅ Sent.", ephemeral=True)

# ─────────────────────────────────────────────
#  EVERYONE — /embed (owner only)
# ─────────────────────────────────────────────

@tree.command(name="embed", description="Send a custom embed message")
@app_commands.describe(title="Embed title", description="Embed description", color="Hex color e.g. #FF0000")
async def embed_cmd(interaction: discord.Interaction, title: str, description: str, color: str = "#5080FF"):
    if not has_owner_role(interaction):
        return await deny(interaction, "Owner")

    try:
        color_int = int(color.replace("#", ""), 16)
    except ValueError:
        color_int = 0x5080FF

    embed = discord.Embed(title=title, description=description, color=color_int)
    embed.set_footer(text="Minion Bot")
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Embed sent.", ephemeral=True)

# ─────────────────────────────────────────────
#  EVERYONE — /help
# ─────────────────────────────────────────────

@tree.command(name="help", description="List all available commands")
async def help_cmd(interaction: discord.Interaction):
    is_owner = has_owner_role(interaction)
    is_mod = has_mod_role(interaction)

    embed = discord.Embed(title="🤖 Minion Bot — Commands", color=0x5080FF)
    embed.set_footer(text="Minion Bot")

    # Everyone
    embed.add_field(name="👤 Everyone", value="\n".join([
        "`/view` — View your profile (ID, avatar, roles, etc.)",
        "`/avatar` — Get a member's profile picture",
        "`/nickname` — Change your own nickname",
        "`/ping` — Check bot latency",
        "`/serverinfo` — View server info",
        "`/membercount` — Show member count",
        "`/roleinfo` — Get info about a role",
    ]), inline=False)

    if is_mod:
        embed.add_field(name="🛡️ Moderator + Owner", value="\n".join([
            "`/kick` — Kick a member",
            "`/warn` — Warn a member",
            "`/warnings` — View a member's warnings",
            "`/timeout` — Timeout a member",
            "`/untimeout` — Remove a timeout",
            "`/purge` — Delete messages",
            "`/setnick` — Force set a nickname",
            "`/view <user>` — View another member's profile",
        ]), inline=False)

    if is_owner:
        embed.add_field(name="👑 Owner Only", value="\n".join([
            "`/ban` — Ban a member",
            "`/unban` — Unban by user ID",
            "`/clearwarnings` — Clear a member's warnings",
            "`/say` — Make the bot say something",
            "`/embed` — Send a custom embed",
        ]), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ─────────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────────

client.run(TOKEN)
