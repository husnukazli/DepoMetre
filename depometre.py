import streamlit as st
from supabase import create_client, Client
import pandas as pd
import os
import uuid
from fpdf import FPDF

# ==========================================
# 1. SUPABASE BAĞLANTISI VE AYARLAR
# ==========================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Arçes Mühendislik - Konfigüratör", page_icon="❄️", layout="wide")

st.markdown("""
    <style>
    .stDataFrame {font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;}
    h1, h2, h3 {color: #0284c7; font-weight: 600;}
    .fiyat-gizli {color: #eab308; font-weight: bold;}
    </style>
""", unsafe_allow_html=True)

# Session State (Hafıza) Başlatma
if 'sepet' not in st.session_state:
    st.session_state['sepet'] = []
if 'kullanici_rol' not in st.session_state:
    st.session_state['kullanici_rol'] = 'ziyaretci' # ziyaretci, bayi, admin
if 'kullanici_email' not in st.session_state:
    st.session_state['kullanici_email'] = ''

is_logged_in = st.session_state['kullanici_rol'] in ['bayi', 'admin']
is_admin = st.session_state['kullanici_rol'] == 'admin'

# ==========================================
# 2. PDF OLUŞTURMA FONKSİYONU (ANTETLİ)
# ==========================================
def create_pdf(sepet_verisi, toplam):
    pdf = FPDF()
    pdf.add_page()
    
    # Font Yükleme
    has_font = os.path.exists("arial.ttf")
    if has_font:
        pdf.add_font("ArialTR", "", "arial.ttf", uni=True)
        pdf.add_font("ArialTR_B", "B", "arial.ttf", uni=True)
    
    # ANTET (BAŞLIK VE LOGO)
    try:
        if os.path.exists("logo.png"):
            pdf.image("logo.png", x=10, y=8, w=40)
    except:
        pass # Logo yoksa atla
        
    pdf.set_font("ArialTR_B" if has_font else "Arial", "B", 20)
    pdf.cell(0, 10, txt="ARCES MUHENDISLIK", ln=True, align='C')
    
    pdf.set_font("ArialTR" if has_font else "Arial", "", 12)
    pdf.cell(0, 6, txt="Soguk Hava Deposu Konfigurasyon Teklifi", ln=True, align='C')
    pdf.cell(0, 6, txt="Web: www.arcesmuhendislik.com", ln=True, align='C')
    pdf.ln(15)
        
    # Tablo Başlıkları
    pdf.set_font("ArialTR_B" if has_font else "Arial", "B", 12)
    pdf.cell(50, 10, txt="Kategori", border=1)
    pdf.cell(100, 10, txt="Marka / Model", border=1)
    pdf.cell(40, 10, txt="Fiyat (TL)", border=1, ln=True)
    
    # Tablo İçeriği
    pdf.set_font("ArialTR" if has_font else "Arial", "", 12)
    for index, row in sepet_verisi.iterrows():
        pdf.cell(50, 10, txt=str(row['Kategori']), border=1)
        pdf.cell(100, 10, txt=str(row['Marka/Model']), border=1)
        pdf.cell(40, 10, txt=f"{row['Fiyat']:,.2f}", border=1, ln=True)
        
    pdf.ln(10)
    pdf.set_font("ArialTR_B" if has_font else "Arial", "B", 14)
    pdf.cell(0, 10, txt=f"Genel Toplam: {toplam:,.2f} TL + KDV", ln=True, align='R')
    return bytes(pdf.output())

def sepetten_cikar(uid):
    st.session_state['sepet'] = [item for item in st.session_state['sepet'] if item.get('sepet_id') != uid]

# ==========================================
# 3. YAN MENÜ (SİDEBAR) - ÜYELİK & LOGO
# ==========================================
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.markdown("## 🏢 ARÇES MÜHENDİSLİK")
        
    st.markdown("---")
    
    if st.session_state['kullanici_rol'] == 'ziyaretci':
        st.write("🔒 **Fiyatları görmek ve teklif oluşturmak için giriş yapın.**")
        tab_giris, tab_kayit = st.tabs(["Giriş Yap", "Kayıt Ol"])
        
        with tab_giris:
            g_email = st.text_input("E-Posta", key="g_email")
            g_sifre = st.text_input("Şifre", type="password", key="g_sifre")
            if st.button("Giriş", use_container_width=True):
                user_req = supabase.table("kullanicilar").select("*").eq("email", g_email).eq("sifre", g_sifre).execute()
                if user_req.data:
                    user_data = user_req.data[0]
                    if user_data['onayli_mi']:
                        st.session_state['kullanici_rol'] = user_data['rol']
                        st.session_state['kullanici_email'] = user_data['email']
                        st.rerun()
                    else:
                        st.warning("Hesabınız henüz yönetici tarafından onaylanmamış.")
                else:
                    st.error("Hatalı e-posta veya şifre.")
                    
        with tab_kayit:
            k_email = st.text_input("E-Posta (Kayıt)")
            k_sifre = st.text_input("Şifre (Kayıt)", type="password")
            if st.button("Kayıt Ol", use_container_width=True):
                try:
                    supabase.table("kullanicilar").insert({"email": k_email, "sifre": k_sifre}).execute()
                    st.success("Kayıt başarılı! Yönetici onayından sonra giriş yapabilirsiniz.")
                except Exception as e:
                    st.error("Bu e-posta zaten kayıtlı olabilir.")
    else:
        st.success(f"Hoş geldiniz, {st.session_state['kullanici_email']}")
        st.info(f"Yetki: {st.session_state['kullanici_rol'].upper()}")
        if st.button("Çıkış Yap", use_container_width=True):
            st.session_state['kullanici_rol'] = 'ziyaretci'
            st.session_state['kullanici_email'] = ''
            st.session_state['sepet'] = []
            st.rerun()

# ==========================================
# 4. VERİTABANI ÖN YÜKLEME
# ==========================================
try:
    kategoriler_db = supabase.table("kategoriler").select("*").execute().data
    markalar_db = supabase.table("markalar").select("*").execute().data
    # Sadece 'aktif_mi' = True olan ürünleri getiriyoruz (Kaldırılmışları gizler)
    parcalar_db = supabase.table("parcalar").select("*").eq("aktif_mi", True).execute().data
    veriler_tamam = bool(kategoriler_db and parcalar_db)
except Exception as e:
    st.error(f"Veritabanı bağlantı hatası: {e}")
    veriler_tamam = False

# ==========================================
# 5. ANA EKRAN YÖNETİMİ (SEKMELER)
# ==========================================
ana_sekmeler = ["Konfigüratör"]
if is_admin:
    ana_sekmeler.append("⚙️ Admin Paneli")

secilen_ana_sekme = st.tabs(ana_sekmeler)

# ----------------- KONFİGÜRATÖR SEKMESİ -----------------
with secilen_ana_sekme[0]:
    st.title("❄️ Soğuk Hava Deposu Konfigüratörü")
    if not is_logged_in:
        st.warning("⚠️ Ziyaretçi Modundasınız: Sistem kapasitesini hesaplayabilir ve malzeme listesini oluşturabilirsiniz ancak **fiyatları görmek ve teklif (PDF) almak için üye girişi yapmalısınız.**")
        
    if veriler_tamam:
        # --- HACİM VE KAPASİTE HESABI ---
        with st.container():
            st.header("1. Hacim ve Kapasite Hesabı")
            col1, col2, col3 = st.columns(3)
            with col1: en = st.number_input("En (Metre)", min_value=1.0, value=3.0, step=0.5)
            with col2: boy = st.number_input("Boy (Metre)", min_value=1.0, value=4.0, step=0.5)
            with col3: yukseklik = st.number_input("Yükseklik (Metre)", min_value=1.0, value=2.5, step=0.5)
                
            hacim = en * boy * yukseklik
            zemin_alani = en * boy
            toplam_yuzey_alani = (2 * zemin_alani) + (2 * en * yukseklik) + (2 * boy * yukseklik)
            
            hedef_sicaklik = st.selectbox("Hedef Depo Sıcaklığı", ["+4 Derece (Soğuk)", "-18 Derece (Donuk)"])
            btu_carpan = 350 if hedef_sicaklik == "+4 Derece (Soğuk)" else 550
            gerekli_btu = int(hacim * btu_carpan)
            
            st.info(f"**Toplam Hacim:** {hacim:.2f} m³ | **Zemin:** {zemin_alani:.2f} m² | **İzolasyon Yüzeyi:** {toplam_yuzey_alani:.2f} m² \n\n **İhtiyaç:** {gerekli_btu:,} BTU/h")

            # Akıllı Kompresör Önerisi
            komp_kategori_id = next((k["id"] for k in kategoriler_db if "Kompresör" in k["kategori_adi"]), None)
            if komp_kategori_id:
                kompresorler = sorted([p for p in parcalar_db if p["kategori_id"] == komp_kategori_id and p["btu_kapasite"] > 0], key=lambda x: x["btu_kapasite"])
                if kompresorler:
                    en_iyi_secim = None
                    en_az_fazla = float('inf')
                    for komp in kompresorler:
                        for adet in [1, 2]:
                            toplam_kapasite = adet * komp["btu_kapasite"]
                            if toplam_kapasite >= gerekli_btu:
                                fazla = toplam_kapasite - gerekli_btu
                                if fazla < en_az_fazla:
                                    en_az_fazla = fazla
                                    en_iyi_secim = (komp, adet)
                    
                    if not en_iyi_secim:
                        en_iyi_secim = (kompresorler[-1], 2)
                        
                    komp, adet = en_iyi_secim
                    marka_ad = next((m["marka_adi"] for m in markalar_db if m["id"] == komp["marka_id"]), "")
                    st.success(f"💡 **Önerilen Kompresör:** {adet} Adet **{marka_ad} - {komp['model_adi']}** ({komp['btu_kapasite']:,} BTU x {adet})")

        st.divider()

        # --- PARÇA SEÇİMİ (KATALOG) ---
        st.header("2. Sistem Bileşenleri")
        kategori_isimleri = [k["kategori_adi"] for k in kategoriler_db]
        sekmeler = st.tabs(kategori_isimleri)
        
        for index, sekme in enumerate(sekmeler):
            with sekme:
                kategori_id = kategoriler_db[index]["id"]
                kategori_adi = kategoriler_db[index]["kategori_adi"]
                uygun_parcalar = [p for p in parcalar_db if p["kategori_id"] == kategori_id]
                
                if uygun_parcalar:
                    for parca in uygun_parcalar:
                        marka_adi = next((m["marka_adi"] for m in markalar_db if m["id"] == parca["marka_id"]), "Bilinmiyor")
                        gosterilecek_fiyat = float(parca['fiyat'])
                        tavsiye_etiketi = ""
                        
                        if "Panel" in kategori_adi:
                            gosterilecek_fiyat = float(parca['fiyat']) * toplam_yuzey_alani
                            tavsiye_etiketi = f"*(Toplam {toplam_yuzey_alani:.2f} m² için)*"
                        if "Kapı" in kategori_adi:
                            if (zemin_alani > 20 and "Sürgülü" in parca['model_adi']) or (zemin_alani <= 20 and "Menteşeli" in parca['model_adi']):
                                tavsiye_etiketi = "💡 **(Tavsiye Edilir)**"

                        p_col1, p_col2, p_col3, p_col4 = st.columns([4, 2, 2, 2])
                        p_col1.write(f"**{marka_adi} - {parca['model_adi']}** {tavsiye_etiketi}")
                        p_col2.write(f"Kapasite: {parca['btu_kapasite']:,} BTU" if parca["btu_kapasite"] > 0 else "")
                        
                        # LOGİN KONTROLÜ: Ziyaretçiden Fiyat Gizleme
                        if is_logged_in:
                            p_col3.write(f"Fiyat: {gosterilecek_fiyat:,.2f} TL")
                        else:
                            p_col3.markdown("<span class='fiyat-gizli'>🔒 Üye Girişi Gerekli</span>", unsafe_allow_html=True)
                        
                        if p_col4.button("Sepete Ekle", key=f"ekle_{parca['id']}"):
                            st.session_state['sepet'].append({
                                "sepet_id": str(uuid.uuid4()),
                                "Kategori": kategori_adi,
                                "Marka/Model": f"{marka_adi} - {parca['model_adi']}",
                                "Fiyat": gosterilecek_fiyat
                            })
                            st.rerun()
                else:
                    st.caption("Bu kategoride ürün bulunamadı.")

        st.divider()

        # --- SEPET ÖZETİ VE PDF ÇIKTISI ---
        st.header("3. Konfigürasyon Özeti")
        if st.session_state['sepet']:
            for item in st.session_state['sepet']:
                if 'sepet_id' not in item:
                    item['sepet_id'] = str(uuid.uuid4())
                s_col1, s_col2, s_col3, s_col4 = st.columns([3, 4, 3, 2])
                s_col1.write(item['Kategori'])
                s_col2.write(item['Marka/Model'])
                
                # Sepette de fiyat gizleme
                if is_logged_in:
                    s_col3.write(f"{item['Fiyat']:,.2f} TL")
                else:
                    s_col3.write("🔒 Gizli")
                    
                s_col4.button("❌ Çıkar", key=f"sil_{item['sepet_id']}", on_click=sepetten_cikar, args=(item['sepet_id'],))
                
            st.write("---")
            
            df_sepet = pd.DataFrame(st.session_state['sepet'])
            toplam_tutar = df_sepet["Fiyat"].sum()
            
            if is_logged_in:
                st.success(f"### 💰 Toplam Sistem Maliyeti: {toplam_tutar:,.2f} TL")
                
                col_pdf, col_temizle = st.columns([1, 1])
                with col_pdf:
                    try:
                        pdf_bytes = create_pdf(df_sepet, toplam_tutar)
                        st.download_button(
                            label="📄 PDF Olarak İndir (Arçes Teklifi)",
                            data=pdf_bytes,
                            file_name="Arces_Soguk_Oda_Teklifi.pdf",
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"PDF hatası: {e}")
                with col_temizle:
                    if st.button("Tüm Sepeti Temizle", type="secondary", use_container_width=True):
                        st.session_state['sepet'] = []
                        st.rerun()
            else:
                st.error("🔒 Sistemin toplam maliyetini görmek ve PDF Teklif alabilmek için lütfen sol menüden yönetici onaylı hesabınızla giriş yapınız.")
                if st.button("Tüm Sepeti Temizle", type="secondary", use_container_width=True):
                    st.session_state['sepet'] = []
                    st.rerun()
        else:
            st.info("Sepetinizde henüz bir parça bulunmuyor.")

# ----------------- ADMİN PANELİ SEKMESİ -----------------
if is_admin:
    with secilen_ana_sekme[1]:
        st.header("⚙️ Yönetici (Admin) Paneli")
        admin_tab1, admin_tab2 = st.tabs(["Kullanıcı Onayları", "Ürün Yönetimi (Gizle/Kaldır)"])
        
        # 1. KULLANICI ONAYLARI
        with admin_tab1:
            st.subheader("Onay Bekleyen Kullanıcılar")
            bekleyenler_req = supabase.table("kullanicilar").select("*").eq("onayli_mi", False).execute()
            if bekleyenler_req.data:
                for usr in bekleyenler_req.data:
                    u_col1, u_col2 = st.columns([3,1])
                    u_col1.write(f"📧 **{usr['email']}** (Kayıt: {usr['olusturma_tarihi'][:10]})")
                    if u_col2.button("✅ Onayla", key=f"onay_{usr['id']}"):
                        supabase.table("kullanicilar").update({"onayli_mi": True}).eq("id", usr['id']).execute()
                        st.success("Kullanıcı onaylandı!")
                        st.rerun()
            else:
                st.info("Onay bekleyen yeni kayıt bulunmuyor.")
                
        # 2. ÜRÜN YÖNETİMİ (Kaldırma/Gizleme)
        with admin_tab2:
            st.subheader("Ürün Kataloğu Yönetimi")
            st.write("Aşağıdaki listeden satışı duran veya katalogdan kaldırmak istediğiniz ürünleri gizleyebilirsiniz.")
            
            tum_parcalar = supabase.table("parcalar").select("*").execute().data
            if tum_parcalar:
                for parca in tum_parcalar:
                    durum = "🟢 Aktif" if parca['aktif_mi'] else "🔴 Gizlendi"
                    p_col1, p_col2 = st.columns([4,1])
                    p_col1.write(f"{durum} | **Model:** {parca['model_adi']} (Fiyat: {parca['fiyat']} TL)")
                    
                    if parca['aktif_mi']:
                        if p_col2.button("🚫 Gizle (Kaldır)", key=f"gizle_{parca['id']}"):
                            supabase.table("parcalar").update({"aktif_mi": False}).eq("id", parca['id']).execute()
                            st.rerun()
                    else:
                        if p_col2.button("✅ Geri Al (Aktif)", key=f"aktif_{parca['id']}"):
                            supabase.table("parcalar").update({"aktif_mi": True}).eq("id", parca['id']).execute()
                            st.rerun()
