from flask import Flask, request, jsonify
import threading
import time
import discord
from discord.ext import commands
import random
import os
import json

CONFIG_FILE = "servers.json"
LINKS_FILE = "links.json"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

# ---------------- CONFIG ----------------

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ---------------- LINKS ----------------

def load_links():
    try:
        with open(LINKS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_links(data):
    with open(LINKS_FILE, "w") as f:
        json.dump(data, f, indent=4)

uuid_to_discord = load_links()
code_to_uuid = {}

CODE_EXPIRY = 300

# ---------------- TEAM LOGIC ----------------

def get_team(member):
    config = load_config().get(str(member.guild.id))

    if not config:
        return "none"

    role_ids = [role.id for role in member.roles]

    for team_name, role_id in config.items():
        if role_id in role_ids:
            return team_name

    return "none"

# ---------------- BOT COMMANDS ----------------

@bot.command()
@commands.has_permissions(administrator=True)
async def addteam(ctx, team: str, role: discord.Role):
    data = load_config()
    guild_id = str(ctx.guild.id)

    if guild_id not in data:
        data[guild_id] = {}

    data[guild_id][team] = role.id
    save_config(data)

    await ctx.send(f"team `{team}` → {role.name} added")

@bot.command()
@commands.has_permissions(administrator=True)
async def removeteam(ctx, team: str):
    data = load_config()
    guild_id = str(ctx.guild.id)

    if guild_id not in data or team not in data[guild_id]:
        await ctx.send("team not found")
        return

    del data[guild_id][team]
    save_config(data)

    await ctx.send(f"removed team `{team}`")

@bot.command()
async def teams(ctx):
    data = load_config()
    guild_id = str(ctx.guild.id)

    if guild_id not in data or not data[guild_id]:
        await ctx.send("no teams set")
        return

    msg = "**Teams:**\n"
    for team, role_id in data[guild_id].items():
        role = ctx.guild.get_role(role_id)
        name = role.name if role else "missing role"
        msg += f"- {team} → {name}\n"

    await ctx.send(msg)

@bot.command()
async def help(ctx):
    msg = (
        "**Fluu's Teams Setup Guide!!**\n\n"

        "**Step 1. install the mod to your server**\n"
        "**Step 2. find the config and replace server id:**\n"
        "`replace PUT_DISCORD_SERVER_ID_HERE with your actual server id `\n"
        "after that, restart your server!\n\n"

        "**Step 3. create roles for your teams**\n"
        "**Step 4. add teams using:**\n"
        "`$addteam <name> @role`\n\n"

        "**Example:**\n"
        "`$addteam sorcerer @Sorcerer`\n"
        "`$addteam curse @Curse`\n\n"

        "**Step 5. make the minecraft teams:**\n"
        "- create teams in Minecraft with the SAME ID or name\n"
        "for example, if you did $addteam sorcerer, then you must create the minecraft team with the ID or name sorcerer\n\n"

        "**Step 6. players verify:**\n"
        "- Run `/verify` in Minecraft\n"
        "- Use `$verify CODE` in Discord\n\n"

        "**you're all set! if you face any issues, join the help server: https://discord.gg/9R5fwPFaDz**"
    )

    await ctx.send(msg)

# ---------------- API ----------------

app = Flask(__name__)

@app.route("/verify/start", methods=["POST"])
def start_verify():
    data = request.json
    uuid = data.get("uuid")

    if not uuid:
        return jsonify({"error": "missing uuid"}), 400

    code = f"FLUU-{random.randint(1000,9999)}"

    code_to_uuid[code] = {
        "uuid": uuid,
        "expires": time.time() + CODE_EXPIRY
    }

    print(f"[VERIFY START] {uuid} -> {code}")
    return jsonify({"code": code})


@app.route("/role", methods=["GET"])
def get_role():
    uuid = request.args.get("uuid")
    guild_id = request.args.get("guild")

    if not uuid or not guild_id:
        return jsonify({"team": "none"})

    if uuid not in uuid_to_discord:
        return jsonify({"team": "none"})

    data = uuid_to_discord[uuid]

    if guild_id not in data:
        return jsonify({"team": "none"})

    discord_id = data[guild_id]

    guild = bot.get_guild(int(guild_id))
    if not guild:
        return jsonify({"team": "none"})

    member = guild.get_member(discord_id)
    if not member:
        return jsonify({"team": "none"})

    team = get_team(member)

    print(f"[ROLE CHECK] {uuid} -> {team} (guild {guild_id})")
    return jsonify({"team": team})

# ---------------- BOT EVENTS ----------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command()
async def verify(ctx, code: str):
    if code not in code_to_uuid:
        await ctx.send("invalid or expired code")
        return

    data = code_to_uuid[code]

    if time.time() > data["expires"]:
        del code_to_uuid[code]
        await ctx.send("code expired")
        return

    uuid = data["uuid"]
    guild_id = str(ctx.guild.id)
    discord_id = ctx.author.id

    # 🔥 MULTI-SERVER SUPPORT
    if uuid not in uuid_to_discord:
        uuid_to_discord[uuid] = {}

    uuid_to_discord[uuid][guild_id] = discord_id

    save_links(uuid_to_discord)

    del code_to_uuid[code]

    await ctx.send("linked successfully")

# ---------------- RUN ----------------

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()

bot.run(os.getenv("DISCORD_TOKEN"))
