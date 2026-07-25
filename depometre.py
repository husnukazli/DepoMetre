import streamlit as st
from supabase import create_client, Client
import pandas as pd
import os
import uuid
import time
import math
from fpdf import FPDF
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# ==========================================
# 1. SUPABASE BAĞLANTISI VE AYARLAR
# ==========================================
st.set_page_config(page_title="Arces Mühendislik - Konfigüratör", page_icon="❄️", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    .stApp > header {display: none !important;}
    [data-testid="stHeader"] {display: none !important;}
    .block-container {padding-top: 2rem !important; margin-top: 0 !important;}
    
    .stDataFrame {font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;}
    h1, h2, h3 {color: #0284c7; font-weight: 600;}
    
    .fiyat-gizli {color: #b45309; font-weight: 500; font-size: 0.85em; background-color: #fef3c7; padding: 4px 10px; border-radius: 6px; border: 1px solid #fde68a;}
    
    .auth-kutu {border: 1px solid #ddd; padding: 20px; border-radius: 10px; background-color: #f8fafc; margin-bottom: 20px;}
    .info-kutu {border: 1px solid #ddd; padding: 20px; border-radius: 10px; background-color: #f0f9ff; margin-bottom: 20px;}
    
    .tooltip {
        position: relative;
        display: inline-block;
        cursor: help;
        color: #0369a1;
        font-weight: bold;
        border-bottom: 1px dashed #0369a1;
    }
    .tooltip .tooltiptext {
        visibility: hidden;
        width: 260px;
        background-color: #1e293b;
        color: #f8fafc;
        text-align: left;
        border-radius: 8px;
        padding: 12px;
        position: absolute;
        z-index: 100;
        bottom: 125%;
        left: 50%;
        margin-left: -130px;
        opacity: 0;
        transition: opacity 0.3s;
        font-size: 0.85em;
        line-height: 1.5;
        font-weight: normal;
        box-shadow: 0px 4px 6px rgba(0,0,0,0.3);
    }
    .tooltip .tooltiptext::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -6px;
        border-width: 6px;
        border-style: solid;
        border-color: #1e293b transparent transparent transparent;
    }
    .tooltip:hover .tooltiptext {
        visibility: visible;
        opacity: 1;
    }
    .custom-info-box {
        border-left: 4px solid #3b82f6; 
        background-color: #eff6ff; 
        padding: 15px; 
        border-radius: 4px; 
        margin-bottom: 10px; 
        font-family: sans-serif;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_supabase():
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    return create_client(url, key)

supabase = init_supabase()

# -- AKILLI KUR YÖNETİMİ --
if 'guncel_kur' not in st.session_state:
    st.session_state['guncel_kur'] = 38.50  

def euro_kurunu_guncelle():
    try:
        response = requests.get("https://www.tcmb.gov.tr/kurlar/today.xml", timeout=5)
        tree = ET.fromstring(response.content)
        for currency in tree.findall('Currency'):
            if currency.get('CurrencyCode') == 'EUR':
                yeni_kur = float(currency.find('ForexSelling').text)
                st.session_state['guncel_kur'] = yeni_kur 
                break
    except:
        pass 

if 'kur_cekildi_mi' not in st.session_state:
    euro_kurunu_guncelle()
    st.session_state['kur_cekildi_mi'] = True

GUNCEL_KUR_EUR = st.session_state['guncel_kur']

if 'sepet' not in st.session_state: st.session_state['sepet'] = []
if 'kullanici_rol' not in st.session_state: st.session_state['kullanici_rol'] = 'ziyaretci' 
if 'kullanici_email' not in st.session_state: st.session_state['kullanici_email'] = ''
if 'oneri_sepete_eklendi' not in st.session_state: st.session_state['oneri_sepete_eklendi'] = False
if 'hesaplama_yapildi' not in st.session_state: st.session_state['hesaplama_yapildi'] = False

is_logged_in = st.session_state['kullanici_rol'] in ['bayi', 'admin']
is_admin = st.session_state['kullanici_rol'] == 'admin'

# --- YARDIMCI FİYAT HESAPLAMA ---
def get_gercek_fiyat_tl(urun):
    birim = urun.get("para_birimi")
    if not birim: 
        birim = "EUR" 
        
    fiyat_degeri = float(urun.get("fiyat") or 0.0)
    
    if birim == "EUR":
        return fiyat_degeri * GUNCEL_KUR_EUR
    else:
        return fiyat_degeri

teknik_sozluk = {
    "Bitzer": "Soğutucu Akışkan: R404A/R448A<br>Voltaj: 380-420V / 50Hz / 3Ph<br>Yağ Tipi: BSE32 (POE)<br>Menşei: Almanya",
    "Copeland": "Soğutucu Akışkan: R404A/R449A<br>Voltaj: 380-420V / 50Hz / 3Ph<br>Kompresör Tipi: Scroll<br>Menşei: ABD/Avrupa",
    "Frascold": "Soğutucu Akışkan: R404A/R448A<br>Voltaj: 400V / 50Hz / 3Ph<br>Yağ Tipi: POE<br>Menşei: İtalya",
    "Guntner": "Gövde: Alüminyum/Galvaniz<br>Fan Voltajı: 230V / 1Ph<br>Defrost: Elektrikli (Standart)<br>Menşei: Almanya",
    "Karyer": "Gövde: Alüminyum<br>Fan Voltajı: 230V / 1Ph<br>Defrost: Elektrikli (Standart)<br>Menşei: Türkiye",
    "Arces PUR": "Yoğunluk: 40-42 kg/m³<br>Yüzey: Boyalı Galvaniz Sac<br>Kilit Sistemi: Eksantrik Kilitli",
    "Arces Termal": "Kasa: Alüminyum/PVC<br>İzolasyon: 40-42 kg/m³ PUR<br>Aksesuar: EPDM Conta"
}

def get_teknik_detay(marka, kw=None):
    for key, value in teknik_sozluk.items():
        if key.lower() in str(marka).lower(): return value
    if kw:
        hp_degeri = float(kw) * 1.36
        ek_bilgi = f"<br>Kapasite: {kw} kW ({hp_degeri:.1f} HP)"
    else:
        ek_bilgi = ""
    return f"Standart Endüstriyel Cihaz<br>Marka: {marka}{ek_bilgi}"

def render_tooltip_box(kategori, marka, model, detay_html, extra_text=""):
    html = f"""
    <div class='custom-info-box'>
        <strong>{kategori}:</strong> 
        <span class='tooltip'>{marka} {model}
            <span class='tooltiptext'>{detay_html}</span>
        </span>
        {extra_text}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ==========================================
# 2. PDF VE SEPET FONKSİYONLARI
# ==========================================
def create_pdf(sepet_verisi, toplam):
    pdf = FPDF()
    pdf.add_page()
    has_font = os.path.exists("arial.ttf")
    if has_font:
        pdf.add_font("ArialTR", "", "arial.ttf", uni=True)
        pdf.add_font("ArialTR_B", "B", "arial.ttf", uni=True)
    try:
        if os.path.exists("logo.png"): pdf.image("logo.png", x=10, y=8, w=40)
    except: pass 
        
    pdf.set_font("ArialTR_B" if has_font else "Arial", "B", 20)
    pdf.cell(0, 10, txt="ARCES MUHENDISLIK", ln=True, align='C')
    pdf.set_font("ArialTR" if has_font else "Arial", "", 12)
    pdf.cell(0, 6, txt="Soguk Hava Deposu Konfigurasyon Teklifi", ln=True, align='C')
    pdf.cell(0, 6, txt="Web: www.arcesmuhendislik.com", ln=True, align='C')
    pdf.ln(15)
        
    pdf.set_font("ArialTR_B" if has_font else "Arial", "B", 12)
    pdf.cell(40, 10, txt="Kategori", border=1)
    pdf.cell(110, 10, txt="Marka / Model", border=1)
    pdf.cell(40, 10, txt="Fiyat (TL)", border=1, ln=True)
    
    pdf.set_font("ArialTR" if has_font else "Arial", "", 12)
    for index, row in sepet_verisi.iterrows():
        pdf.cell(40, 10, txt=str(row['Kategori'])[:15], border=1)
        pdf.cell(110, 10, txt=str(row['Marka/Model'])[:45], border=1)
        pdf.cell(40, 10, txt=f"{row['Fiyat']:,.2f}", border=1, ln=True)
        
    pdf.ln(10)
    pdf.set_font("ArialTR_B" if has_font else "Arial", "B", 14)
    pdf.cell(0, 10, txt=f"Genel Toplam: {toplam:,.2f} TL + KDV", ln=True, align='R')
    pdf.set_font("ArialTR" if has_font else "Arial", "", 10)
    pdf.cell(0, 10, txt=f"Not: Bu teklif {datetime.now().strftime('%d.%m.%Y')} tarihli kur (1 EUR = {GUNCEL_KUR_EUR:.2f} TL) ile hazirlanmistir.", ln=True, align='R')
    return bytes(pdf.output())

def sepetten_cikar(uid):
    st.session_state['sepet'] = [item for item in st.session_state['sepet'] if item.get('sepet_id') != uid]

# ==========================================
# 3. TERMODİNAMİK HESAPLAMA MOTORU 
# ==========================================
def hesapla_sogutma_yuku(en, boy, yukseklik, t_dis, t_ic, panel_kalinlik, urun_tipi, urun_miktar_kg, kapi_acilis, db):
    panel = next((p for p in db["paneller"] if str(p["kalinlik_mm"]) == str(panel_kalinlik)), None)
    if panel is None: return None
        
    u_degeri = float(panel["u_degeri"])
    zemin_alani = en * boy
    duvar_tavan_alani = (2 * en * yukseklik) + (2 * boy * yukseklik) + (en * boy)
    
    q_duvar_tavan = u_degeri * duvar_tavan_alani * (t_dis - t_ic) * 24 / 1000
    q_zemin = u_degeri * zemin_alani * (15 - t_ic) * 24 / 1000 
    q_iletim = q_duvar_tavan + q_zemin
    
    urun = db["urun_verileri"][urun_tipi]
    q_urun_duyulur = urun_miktar_kg * float(urun["cp"]) * (t_dis - t_ic) / 3600
    q_urun_solunum = (urun_miktar_kg * float(urun["solunum_kj_kg"])) / 3600
    q_urun_toplam = q_urun_duyulur + q_urun_solunum
    
    kisi_sayisi = 1 if zemin_alani < 20 else 2
    q_ic = ((kisi_sayisi * 4 * 270) / 1000) + ((math.ceil(zemin_alani / 10) * 4 * 100) / 1000)
    
    degisim_katsayisi = {"Düşük": 3, "Orta": 5, "Yüksek": 8}[kapi_acilis]
    q_infiltrasyon = degisim_katsayisi * (en * boy * yukseklik) * 2 * (t_dis - t_ic) / 3600
    
    toplam_gunluk_kwh = q_iletim + q_urun_toplam + q_ic + q_infiltrasyon + ((q_iletim + q_urun_toplam) * 0.15)
    return {
        "q_iletim": q_iletim, "q_urun": q_urun_toplam, "q_infiltrasyon": q_infiltrasyon,
        "toplam_kwh": toplam_gunluk_kwh, "gerekli_kw": (toplam_gunluk_kwh * 1.20) / 16.0,
        "zemin_alani": zemin_alani, "toplam_panel_m2": zemin_alani * 2 + duvar_tavan_alani
    }

# ==========================================
# 4. EN ÜST ALAN: GİRİŞ 
# ==========================================
st.markdown("<div class='auth-kutu'>", unsafe_allow_html=True)
col_logo, col_auth = st.columns([1, 2])

with col_logo:
    if os.path.exists("logo.png"): st.image("logo.png", width=250)
    else: st.markdown("## ARCES MÜHENDİSLİK")

with col_auth:
    if not is_logged_in:
        auth_sekmeler = st.tabs(["Giriş Yap", "Kayıt Ol", "Şifremi Unuttum"])
        with auth_sekmeler[0]:
            col_g1, col_g2, col_g3 = st.columns([2, 2, 1])
            g_email = col_g1.text_input("E-Posta", key="g_email", label_visibility="collapsed", placeholder="E-Posta Adresiniz")
            g_sifre = col_g2.text_input("Şifre", type="password", key="g_sifre", label_visibility="collapsed", placeholder="Şifreniz")
            if col_g3.button("Giriş Yap", use_container_width=True):
                try:
                    user_req = supabase.table("kullanicilar").select("*").eq("email", g_email.strip().lower()).eq("sifre", g_sifre.strip()).execute()
                    if user_req.data and user_req.data[0].get('onayli_mi', False):
                        st.session_state['kullanici_rol'] = user_req.data[0].get('rol', 'bayi')
                        st.session_state['kullanici_email'] = user_req.data[0]['email']
                        st.rerun()
                    else: st.error("Hatalı giriş veya onay bekleyen hesap.")
                except: st.error("Bağlantı hatası.")
        with auth_sekmeler[1]:
            col_k1, col_k2, col_k3 = st.columns([2, 2, 1])
            k_email = col_k1.text_input("E-Posta", key="k_email", label_visibility="collapsed", placeholder="E-Posta")
            k_sifre = col_k2.text_input("Şifre", type="password", key="k_sifre", label_visibility="collapsed", placeholder="Şifre")
            if col_k3.button("Kayıt Ol", use_container_width=True):
                try:
                    supabase.table("kullanicilar").insert({"email": k_email.strip().lower(), "sifre": k_sifre.strip()}).execute()
                    st.success("Kayıt başarılı! Onay bekleniyor.")
                except: st.error("Bu e-posta zaten var.")
        with auth_sekmeler[2]:
            st.info("Yöneticiye şifre sıfırlama talebi gönderebilirsiniz.")
    else:
        st.success(f"Hoş geldiniz, {st.session_state['kullanici_email']} ({st.session_state['kullanici_rol'].upper()})")
        if st.button("🚪 Çıkış Yap", type="secondary"):
            st.session_state['kullanici_rol'] = 'ziyaretci'
            st.session_state['kullanici_email'] = ''
            st.session_state['sepet'] = []
            st.session_state['hesaplama_yapildi'] = False
            st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

st.info(f"💶 **Güncel Euro Kuru:** 1 EUR = {GUNCEL_KUR_EUR:.4f} TL")

# ==========================================
# 5. VERİTABANI ÖN YÜKLEME 
# ==========================================
@st.cache_data(ttl=600)
def veritabani_cek():
    try:
        prc = supabase.table("parcalar").select("*").execute().data 
        return {
            "paneller": supabase.table("paneller").select("*").execute().data, 
            "urun_verileri": {i["urun_tipi"]: {"cp": i["cp"], "solunum_kj_kg": i["solunum_kj_kg"]} for i in supabase.table("urun_verileri").select("*").execute().data}, 
            "parcalar_db": prc,
            "kompresorler": [p for p in prc if str(p.get("tip")).lower() == "kompresor"],
            "evaporatorler": [p for p in prc if str(p.get("tip")).lower() == "evaporator"],
            "panolar": [p for p in prc if str(p.get("tip")).lower() in ["pano", "elektrik panosu", "kumanda panosu"]]
        }
    except: return None
db = veritabani_cek()

# ==========================================
# 6. ANA EKRAN YÖNETİMİ
# ==========================================
if db:
    ana_sekmeler = ["İleri Düzey Konfigüratör"]
    if is_admin: ana_sekmeler.append("⚙️ Admin Paneli")
    secilen_ana_sekme = st.tabs(ana_sekmeler)

    with secilen_ana_sekme[0]:
        if not is_logged_in:
            st.warning("⚠️ **MİSAFİR MODU:** Sistemi analiz edip parçaları seçebilirsiniz. Fiyatları ve teklifleri görmek için üye girişi yapmalısınız.")
            
        st.markdown("<div class='info-kutu'><h3 style='text-align: center;'>1. Adım: Termodinamik Analiz ve Otomatik Öneri</h3></div>", unsafe_allow_html=True)
        
        c_sol, c_sag = st.columns(2)
        with c_sol:
            il_sicakliklari = {"İzmir": 35.0, "Antalya": 38.0, "Adana": 37.0, "İstanbul": 33.0, "Ankara": 32.0, "Zonguldak": 31.0, "Diğer": 35.0}
            secilen_il = st.selectbox("Projenin Uygulanacağı İl", list(il_sicakliklari.keys()))
            t_dis = st.number_input("Dış Ortam Sıcaklığı (°C)", value=il_sicakliklari[secilen_il], step=1.0)
            
            en = st.number_input("En (Metre)", min_value=1.0, value=4.0, step=0.5)
            boy = st.number_input("Boy (Metre)", min_value=1.0, value=5.0, step=0.5)
            yukseklik = st.number_input("Yükseklik (Metre)", min_value=2.0, value=2.5, step=0.1)
            
            bolme_istiyor_mu = st.checkbox("🔲 Bu depoyu ortadan ikiye bölmek (ara duvar eklemek) istiyorum")
            bolme_yonu = "Yok"
            if bolme_istiyor_mu:
                bolme_yonu = st.radio("Bölme duvarı hangi yönde olacak?", ["Enine Böl (Kısa kenarı keser)", "Boyuna Böl (Uzun kenarı keser)"])
                
        with c_sag:
            t_ic = st.selectbox("Hedef Depo Sıcaklığı (°C)", [4.0, -18.0])
            urun_tipi = st.selectbox("Depolanacak Ürün Cinsi", list(db["urun_verileri"].keys()))
            urun_miktar_kg = st.number_input("Günlük Ürün Girişi (Kg/Gün)", min_value=0, value=2000, step=500)
            kapi_acilis = st.selectbox("Kapı Açılma Frekansı", ["Düşük", "Orta", "Yüksek"], index=1)
            tavsiye_panel = 80 if t_ic > 0 else 120
            panel_secenekleri = [p["kalinlik_mm"] for p in db["paneller"]]
            secilen_panel_kalinlik = st.selectbox("İzolasyon Paneli (mm)", panel_secenekleri, index=panel_secenekleri.index(tavsiye_panel) if tavsiye_panel in panel_secenekleri else 0)

        btn_col1, btn_col2 = st.columns([2, 8])
        with btn_col1:
            if st.button("Sistem Hesapla ve Öner", type="primary"): 
                st.session_state['hesaplama_yapildi'] = True
                st.session_state['oneri_sepete_eklendi'] = False
        with btn_col2:
            if st.session_state.get('hesaplama_yapildi', False):
                if st.button("🧹 Hesaplamayı Temizle"):
                    st.session_state['hesaplama_yapildi'] = False
                    st.session_state['oneri_sepete_eklendi'] = False
                    st.rerun()
            
        if st.session_state.get('hesaplama_yapildi', False):
            sonuclar = hesapla_sogutma_yuku(en, boy, yukseklik, t_dis, t_ic, secilen_panel_kalinlik, urun_tipi, urun_miktar_kg, kapi_acilis, db)
            
            if sonuclar:
                gerekli_kw = sonuclar['gerekli_kw']
                gerekli_hp = gerekli_kw * 1.36
                st.success(f"### ⚙️ Gerekli Soğutma Kapasitesi: {gerekli_kw:.2f} kW ({gerekli_hp:.1f} HP)")
                
                kapi_sayisi = 2 if bolme_istiyor_mu else 1
                ekstra_duvar_alani = 0.0
                if bolme_istiyor_mu:
                    ekstra_duvar_alani = (en * yukseklik) if "Enine" in bolme_yonu else (boy * yukseklik)

                # --- KOMPRESÖR SEÇİMİ VE ÇOKLU SİSTEM MANTIĞI ---
                komp = None
                komp_carpani = 1
                
                uygun_komp_tek = [k for k in db["kompresorler"] if float(k.get("kapasite_kw", 0)) >= gerekli_kw]
                if uygun_komp_tek:
                    komp = min(uygun_komp_tek, key=lambda x: float(x["kapasite_kw"]))
                    komp_carpani = 1
                else:
                    yarim_yuk = gerekli_kw / 2.0
                    uygun_komp_ikili = [k for k in db["kompresorler"] if float(k.get("kapasite_kw", 0)) >= yarim_yuk]
                    if uygun_komp_ikili:
                        komp = min(uygun_komp_ikili, key=lambda x: float(x["kapasite_kw"]))
                        komp_carpani = 2
                    elif db["kompresorler"]:
                        komp = max(db["kompresorler"], key=lambda x: float(x["kapasite_kw"]))
                        komp_carpani = math.ceil(gerekli_kw / float(komp.get("kapasite_kw", 1)))

                # --- EVAPORATÖR SEÇİMİ ---
                temel_evap_carpani = 2 if bolme_istiyor_mu else 1
                evap_carpani = max(temel_evap_carpani, komp_carpani)

                uygun_evap = [e for e in db["evaporatorler"] if float(e.get("min_kw", 0)) <= gerekli_kw <= float(e.get("max_kw", 999))]
                evap = uygun_evap[0] if uygun_evap else (db["evaporatorler"][0] if db["evaporatorler"] else None)
                
                # --- ELEKTRİK PANOSU SEÇİMİ ---
                pano = db["panolar"][0] if db["panolar"] else None

                panel_veri = next((p for p in db["paneller"] if str(p["kalinlik_mm"]) == str(secilen_panel_kalinlik)), None)
                
                brut_panel_m2 = (sonuclar['toplam_panel_m2'] + ekstra_duvar_alani) * 1.08
                kapi_tipi = "Sürgülü Kapı (120x200)" if sonuclar['zemin_alani'] > 20 else "Menteşeli Çarpma Kapı (90x190)"

                st.write("#### 🛠️ Önerilen Bileşenler")
                onerilen_sepet_listesi = []
                
                if komp:
                    m, md = komp.get('marka',''), komp.get('model_adi','')
                    komp_tek_kw = float(komp.get('kapasite_kw', 0))
                    toplam_komp_kw = komp_tek_kw * komp_carpani
                    toplam_komp_hp = toplam_komp_kw * 1.36 
                    
                    komp_baslik = f"{m} - {md}" if komp_carpani == 1 else f"{m} - {md} ({komp_carpani} Adet)"
                    toplam_komp_fiyat = get_gercek_fiyat_tl(komp) * komp_carpani
                    
                    render_tooltip_box("Kompresör Grubu", m, komp_baslik, get_teknik_detay(m, komp_tek_kw), f" | Toplam Kapasite: {toplam_komp_kw:.1f} kW ({toplam_komp_hp:.1f} HP) - {komp_carpani} Adet")
                    onerilen_sepet_listesi.append({"Kategori": "Kompresör", "Marka/Model": komp_baslik, "Fiyat": toplam_komp_fiyat})
                
                if evap:
                    m, md = evap.get('marka',''), evap.get('model_adi','')
                    render_tooltip_box("Evaporatör", m, md, get_teknik_detay(m), f" | {evap_carpani} Adet")
                    evap_toplam_fiyat = get_gercek_fiyat_tl(evap) * evap_carpani
                    evap_baslik = f"{m} - {md}" if evap_carpani == 1 else f"{m} - {md} ({evap_carpani} Adet)"
                    onerilen_sepet_listesi.append({"Kategori": "Evaporatör", "Marka/Model": evap_baslik, "Fiyat": evap_toplam_fiyat})

                if pano:
                    m, md = pano.get('marka',''), pano.get('model_adi','')
                    render_tooltip_box("Elektrik Panosu", m, md, get_teknik_detay(m), " | 1 Adet Kumanda ve Güç Panosu")
                    pano_fiyat = get_gercek_fiyat_tl(pano)
                    onerilen_sepet_listesi.append({"Kategori": "Elektrik Panosu", "Marka/Model": f"{m} - {md}", "Fiyat": pano_fiyat})
                
                if panel_veri:
                    panel_ad = f"{secilen_panel_kalinlik} mm PUR/PIR"
                    duvar_metni = "(Fire ve Ara Duvar Dahil)" if bolme_istiyor_mu else "(Fire Dahil)"
                    render_tooltip_box("Panel", "Arces PUR", panel_ad, get_teknik_detay("Arces PUR"), f" | Miktar: {brut_panel_m2:.1f} m² {duvar_metni}")
                    onerilen_sepet_listesi.append({"Kategori": "İzolasyon Paneli", "Marka/Model": f"{secilen_panel_kalinlik} mm Panel ({brut_panel_m2:.1f} m²)", "Fiyat": float(panel_veri["fiyat_eur_m2"]) * brut_panel_m2 * GUNCEL_KUR_EUR})
                
                kapi_fiyat_tl = ((450 if "Sürgülü" in kapi_tipi else 325) + (50 if t_ic < 0 else 0)) * GUNCEL_KUR_EUR * kapi_sayisi
                kapi_baslik = kapi_tipi if kapi_sayisi == 1 else f"{kapi_tipi} ({kapi_sayisi} Adet)"
                render_tooltip_box("Kapı", "Arces Termal", kapi_baslik, get_teknik_detay("Arces Termal"))
                onerilen_sepet_listesi.append({"Kategori": "Kapı", "Marka/Model": kapi_baslik, "Fiyat": kapi_fiyat_tl})
                
                st.write("")
                
                if not st.session_state.get('oneri_sepete_eklendi', False):
                    if st.button("🛒 BU SİSTEMİ SEPETE EKLE", type="primary"):
                        for urun in onerilen_sepet_listesi:
                            urun["sepet_id"] = str(uuid.uuid4())
                            st.session_state['sepet'].append(urun)
                        st.session_state['oneri_sepete_eklendi'] = True
                        st.rerun()
                else:
                    st.warning("✅ **Bu sistem şu anda sepetinizde bulunuyor.**")
                    if st.button("Yine de İkinci Kez Ekle", type="secondary"):
                        for urun in onerilen_sepet_listesi:
                            urun["sepet_id"] = str(uuid.uuid4())
                            st.session_state['sepet'].append(urun)
                        st.success("Sistem ikinci kez sepete eklendi!")

        st.divider()
        
        # --- MANUEL PARÇA SEÇİMİ ---
        st.markdown("<div class='info-kutu'><h3 style='text-align: center;'>2. Adım: Manuel Katalog</h3></div>", unsafe_allow_html=True)
        
        kategori_isimleri = list(set([str(p.get("tip", "Diger")).capitalize() for p in db["parcalar_db"] if p.get("tip")]))
        if kategori_isimleri:
            sekmeler_kat = st.tabs(kategori_isimleri)
            for index, sekme in enumerate(sekmeler_kat):
                with sekme:
                    uygun_parcalar = [p for p in db["parcalar_db"] if str(p.get("tip", "")).lower() == kategori_isimleri[index].lower()]
                    for parca in uygun_parcalar:
                        p_birim = parca.get("para_birimi")
                        if not p_birim:
                            p_birim = "EUR" 
                            
                        val = float(parca.get("fiyat") or 0.0)
                        
                        if p_birim == "EUR":
                            tl_karsiligi = val * GUNCEL_KUR_EUR
                            fiyat_metni = f"{val:,.2f} EUR ({tl_karsiligi:,.2f} TL)"
                            sepet_fiyati = tl_karsiligi 
                        else:
                            fiyat_metni = f"{val:,.2f} TL"
                            sepet_fiyati = val

                        p_kw = float(parca.get("kapasite_kw") or 0.0)
                        hp_metni = f" ({p_kw * 1.36:.1f} HP)" if p_kw > 0 else ""

                        p_col1, p_col2, p_col3 = st.columns([5, 3, 2])
                        p_col1.write(f"**{parca.get('marka', 'Markasız')} - {parca.get('model_adi', 'İsimsiz')}{hp_metni}**")
                        
                        if is_logged_in: p_col2.write(f"Fiyat: {fiyat_metni}")
                        else: p_col2.markdown("<span class='fiyat-gizli'>🔒 Fiyatlandırma için oturum açın</span>", unsafe_allow_html=True)
                        
                        if p_col3.button("Ekle", key=f"ekle_{parca['id']}"):
                            st.session_state['sepet'].append({
                                "sepet_id": str(uuid.uuid4()), "Kategori": kategori_isimleri[index],
                                "Marka/Model": f"{parca.get('marka', '')} - {parca.get('model_adi', '')}", "Fiyat": sepet_fiyati
                            })
                            st.rerun()

        st.divider()

        # --- SEPET ÖZETİ ---
        st.header("🛒 3. Adım: Proje Sepeti")
        if st.session_state['sepet']:
            for item in st.session_state['sepet']:
                s_col1, s_col2, s_col3, s_col4 = st.columns([2, 5, 3, 2])
                s_col1.write(item['Kategori'])
                s_col2.write(item['Marka/Model'])
                if is_logged_in: s_col3.write(f"{item['Fiyat']:,.2f} TL")
                else: s_col3.markdown("<span class='fiyat-gizli'>🔒 Fiyatlandırma için oturum açın</span>", unsafe_allow_html=True)
                s_col4.button("❌ Çıkar", key=f"sil_{item['sepet_id']}", on_click=sepetten_cikar, args=(item['sepet_id'],))
                
            st.write("---")
            df_sepet = pd.DataFrame(st.session_state['sepet'])
            toplam_tutar = df_sepet["Fiyat"].sum()
            
            if is_logged_in:
                st.success(f"### 💰 Toplam Maliyet: {toplam_tutar:,.2f} TL")
                col_pdf, col_temizle = st.columns([1, 1])
                with col_pdf:
                    try: st.download_button("📄 PDF İndir", create_pdf(df_sepet, toplam_tutar), "Teklif.pdf", "application/pdf", use_container_width=True)
                    except: pass
                with col_temizle:
                    if st.button("Tüm Sepeti Temizle", use_container_width=True): 
                        st.session_state['sepet'] = []
                        st.session_state['oneri_sepete_eklendi'] = False
                        st.rerun()
            else:
                st.error("🔒 Sistemin toplam maliyetini görmek ve resmi PDF teklifini almak için lütfen yukarıdan kayıt olun veya giriş yapın.")
                if st.button("Sepeti Temizle"): 
                    st.session_state['sepet'] = []
                    st.session_state['oneri_sepete_eklendi'] = False
                    st.rerun()
        else:
            st.info("Sepetinizde parça yok.")

    # ----------------- ADMIN PANELİ -----------------
    if is_admin:
        with secilen_ana_sekme[1]:
            st.header("⚙️ Yönetici (Admin) Paneli")
            
            admin_tab1, admin_tab2, admin_tab3, admin_tab4, admin_tab5 = st.tabs([
                "👥 Kullanıcı Onayları", 
                "🔑 Şifre Talepleri",
                "🗂️ Müşteri Teklif Arşivi", 
                "➕ Yeni Ürün Ekle", 
                "✏️ Katalog Yönetimi"
            ])
            
            with admin_tab1:
                bekleyenler = supabase.table("kullanicilar").select("*").eq("onayli_mi", False).execute().data
                if bekleyenler:
                    for usr in bekleyenler:
                        u_col1, u_col2 = st.columns([3,1])
                        u_col1.write(f"📧 **{usr['email']}**")
                        if u_col2.button("✅ Onayla", key=f"onay_{usr['id']}"):
                            supabase.table("kullanicilar").update({"onayli_mi": True}).eq("id", usr['id']).execute()
                            st.rerun()
                else:
                    st.info("Onay bekleyen yeni kayıt yok.")
                    
            with admin_tab2:
                sifre_isteyenler = supabase.table("kullanicilar").select("*").eq("sifre_sifirlama_istendi", True).execute().data
                if sifre_isteyenler:
                    for usr in sifre_isteyenler:
                        s_col1, s_col2 = st.columns([3, 1])
                        s_col1.write(f"📧 **{usr['email']}** şifre sıfırlama bekliyor.")
                        if s_col2.button("Geçici Şifre Ata", key=f"sifirla_{usr['id']}"):
                            supabase.table("kullanicilar").update({"sifre": "arces1234", "sifre_sifirlama_istendi": False}).eq("id", usr['id']).execute()
                            st.rerun()
                else:
                    st.info("Şifre sıfırlama talebi bulunmuyor.")
                    
            with admin_tab3:
                st.subheader("🗂️ Geçmiş Müşteri Teklifleri Arşivi")
                try:
                    teklifler_data = supabase.table("teklifler").select("*").execute().data
                    if teklifler_data:
                        df_teklif = pd.DataFrame(teklifler_data)
                        st.dataframe(df_teklif, use_container_width=True)
                    else:
                        st.info("Henüz veritabanına kaydedilmiş bir teklif bulunmuyor.")
                except Exception as e:
                    st.error("Veritabanına bağlanırken bir hata oluştu veya 'teklifler' tablosu eksik.")

            with admin_tab4:
                st.subheader("Kataloğa Yeni Cihaz Ekle")
                mevcut_tipler = list(set([str(p.get("tip", "diger")).capitalize() for p in db["parcalar_db"] if p.get("tip")]))
                mevcut_markalar = list(set([str(p.get("marka", "Markasız")).capitalize() for p in db["parcalar_db"] if p.get("marka")]))
                
                with st.form("yeni_urun_formu"):
                    col_t1, col_t2 = st.columns(2)
                    secilen_tip = col_t1.selectbox("Kategori Seçimi", ["Listeden Seç..."] + mevcut_tipler)
                    yeni_tip = col_t2.text_input("Veya Yeni Kategori Yaz", placeholder="Örn: Fan, Pano vb.")
                    
                    col_m1, col_m2 = st.columns(2)
                    secilen_marka = col_m1.selectbox("Marka Seçimi", ["Listeden Seç..."] + mevcut_markalar)
                    yeni_marka = col_m2.text_input("Veya Yeni Marka Yaz", placeholder="Örn: X-Cooling")
                    
                    y_model = st.text_input("Model Adı", placeholder="Örn: Yeni Seri")
                    y_kw = st.number_input("Kapasite (kW) - Kapı/Panel ise 0 bırakın", min_value=0.0, step=1.0)
                    y_fiyat = st.number_input("Birim Fiyatı (Seçilen Para Birimine Göre)", min_value=0.0, step=100.0)
                    y_para_birimi = st.selectbox("Para Birimi", ["EUR", "TL"])
                    
                    if st.form_submit_button("Ürünü Kaydet"):
                        final_tip = yeni_tip.strip() if yeni_tip.strip() else (secilen_tip if secilen_tip != "Listeden Seç..." else "")
                        final_marka = yeni_marka.strip() if yeni_marka.strip() else (secilen_marka if secilen_marka != "Listeden Seç..." else "")
                        
                        if not final_tip or not final_marka or not y_model:
                            st.error("Lütfen Kategori, Marka ve Model adını eksiksiz doldurun.")
                        else:
                            supabase.table("parcalar").insert({
                                "tip": final_tip.lower(),
                                "marka": final_marka,
                                "model_adi": y_model,
                                "kapasite_kw": y_kw,
                                "fiyat": y_fiyat,
                                "para_birimi": y_para_birimi
                            }).execute()
                            st.success("✅ Yeni ürün eklendi! Önbelleği (Clear Cache) temizlediğinizde manuel katalogda belirecektir.")

            with admin_tab5:
                st.subheader("✏️ Katalog Yönetimi (Ürün Güncelle ve Sil)")
                tum_parcalar = db["parcalar_db"]
                if tum_parcalar:
                    secenekler = {f"{p.get('marka','')} - {p.get('model_adi','')}": p for p in tum_parcalar}
                    secilen_isim = st.selectbox("İşlem Yapılacak Ürünü Seçin", list(secenekler.keys()))
                    secilen_p = secenekler[secilen_isim]
                    
                    with st.form("guncelleme_formu"):
                        c_g1, c_g2 = st.columns(2)
                        yeni_marka = c_g1.text_input("Marka", value=secilen_p.get("marka", ""))
                        yeni_model = c_g2.text_input("Model", value=secilen_p.get("model_adi", ""))
                        
                        mevcut_kw = float(secilen_p.get("kapasite_kw") or 0.0)
                        yeni_kw = c_g1.number_input(f"Kapasite (kW) -> Yaklaşık {mevcut_kw * 1.36:.1f} HP", value=mevcut_kw)
                        
                        mevcut_birim = secilen_p.get("para_birimi")
                        if not mevcut_birim: mevcut_birim = "EUR"
                        
                        mevcut_fiyat = float(secilen_p.get("fiyat") or 0.0)
                        
                        yeni_fiyat = c_g2.number_input("Fiyat", value=mevcut_fiyat)
                        yeni_birim = c_g1.selectbox("Para Birimi", ["EUR", "TL"], index=0 if mevcut_birim=="EUR" else 1)
                        
                        st.write("---")
                        c_btn1, c_btn2 = st.columns(2)
                        guncelle_btn = c_btn1.form_submit_button("💾 Değişiklikleri Güncelle")
                        sil_btn = c_btn2.form_submit_button("🗑️ Ürünü Kalıcı Olarak Sil")
                        
                        if guncelle_btn:
                            update_data = {
                                "marka": yeni_marka,
                                "model_adi": yeni_model,
                                "kapasite_kw": yeni_kw,
                                "para_birimi": yeni_birim,
                                "fiyat": yeni_fiyat
                            }
                                
                            supabase.table("parcalar").update(update_data).eq("id", secilen_p["id"]).execute()
                            st.success("✅ Ürün başarıyla güncellendi! Lütfen sağ üstten 'Clear Cache' yapıp sayfayı yenileyin.")
                        
                        if sil_btn:
                            supabase.table("parcalar").delete().eq("id", secilen_p["id"]).execute()
                            st.warning("⚠️ Ürün katalogdan tamamen silindi! Lütfen 'Clear Cache' yapıp sayfayı yenileyin.")
                else:
                    st.info("Katalogda düzenlenecek parça bulunamadı.")
