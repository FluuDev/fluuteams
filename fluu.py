from flask import Flask, request, jsonify
import threading
import time
import discord
from discord.ext import commands
import random
import os
import json

CONFIG_FILE = "servers.json"


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="$", intents=intents)

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

code_to_uuid = {}
uuid_to_discord = {}

CODE_EXPIRY = 300

def get_guild_and_member(discord_id):
    for guild in bot.guilds:
        member = guild.get_member(discord_id)
        if member:
            return guild, member
    return None, None

def get_team(member):
    config = load_config().get(str(member.guild.id))

    if not config:
        return "none"

    role_ids = [role.id for role in member.roles]

    for team_name, role_id in config.items():
        if role_id in role_ids:
            return team_name

    return "none"

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

app = Flask(__name__)


@app.route("/verify/start", methods=["POST"])
def start_verify():
    data = request.json
    uuid = data.get("uuid")

    if not uuid:
        return jsonify({"error": "missing uuid"}), 400

    code = f"JUJU-{random.randint(1000,9999)}"

    code_to_uuid[code] = {
        "uuid": uuid,
        "expires": time.time() + CODE_EXPIRY
    }

    print(f"[VERIFY START] {uuid} -> {code}")

    return jsonify({"code": code})


@app.route("/role", methods=["GET"])
def get_role():
    uuid = request.args.get("uuid")

    if uuid not in uuid_to_discord:
        return jsonify({"team": "none"})

    discord_id = uuid_to_discord[uuid]

    guild, member = get_guild_and_member(discord_id)

    if not member:
        return jsonify({"team": "none"})

    team = get_team(member)

    print(f"[ROLE CHECK] {uuid} -> {team}")

    return jsonify({"team": team})


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

    uuid_to_discord[uuid] = ctx.author.id
    del code_to_uuid[code]

    await ctx.send("linked successfully")


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()


bot.run(os.getenv("DISCORD_TOKEN"))