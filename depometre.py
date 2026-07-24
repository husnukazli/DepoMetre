import streamlit as st
from supabase import create_client, Client
import pandas as pd
import os
from fpdf import FPDF

# ==========================================
# FONKSİYONLAR (Sola tam dayalı - Boşluksuz)
# ==========================================
def create_pdf(sepet_verisi, toplam):
    pdf = FPDF()
    pdf.add_page()
    
    if os.path.exists("arial.ttf"):
        pdf.add_font("ArialTR", "", "arial.ttf", uni=True)
        pdf.set_font("ArialTR", "", 16)
    else:
        pdf.set_font("Arial", "B", 16)
        
    pdf.cell(0, 10, txt="Soguk Hava Deposu Konfigurasyon Ozeti", ln=True, align='C')
    pdf.ln(10)
    
    if os.path.exists("arial.ttf"):
        pdf.set_font("ArialTR", "", 12)
    else:
        pdf.set_font("Arial", "", 12)
        
    pdf.cell(50, 10, txt="Kategori", border=1)
    pdf.cell(100, 10, txt="Marka / Model", border=1)
    pdf.cell(40, 10, txt="Fiyat (TL)", border=1, ln=True)
    
    for index, row in sepet_verisi.iterrows():
        pdf.cell(50, 10, txt=str(row['Kategori']), border=1)
        pdf.cell(100, 10, txt=str(row['Marka/Model']), border=1)
        pdf.cell(40, 10, txt=f"{row['Fiyat']:,.2f}", border=1, ln=True)
        
    pdf.ln(10)
    if os.path.exists("arial.ttf"):
        pdf.set_font("ArialTR", "", 14)
    else:
        pdf.set_font("Arial", "B", 14)
        
    pdf.cell(0, 10, txt=f"Genel Toplam: {toplam:,.2f} TL", ln=True, align='R')
    
    return bytes(pdf.output())

# --- SUPABASE BAĞLANTISI ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# (Kodun geri kalanı buradan itibaren aynı şekilde devam edecek...)
