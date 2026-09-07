# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import json
import os
import asyncio
from aiohttp import web, ClientSession

# تحميل ملف الإعدادات
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

BLACKLIST_FILE = "blacklist.txt"
if not os.path.exists(BLACKLIST_FILE):
    with open(BLACKLIST_FILE, "w") as f:
        pass

def is_blacklisted(user_id):
    with open(BLACKLIST_FILE, "r") as f:
        blacklisted = f.read().splitlines()
    return str(user_id) in blacklisted

def add_to_blacklist(user_id):
    if not is_blacklisted(user_id):
        with open(BLACKLIST_FILE, "a") as f:
            f.write(f"{user_id}\n")

class RecruitmentView(discord.ui.View):
    def __init__(self, applicant_id, answers):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.answers = answers

    async def check_permissions(self, interaction: discord.Interaction):
        user_role_ids = [role.id for role in interaction.user.roles]
        allowed = any(role_id in config['ALLOWED_MANAGEMENT_ROLES'] for role_id in user_role_ids)
        if interaction.user.id == interaction.guild.owner_id or allowed:
            return True
        await interaction.response.send_message("❌ غير مصرح لك.", ephemeral=True)
        return False

    @discord.ui.button(label="✅ قبول", style=discord.ButtonStyle.success, custom_id="accept_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction): return
        
        guild = bot.get_guild(config['GUILD_ID'])
        member = guild.get_member(int(self.applicant_id))
        
        if member:
            role = guild.get_role(config['TRAINEE_ROLE_ID'])
            if role:
                await member.add_roles(role)
                try:
                    await member.send(f"🎉 **تهانينا!** تم قبول طلب انضمامك للإدارة في سيرفر **{guild.name}**.")
                except: pass
            
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.title = f"✅ تم قبول المتقدم بواسطة: {interaction.user.name}"
            for child in self.children: child.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ العضو غير موجود بالسيرفر.", ephemeral=True)

    @discord.ui.button(label="❌ رفض", style=discord.ButtonStyle.danger, custom_id="reject_btn")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction): return
        
        guild = bot.get_guild(config['GUILD_ID'])
        member = guild.get_member(int(self.applicant_id))
        if member:
            try: await member.send(f"❌ تم رفض طلب تقديمك في **{guild.name}**.")
            except: pass
        
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = f"❌ تم الرفض بواسطة: {interaction.user.name}"
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🚫 بلاك ليست", style=discord.ButtonStyle.secondary, custom_id="blacklist_btn")
    async def blacklist(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction): return
        
        add_to_blacklist(self.applicant_id)
        guild = bot.get_guild(config['GUILD_ID'])
        member = guild.get_member(int(self.applicant_id))
        
        if member:
            try: await member.send(f"🚫 تم حظرك من التقديم في **{guild.name}**.")
            except: pass
        
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.dark_gray()
        embed.title = f"🚫 بلاك ليست بواسطة: {interaction.user.name}"
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تقديم الإدارة</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #1a1c1e; color: #fff; padding: 20px; text-align: right; }
        .container { max-width: 700px; margin: 0 auto; background: #24272b; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
        h1 { color: #5865F2; text-align: center; margin-bottom: 20px; }
        .user-info { background: #2f3136; padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: center; color: #43b581; font-weight: bold; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: bold; color: #b9bbbe; }
        textarea { width: 100%; padding: 12px; background: #1e2226; border: 1px solid #31353b; border-radius: 6px; color: #fff; box-sizing: border-box; resize: vertical; height: 100px; }
        textarea:focus { border-color: #5865F2; outline: none; }
        button { width: 100%; padding: 14px; background: #5865F2; border: none; color: white; font-size: 16px; font-weight: bold; border-radius: 6px; cursor: pointer; transition: 0.2s; }
        button:hover { background: #4752c4; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 استمارة التقديم على الإدارة</h1>
        <div class="user-info">
            ✅ مسجل الدخول بحساب: {USERNAME}
        </div>
        <form method="POST" action="/submit">
            <!-- الآيدي محمي ومخفي لتجنب التلاعب -->
            <input type="hidden" name="user_id" value="{USER_ID}">
            {% QUESTIONS_PLACEHOLDER %}
            <button type="submit">إرسال طلب التقديم</button>
        </form>
    </div>
</body>
</html>
"""

async def start_webserver():
    app = web.Application()
    
    async def handle_home(request):
        return web.Response(text='''
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head><meta charset="UTF-8"><title>تسجيل الدخول</title>
        <style>
            body { font-family: sans-serif; background-color: #1a1c1e; color: #fff; text-align: center; padding-top: 150px; }
            a { display: inline-block; padding: 15px 30px; background: #5865F2; color: white; text-decoration: none; border-radius: 8px; font-size: 18px; font-weight: bold; transition: 0.3s; }
            a:hover { background: #4752c4; }
        </style>
        </head>
        <body>
            <h1>نظام التقديم للإدارة</h1>
            <p>يجب ربط حساب ديسكورد الخاص بك لتقديم الطلب</p><br>
            <a href="/login">🔗 تسجيل الدخول بواسطة Discord</a>
        </body>
        </html>
        ''', content_type='text/html')

    async def login(request):
        client_id = config.get("CLIENT_ID")
        redirect_uri = config.get("REDIRECT_URI")
        auth_url = f"https://discord.com/api/oauth2/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=identify"
        raise web.HTTPFound(auth_url)

    async def callback(request):
        code = request.query.get('code')
        if not code:
            return web.Response(text="❌ تم إلغاء تسجيل الدخول.", content_type='text/html')

        async with ClientSession() as session:
            data = {
                'client_id': config.get("CLIENT_ID"),
                'client_secret': config.get("CLIENT_SECRET"),
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': config.get("REDIRECT_URI")
            }
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            async with session.post('https://discord.com/api/oauth2/token', data=data, headers=headers) as resp:
                token_info = await resp.json()
                if 'access_token' not in token_info:
                    return web.Response(text="❌ فشل في مصادقة الحساب. يرجى التحقق من CLIENT_SECRET و REDIRECT_URI.", content_type='text/html')
                access_token = token_info['access_token']

            async with session.get('https://discord.com/api/users/@me', headers={'Authorization': f'Bearer {access_token}'}) as resp:
                user_info = await resp.json()
                user_id = user_info.get('id')
                username = user_info.get('username')

        if is_blacklisted(user_id):
            return web.Response(text="<h2 style='color:red; text-align:center; margin-top:50px;'>❌ نأسف، هذا الحساب محظور من التقديم.</h2>", content_type='text/html')

        questions_html = ""
        for i, q in enumerate(config['QUESTIONS'], 1):
            questions_html += f'''
            <div class="form-group">
                <label>{i}. {q}</label>
                <textarea name="q_{i}" required></textarea>
            </div>
            '''
        
        page = HTML_PAGE.replace("{% QUESTIONS_PLACEHOLDER %}", questions_html)
        page = page.replace("{USER_ID}", str(user_id)).replace("{USERNAME}", str(username))
        
        return web.Response(text=page, content_type='text/html')

    async def handle_submit(request):
        data = await request.post()
        user_id = data.get('user_id')
        
        if not user_id or is_blacklisted(user_id):
            return web.Response(text="❌ طلب غير صالح أو حساب محظور.", content_type='text/html')
        
        guild = bot.get_guild(config['GUILD_ID'])
        channel = bot.get_channel(config['MANAGEMENT_CHANNEL_ID'])
        
        if channel:
            embed = discord.Embed(
                title="📥 طلب تقديم جديد على الإدارة",
                description=f"**صاحب الطلب (آيدي):** {user_id}\n**الحساب في السيرفر:** <@{user_id}>",
                color=discord.Color.blue()
            )
            
            for i, q in enumerate(config['QUESTIONS'], 1):
                ans = data.get(f'q_{i}')
                if ans:
                    if len(ans) > 1024: ans = ans[:1020] + "..."
                    embed.add_field(name=f"س{i}: {q}", value=ans, inline=False)
            
            view = RecruitmentView(applicant_id=user_id, answers=data)
            await channel.send(embed=embed, view=view)
            
            return web.Response(text="<div style='text-align:center; margin-top:50px;'> <h2 style='color:#2ecc71;'>✅ تم إرسال طلبك بنجاح!</h2> </div>", content_type='text/html')
        
        return web.Response(text="❌ خطأ: لم يتم العثور على غرفة الإدارة.", content_type='text/html')

    app.router.add_get('/', handle_home)
    app.router.add_get('/login', login)
    app.router.add_get('/callback', callback)
    app.router.add_post('/submit', handle_submit)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # التوافق الكامل مع منصة Render (يأخذ المنفذ من النظام تلقائياً)
    port = int(os.environ.get('PORT', config.get('WEB_SERVER_PORT', 8080)))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Server started on port {port}")

@bot.event
async def on_ready():
    print(f"✅ تم تسجيل الدخول كـ: {bot.user.name}")
    bot.loop.create_task(start_webserver())

if __name__ == "__main__":
    if config.get('BOT_TOKEN') == "ضع_توكن_البوت_هنا":
        print("❌ الرجاء تحديث التوكن في ملف config.json")
    else:
        bot.run(config['BOT_TOKEN'])
