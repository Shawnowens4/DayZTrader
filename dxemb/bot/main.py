import os
import discord

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"DXEMB bot online as {client.user}")

def run():
    if not TOKEN:
        print("DISCORD_BOT_TOKEN not set - bot will not connect to Discord Gateway.")
        print("DXEMB bot skeleton started (no-op mode).")
        import time
        while True:
            time.sleep(60)
    else:
        client.run(TOKEN)

if __name__ == "__main__":
    run()
