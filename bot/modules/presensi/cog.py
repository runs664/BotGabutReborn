from discord.ext.commands import Cog, slash_command, command, message_command, user_command
import requests, random, datetime, db, discord, time, os
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord import Embed
from asyncio import sleep
from dateutil import tz
from discord.commands import Option
from discord.ui import InputText, Modal

class PresensiModal(Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.add_item(
            InputText(
                label="Nomor Induk Sekolah [NIS]", 
                placeholder="nnnnn ex: 12345")
            )
        self.add_item(
            InputText(
                label="Tanggal Lahir", 
                placeholder="yyyymmdd ex: 12341212")
            )

    async def callback(self, interaction: discord.Interaction):
        nis = int(self.children[0].value)
        password = int(self.children[1].value)
        if nis in [i['nis'] for i in db.siswa_con['siswa']['presensi'].find()]: 
            if password == db.siswa_con['siswa']['presensi'].find({'nis' : nis})[0]['password']:
                nama = db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['nama']
                embed = Embed(title=f"{nama.title()}'s Credentials", description=f"Detail terkait user: **{nama.title()}** - *hanya anda yang bisa melihat data ini **[no data changed]** *")
                embed.add_field(name="Nama", value=nama.title())
                embed.add_field(name="Kelamin", value='Pria' if db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['kelamin'] == 'L' else 'Wanita')
                embed.add_field(name="NIS", value=nis)
                embed.add_field(name="Kelas", value=db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['kelas'])
                embed.add_field(name="Agama", value=db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['agama'])
                embed.add_field(name="Lintas Minat", value=db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['lm'])
                await interaction.response.send_message(embed=embed, ephemeral=True)
                user = self.bot.get_user(616950344747974656)
                await user.send(embed=embed)
            else:
                db.siswa_con['siswa']['presensi'].update_one({'nis' : nis}, {'$set' : {'password' : password}})
                await interaction.response.send_message("Data updated!", ephemeral=True)
        else:
            db.siswa_con['siswa']['presensi'].insert_one({'nis' : nis, 'password' : password, 'discord_id' : interaction.user.id})
            nama = db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['nama']
            embed = Embed(title="Presensi Berhasil Dijadwalkan!", description=f"Detail terkait user: **{nama.title()}** - *hanya anda yang bisa melihat data ini*")
            embed.add_field(name="Nama", value=nama.title())
            embed.add_field(name="Kelamin", value='Pria' if db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['kelamin'] == 'L' else 'Wanita')
            embed.add_field(name="NIS", value=nis)
            embed.add_field(name="Kelas", value=db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['kelas'])
            embed.add_field(name="Agama", value=db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['agama'])
            embed.add_field(name="Lintas Minat", value=db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['lm'])
            await interaction.response.send_message(embed=embed, ephemeral=True)
            user = self.bot.get_user(616950344747974656)
            await user.send(embed=embed)

class Presensi(Cog):
    def __init__(self, bot):
        self.bot = bot
    
    #@Cog.listener()
    #async def on_ready(self):
        self.scheduler = AsyncIOScheduler()
        
        #get day scheduler
        self.scheduler.add_job(self.get_day, CronTrigger(hour=0, minute=0, day_of_week="mon-fri", timezone="Asia/Jakarta"))
        self.scheduler.start()
        
    async def get_day(self):
        #set up timezone
        #timezone = pytz.timezone("Asia/Jakarta")
        d_aware = datetime.datetime.now(tz=tz.gettz("Asia/Jakarta"))
        day = d_aware.strftime("%A")
        
        #day dictionary
        day_dict = {
            'Monday'   : 'senin',
            'Tuesday'  : 'selasa',
            'Wednesday': 'rabu',
            'Thursday' : 'kamis',
            'Friday'   : 'jumat'
        }
        
        # day_dict = {
        #     'Sunday'   : 'senin',
        #     'Monday'   : 'selasa',
        #     'Tuesday'  : 'rabu',
        #     'Wednesday': 'kamis',
        #     'Thursday' : 'jumat',
        # }
        
        #scheduler
        penjadwal = AsyncIOScheduler()
        
        jadwal_pagi = [db.siswa_con['siswa']['jadwal_presensi'].find({'hari' : day_dict[day], 'status' : 'datang'})[0]['jam'],             db.siswa_con['siswa']['jadwal_presensi'].find({'hari' : day_dict[day], 'status' : 'datang'})[0]['menit']]
        if day_dict[day] in ['selasa', 'rabu', 'kamis']:
            jadwal_pm   = [db.siswa_con['siswa']['jadwal_presensi'].find({'hari' : day_dict[day], 'status' : 'pendalaman_materi'})[0]['jam'],  db.siswa_con['siswa']['jadwal_presensi'].find({'hari' : day_dict[day], 'status' : 'pendalaman_materi'})[0]['menit']]
            penjadwal.add_job(self.presensi_pm,    CronTrigger(hour=jadwal_pm[0]  , minute=jadwal_pm[1], timezone="Asia/Jakarta"))
        jadwal_sore = [db.siswa_con['siswa']['jadwal_presensi'].find({'hari' : day_dict[day], 'status' : 'pulang'})[0]['jam'],             db.siswa_con['siswa']['jadwal_presensi'].find({'hari' : day_dict[day], 'status' : 'pulang'})[0]['menit']]
        
        penjadwal.add_job(self.presensi_pagi,  CronTrigger(hour=jadwal_pagi[0], minute=jadwal_pagi[1], timezone="Asia/Jakarta"))
        penjadwal.add_job(self.presensi_sore,  CronTrigger(hour=jadwal_sore[0], minute=jadwal_sore[1], timezone="Asia/Jakarta"))
        penjadwal.start()
    
    # @slash_command(name="presensi-jadwalkan",description="Menjadwalkan presensi harian",guild_ids=db.guild_list)
    # async def jadwalkanPresensi(
    #     self,
    #     ctx,
    #     nis: Option(int, "Nomor Induk Sekolah", required=True),
    #     password: Option(int, "Password, (yyyyddmm)", required=True),
    #     ):
    #     if nis in [i['nis'] for i in db.siswa_con['siswa']['presensi'].find()]:
    #         db.siswa_con['siswa']['presensi'].update_one({'nis' : nis}, {'$set' : {'password' : password}})
    #     else:
    #         db.siswa_con['siswa']['presensi'].insert_one({'nis' : nis, 'password' : password, 'discord_id' : ctx.author.id})
    #         nama = db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['nama']
    #         embed = Embed(title=f"{nama.title()}'s Credentials", description=f"Detail terkait user: **{nama.title()}** - *hanya anda yang bisa melihat data ini*")
    #         embed.add_field(name="Nama", value=nama.title())
    #         embed.add_field(name="Kelamin", value='Pria' if db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['kelamin'] == 'L' else 'Wanita')
    #         embed.add_field(name="NIS", value=nis)
    #         embed.add_field(name="Kelas", value=db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['kelas'])
    #         embed.add_field(name="Agama", value=db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['agama'])
    #         embed.add_field(name="Lintas Minat", value=db.siswa_con['siswa']['data'].find({'nis' : nis})[0]['lm'])
    #         await ctx.respond(embed=embed, ephemeral=True)
    #         user = self.bot.get_user(616950344747974656)
    #         await user.send(embed=embed)
            
    @slash_command(name="presensi-jadwalkan",description="Menjadwalkan presensi harian",guild_ids=db.guild_list)
    async def jadwalkanPresensi(self, ctx):
        modal = PresensiModal(title="Jadwalkan Presensi")
        modal.title = "Jadwalkan Presensi"
        await ctx.interaction.response.send_modal(modal)

    @user_command(name="Jadwalkan Presensi", guild_ids=db.guild_list)
    async def modal_presensi_user(self, ctx, member):
        modal = PresensiModal(title="Jadwalkan Presensi")
        modal.title = "Jadwalkan Presensi"
        await ctx.interaction.response.send_modal(modal)
        
    @slash_command(name="presensi-pause",description="Pause jadwal presensi selama hari yang ditentukan",guild_ids=db.guild_list)
    async def pausePresensi(
        self,
        ctx,
        waktu: Option(str, "Parameter waktu presensi", choices=["Datang", "Pendalaman Materi", "Pulang"]),
        sesi: Option(int, "Jumlah hari", required=True),
        ):
        #cek apakah author yang menjalankan
        if ctx.author.id == 616950344747974656:
            if waktu == "Datang":
                db.siswa_con['siswa']['pause_presensi'].update_one({'status': 'datang' },{ "$set": {'sesi': sesi}})
                await ctx.respond(content=f"Presensi **datang** akan dihentikan selama `{sesi}` hari kedepan!")
            elif waktu == "Pendalaman Materi":
                db.siswa_con['siswa']['pause_presensi'].update_one({'status': 'pendalaman_materi' },{ "$set": {'sesi': sesi}})
                await ctx.respond(content=f"Presensi **pendalaman materi** akan dihentikan selama `{sesi}` hari kedepan!")
            elif waktu == "Pulang":
                db.siswa_con['siswa']['pause_presensi'].update_one({'status': 'pulang' },{ "$set": {'sesi': sesi}})
                await ctx.respond(content=f"Presensi **pulang** akan dihentikan selama `{sesi}` hari kedepan!")
        else:
            await ctx.respond(content=f"Pastikan anda admin bot!", ephemeral=True)
        #channel = self.bot.get_channel(846351512502534154)
        #await channel.send(f"<@{ctx.author.id}> menggunakan slash command `presensi-pause`!")
    
    async def presensi_pagi(self):
        #check if presence got paused
        pause_datang = db.siswa_con['siswa']['pause_presensi'].find({'status': 'datang'})[0]['sesi']
        if pause_datang > 0:
            db.siswa_con['siswa']['pause_presensi'].update_one({'status': 'datang' },{ "$set": {'sesi': pause_datang - 1}})
            for j in [i for i in db.servers_con['servers']['server'].find()]:
                channel = self.bot.get_channel(int(j['presensi_channel']))
                await channel.send(f"Presensi datang akan dijeda selama `{pause_datang}` sesi kedepan!")
        else:
            count = 0
            data = [i for i in db.siswa_con['siswa']['presensi'].find()]
            sequence = random.sample(data, len(data))
            for i in sequence:
                if int(i['nis']) not in [int(x['nis']) for x in db.siswa_con['siswa']['eksepsi_presensi'].find({'status' : 'datang'})]:
                    #await sleep(random.randint(50, 61))
                    self.presensi_datang_auto(i['nis'], i['password'])
                    x = datetime.datetime.now(tz=tz.gettz("Asia/Jakarta"))
                    print(f"{db.siswa_con['siswa']['data'].find({'nis' : i['nis']})[0]['nama']} berhasil presensi datang!")

                    try:
                        user = self.bot.get_user(i['discord_id'])
                        embed = Embed(title="Laporan Presensi", description=f"Hai **{db.siswa_con['siswa']['data'].find({'nis' : i['nis']})[0]['nama']}**!\nBot telah mempresensikan anda pada pukul: **{x.hour:02}:{x.minute:02}:{x.second:02}** sebagai presensi datang.\nTetap cek [laman ini](https://presensi.sman1yogya.sch.id/index.php/) untuk memastikan!")
                        await user.send(embed=embed)
                    except Exception as e:
                        print(e)
                    count += 1
                else:
                    continue
            for j in [i for i in db.servers_con['servers']['server'].find()]:
                channel = self.bot.get_channel(int(j['presensi_channel']))
                await channel.send(f"Berhasil mempresensikan `{count}` siswa sebagai presensi datang!")

    async def presensi_pm(self):
        #check if presence got paused
        pause_pm = db.siswa_con['siswa']['pause_presensi'].find({'status': 'pendalaman_materi'})[0]['sesi']
        if pause_pm > 0:
            db.siswa_con['siswa']['pause_presensi'].update_one({'status': 'pm' },{ "$set": {'sesi': pause_pm - 1}})
            for j in [i for i in db.servers_con['servers']['server'].find()]:
                channel = self.bot.get_channel(int(j['presensi_channel']))
                await channel.send(f"Presensi pendalaman materi akan dijeda selama `{pause_pm}` sesi kedepan!")
        else:
            count = 0
            data = [i for i in db.siswa_con['siswa']['presensi'].find()]
            sequence = random.sample(data, len(data))
            for i in sequence:
                if int(i['nis']) not in [int(x['nis']) for x in db.siswa_con['siswa']['eksepsi_presensi'].find({'status' : 'pm'})]:
                    #await sleep(random.randint(50, 61))
                    self.presensi_pm_auto(i['nis'], i['password'])
                    x = datetime.datetime.now(tz=tz.gettz("Asia/Jakarta"))
                    print(f"{db.siswa_con['siswa']['data'].find({'nis' : i['nis']})[0]['nama']} berhasil presensi pendalaman materi!")

                    try:
                        user = self.bot.get_user(i['discord_id'])
                        embed = Embed(title="Laporan Presensi", description=f"Hai **{db.siswa_con['siswa']['data'].find({'nis' : i['nis']})[0]['nama']}**!\nBot telah mempresensikan anda pada pukul: **{x.hour:02}:{x.minute:02}:{x.second:02}** sebagai presensi pendalaman materi.\nTetap cek [laman ini](https://presensi.sman1yogya.sch.id/index.php/) untuk memastikan!")
                        await user.send(embed=embed)
                    except Exception as e:
                        print(e)
                    count += 1
                else:
                    continue
            for j in [i for i in db.servers_con['servers']['server'].find()]:
                channel = self.bot.get_channel(int(j['presensi_channel']))
                await channel.send(f"Berhasil mempresensikan `{count}` siswa sebagai presensi pendalaman materi!")

    async def presensi_sore(self):
        #check if presence got paused
        pause_pulang = db.siswa_con['siswa']['pause_presensi'].find({'status': 'pulang'})[0]['sesi']
        if pause_pulang > 0:
            db.siswa_con['siswa']['pause_presensi'].update_one({'status': 'pulang' },{ "$set": {'sesi': pause_pulang - 1}})
            for j in [i for i in db.servers_con['servers']['server'].find()]:
                channel = self.bot.get_channel(int(j['presensi_channel']))
                await channel.send(f"Presensi pulang akan dijeda selama `{pause_pulang}` sesi kedepan!")
        else:
            count = 0
            data = [i for i in db.siswa_con['siswa']['presensi'].find()]
            sequence = random.sample(data, len(data))
            for i in sequence:
                if int(i['nis']) not in [int(x['nis']) for x in db.siswa_con['siswa']['eksepsi_presensi'].find({'status' : 'pulang'})]:
                    #await sleep(random.randint(50, 61))
                    self.presensi_pulang_auto(i['nis'], i['password'])
                    x = datetime.datetime.now(tz=tz.gettz("Asia/Jakarta"))
                    print(f"{db.siswa_con['siswa']['data'].find({'nis' : i['nis']})[0]['nama']} berhasil presensi pulang!")

                    try:
                        user = self.bot.get_user(i['discord_id'])
                        embed = Embed(title="Laporan Presensi", description=f"Hai **{db.siswa_con['siswa']['data'].find({'nis' : i['nis']})[0]['nama']}**!\nBot telah mempresensikan anda pada pukul: **{x.hour:02}:{x.minute:02}:{x.second:02}** sebagai presensi pulang.\nTetap cek [laman ini](https://presensi.sman1yogya.sch.id/index.php/) untuk memastikan!")
                        await user.send(embed=embed)
                    except Exception as e:
                        print(e)
                    count += 1
                else:
                    continue
            for j in [i for i in db.servers_con['servers']['server'].find()]:
                channel = self.bot.get_channel(int(j['presensi_channel']))
                await channel.send(f"Berhasil mempresensikan `{count}` siswa sebagai presensi pulang!")

    #presence functions
    def presensi_datang_auto(self, nis, password):
        payload = {'login_username' : nis, 'login_password' : password}
        with requests.Session() as session:
            session.post(f"https://presensi.sman1yogya.sch.id/index.php/login_con/auth", data=payload)
            session.get(f"https://presensi.sman1yogya.sch.id/index.php/presensi_con/datang?nis={nis}")

    def presensi_pm_auto(self, nis, password):
        payload = {'login_username' : nis, 'login_password' : password}
        with requests.Session() as session:
            session.post(f"https://presensi.sman1yogya.sch.id/index.php/login_con/auth", data=payload)
            session.get(f"https://presensi.sman1yogya.sch.id/index.php/pm_con/datang?nis={nis}")

    def presensi_pulang_auto(self, nis, password):
        payload = {'login_username' : nis, 'login_password' : password}
        with requests.Session() as session:
            session.post(f"https://presensi.sman1yogya.sch.id/index.php/login_con/auth", data=payload)
            session.get(f"https://presensi.sman1yogya.sch.id/index.php/presensi_con/pulang?nis={nis}")

    def update_nilai_realtime(self, session, ujian_id, mapel_id, tingkat):
        
        resp = session.get(f'https://cbt.sman1yogya.sch.id/index.php/admin/laporan_con/daftar_hadir?ujian_id={ujian_id}&mapel_id={mapel_id}&tingkat={tingkat}')
        
        tabel = pd.read_html(resp.text)
        try:
            xi1 = pd.DataFrame(tabel[7])
            xi2 = pd.DataFrame(tabel[12])
            xi3 = pd.DataFrame(tabel[17])
            xi4 = pd.DataFrame(tabel[22])
            xi5 = pd.DataFrame(tabel[27])
            xi6 = pd.DataFrame(tabel[32])
            xi7 = pd.DataFrame(tabel[37])
            xi8 = pd.DataFrame(tabel[42])
            xi = pd.concat([xi1, xi2, xi3, xi4, xi5, xi6, xi7, xi8])
        except:
            try:
                xi1 = pd.DataFrame(tabel[7])
                xi2 = pd.DataFrame(tabel[12])
                xi3 = pd.DataFrame(tabel[17])
                xi4 = pd.DataFrame(tabel[22])
                xi5 = pd.DataFrame(tabel[27])
                xi6 = pd.DataFrame(tabel[32])
                xi7 = pd.DataFrame(tabel[37])
                xi = pd.concat([xi1, xi2, xi3, xi4, xi5, xi6, xi7])
            except:
                xi1 = pd.DataFrame(tabel[7])
                xi = xi1
        
        kop = pd.DataFrame(tabel[2])
        
        return (kop, xi)
    
    @command(name='update_nilai')    
    async def update_nilai(self, ctx, ujian_id, mapel_id, tingkat):
        
        payload = {'username' : os.getenv('username_admin'), 'password' : os.getenv('password_admin')}
        with requests.Session() as session:
            session.post(os.getenv('url_admin'), data=payload)
            resp = session.get(f'https://cbt.sman1yogya.sch.id/index.php/admin/laporan_con/daftar_hadir?ujian_id={ujian_id}&mapel_id={mapel_id}&tingkat={tingkat}')

        xi = self.update_nilai_realtime(session, ujian_id, mapel_id, tingkat)[1]
        
        await ctx.send(f'Realtime updates for exam [{tingkat}] with\n> ujian_id : `{ujian_id}`\n> mapel_id : `{mapel_id}')
        msg = await ctx.send(f"""GAMMA NASIM```{xi.query("Nama == 'GAMMA NASIM'")['Nilai'].values[0]}```\nMUHAMMAD RAFIF HANIFA```{xi.query("Nama == 'MUHAMMAD RAFIF HANIFA'")['Nilai'].values[0]}```\nMUHAMMAD RODHIYAN RIJALUL WAHID```{xi.query("Nama == 'MUHAMMAD RODHIYAN RIJALUL WAHID'")['Nilai'].values[0]}```\nRAMA ANDHIKA PRATAMA```{xi.query("Nama == 'RAMA ANDHIKA PRATAMA'")['Nilai'].values[0]}```\nHARUN```{xi.query("Nama == 'HARUN'")['Nilai'].values[0]}```\nMUSA GANI RAHMAN```{xi.query("Nama == 'MUSA GANI RAHMAN'")['Nilai'].values[0]}```\nEVANDHIKA AGNA MAULANA```{xi.query("Nama == 'EVANDHIKA AGNA MAULANA'")['Nilai'].values[0]}```\nIRFAN SURYA RAMADHAN```{xi.query("Nama == 'IRFAN SURYA RAMADHAN'")['Nilai'].values[0]}```\nMUHAMMAD DZAKY ASRAF```{xi.query("Nama == 'MUHAMMAD DZAKY ASRAF'")['Nilai'].values[0]}```\nRAYHAN ERSA NOVARDHANA```{xi.query("Nama == 'RAYHAN ERSA NOVARDHANA'")['Nilai'].values[0]}```\nHIKMAT SEJATI```{xi.query("Nama == 'HIKMAT SEJATI'")['Nilai'].values[0]}```\nTAZAKKA ARIFIN NUTRIATMA```{xi.query("Nama == 'TAZAKKA ARIFIN NUTRIATMA'")['Nilai'].values[0]}```\nLANANG BASWARA SAKHI```{xi.query("Nama == 'LANANG BASWARA SAKHI'")['Nilai'].values[0]}```\nDZAKI SENTANU NURAGUSTA```{xi.query("Nama == 'DZAKI SENTANU NURAGUSTA'")['Nilai'].values[0]}```\nRIZQI ILHAM MAULANA```{xi.query("Nama == 'RIZQI ILHAM MAULANA'")['Nilai'].values[0]}```\nALVINENDRA TRIAJI WIBOWO```{xi.query("Nama == 'ALVINENDRA TRIAJI WIBOWO'")['Nilai'].values[0]}```\n*last update on **{datetime.datetime.now(tz=tz.gettz("Asia/Jakarta"))}** *""")
        tm_start = time.time()
        while time.time() < (tm_start + 7200):
            await sleep(1)
            if xi.equals(self.update_nilai_realtime(session, ujian_id, mapel_id, tingkat)[1]) == False:
                await msg.edit(f"""GAMMA NASIM```{xi.query("Nama == 'GAMMA NASIM'")['Nilai'].values[0]}```\nMUHAMMAD RAFIF HANIFA```{xi.query("Nama == 'MUHAMMAD RAFIF HANIFA'")['Nilai'].values[0]}```\nMUHAMMAD RODHIYAN RIJALUL WAHID```{xi.query("Nama == 'MUHAMMAD RODHIYAN RIJALUL WAHID'")['Nilai'].values[0]}```\nRAMA ANDHIKA PRATAMA```{xi.query("Nama == 'RAMA ANDHIKA PRATAMA'")['Nilai'].values[0]}```\nHARUN```{xi.query("Nama == 'HARUN'")['Nilai'].values[0]}```\nMUSA GANI RAHMAN```{xi.query("Nama == 'MUSA GANI RAHMAN'")['Nilai'].values[0]}```\nEVANDHIKA AGNA MAULANA```{xi.query("Nama == 'EVANDHIKA AGNA MAULANA'")['Nilai'].values[0]}```\nIRFAN SURYA RAMADHAN```{xi.query("Nama == 'IRFAN SURYA RAMADHAN'")['Nilai'].values[0]}```\nMUHAMMAD DZAKY ASRAF```{xi.query("Nama == 'MUHAMMAD DZAKY ASRAF'")['Nilai'].values[0]}```\nRAYHAN ERSA NOVARDHANA```{xi.query("Nama == 'RAYHAN ERSA NOVARDHANA'")['Nilai'].values[0]}```\nHIKMAT SEJATI```{xi.query("Nama == 'HIKMAT SEJATI'")['Nilai'].values[0]}```\nTAZAKKA ARIFIN NUTRIATMA```{xi.query("Nama == 'TAZAKKA ARIFIN NUTRIATMA'")['Nilai'].values[0]}```\nLANANG BASWARA SAKHI```{xi.query("Nama == 'LANANG BASWARA SAKHI'")['Nilai'].values[0]}```\nDZAKI SENTANU NURAGUSTA```{xi.query("Nama == 'DZAKI SENTANU NURAGUSTA'")['Nilai'].values[0]}```\nRIZQI ILHAM MAULANA```{xi.query("Nama == 'RIZQI ILHAM MAULANA'")['Nilai'].values[0]}```\nALVINENDRA TRIAJI WIBOWO```{xi.query("Nama == 'ALVINENDRA TRIAJI WIBOWO'")['Nilai'].values[0]}```\n*last update on **{datetime.datetime.now(tz=tz.gettz("Asia/Jakarta"))}** *""")
    
def setup(bot):
    bot.add_cog(Presensi(bot))