# PDF OLUŞTURMA FONKSİYONU
    def create_pdf(sepet_verisi, toplam):
        pdf = FPDF()
        pdf.add_page()
        
        # Font Yükleme (GitHub'a eklenen arial.ttf üzerinden)
        if os.path.exists("arial.ttf"):
            pdf.add_font("ArialTR", "", "arial.ttf", uni=True)
            pdf.set_font("ArialTR", "", 16)
        else:
            pdf.set_font("Arial", "B", 16) # Fallback
            
        pdf.cell(0, 10, txt="Soguk Hava Deposu Konfigurasyon Ozeti", ln=True, align='C')
        pdf.ln(10)
        
        if os.path.exists("arial.ttf"):
            pdf.set_font("ArialTR", "", 12)
        else:
            pdf.set_font("Arial", "", 12)
            
        # Başlıklar
        pdf.cell(50, 10, txt="Kategori", border=1)
        pdf.cell(100, 10, txt="Marka / Model", border=1)
        pdf.cell(40, 10, txt="Fiyat (TL)", border=1, ln=True)
        
        # Ürünler
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
        
        # DÜZELTİLEN SATIR: fpdf2 doğrudan bytearray döndürdüğü için encode kullanmıyoruz.
        return bytes(pdf.output())
