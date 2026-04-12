import discord
from discord import app_commands
import os
import io
import g4f

# Only requires Discord Token! Zero external API keys needed.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

class LuaGeneratorBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Syncs the slash commands to Discord globally when the bot starts
        await self.tree.sync()
        print("Slash commands synced successfully!")

client = LuaGeneratorBot()

@client.event
async def on_ready():
    print(f'Logged in fully as {client.user} (ID: {client.user.id})')
    print('Bot is ready to receive commands!')
    print('------')

@client.tree.command(name="generatescript", description="Generates a flawless Lua script using free AI based on your prompt")
@app_commands.describe(prompt="What do you want the Lua script to do?")
async def generatescript(interaction: discord.Interaction, prompt: str):
    # Defer the interaction immediately because Free AI inference can take a few seconds
    await interaction.response.defer(thinking=True)
    
    try:
        system_instructions = (
            "You are an elite Lua and Roblox script developer. "
            "Write a highly functional, error-free Lua script based on the user's prompt. "
            "Do not include any English conversational text or explanations. "
            "Only output the pure Lua code wrapped cleanly in ```lua ``` codeblocks. "
            "Ensure the script is optimized, well-structured, and secure."
        )
        
        # Async invocation of the completely Free GPT-4 Inference wrappers
        response = await g4f.ChatCompletion.create_async(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": prompt}
            ]
        )
        
        # G4F returns the raw text natively in this method
        script_content = response.strip()
        
        # Fallback to wrap text if AI forgets markdown formatting
        if not script_content.startswith("```lua") and not script_content.startswith("```"):
            script_content = f"```lua\n{script_content}\n```"
        
        # Validate Discord's 2000 character limit per message
        if len(script_content) > 1900:
            # Clean up markdown format for RAW dumping into the .lua file
            raw_script = script_content.replace("```lua\n", "").replace("\n```", "").replace("```", "")
            
            file_stream = io.BytesIO(raw_script.encode('utf-8'))
            script_file = discord.File(file_stream, filename="generated_script.lua")
            
            await interaction.followup.send(content="✨ The script was securely generated but was too long for a message, so I attached it as a file for you!", file=script_file)
        else:
            await interaction.followup.send(content=f"✨ **Here is your generated script!**\n{script_content}")
            
    except Exception as e:
        await interaction.followup.send(content=f"❌ An error occurred while generating the script using the Free API:\n```\n{str(e)}\n```")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("CRITICAL: Please set the DISCORD_TOKEN environment variable in Railway.")
    else:
        client.run(DISCORD_TOKEN)
