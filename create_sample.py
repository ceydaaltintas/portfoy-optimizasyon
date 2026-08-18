import random
import os
import pandas as pd


def create_sample(path: str = "sample_data/ornek_veri.xlsx"):
    random.seed(42)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    PORTFOYLER_IC = [f"PF-{i:02d}" for i in range(1, 16)]
    PORTFOYLER_DIS = ["EKT-01", "EKT-02"]
    TUM_PORTFOYLER = PORTFOYLER_IC + PORTFOYLER_DIS
    SICILLER = [str(s) for s in range(10001, 10021)]
    GECICI_SAATLER = {"EKT-01": ("09:00", "12:00"), "EKT-02": ("13:00", "16:00")}

    # Sheet 1: Mevcut_Atama
    atama_rows = []
    for i, sicil in enumerate(SICILLER):
        ana_pf = PORTFOYLER_IC[i % len(PORTFOYLER_IC)]
        atama_rows.append({"Sicil": sicil, "Portfoy": ana_pf, "Portfoy Seviyesi": "ANA",
                           "Baslangic Zamani": None, "Bitis Zamani": None})

    for sicil in SICILLER:
        ana_pf = next(r["Portfoy"] for r in atama_rows if r["Sicil"] == sicil and r["Portfoy Seviyesi"] == "ANA")
        for pf in random.sample([p for p in PORTFOYLER_IC if p != ana_pf], random.randint(2, 4)):
            atama_rows.append({"Sicil": sicil, "Portfoy": pf, "Portfoy Seviyesi": "DESTEK",
                               "Baslangic Zamani": None, "Bitis Zamani": None})

    for pf, sicil_listesi in {"EKT-01": random.sample(SICILLER, 4), "EKT-02": random.sample(SICILLER, 3)}.items():
        bas, bit = GECICI_SAATLER[pf]
        for sicil in sicil_listesi:
            if not any(r["Sicil"] == sicil and r["Portfoy"] == pf for r in atama_rows):
                atama_rows.append({"Sicil": sicil, "Portfoy": pf, "Portfoy Seviyesi": "GECİCİ",
                                   "Baslangic Zamani": bas, "Bitis Zamani": bit})
    sheet1 = pd.DataFrame(atama_rows)

    # Sheet 2: Portfoy_Is_Yuku
    rows2 = []
    for pf in TUM_PORTFOYLER:
        ic = pf in PORTFOYLER_IC
        toplam_ref = random.randint(400, 800) if ic else random.randint(150, 350)
        om_oran = random.uniform(0.55, 0.80) if ic else random.uniform(0.30, 0.55)
        om_ref = int(toplam_ref * om_oran)
        om_disi_ref = toplam_ref - om_ref
        islem_per_ref = random.uniform(2.0, 4.0)
        toplam_islem = int(toplam_ref * islem_per_ref)
        aktif_gun = random.randint(18, 22)
        rows2.append({
            "Portfoy": pf,
            "Toplam Referans Adedi": toplam_ref,
            "Toplam Islem Adedi": toplam_islem,
            "OM`ye Yonlendirilen Referans Adedi": om_ref,
            "OM`ye Yonlendirilmeyen Referans Adedi": om_disi_ref,
            "Aktif Is Günü Sayisi": aktif_gun,
            "Günlük Ortalama Referans Adedi": round(toplam_ref / aktif_gun, 1),
            "Gunluk Medyan Referans Adedi": round(toplam_ref / aktif_gun * random.uniform(0.88, 0.95), 1),
            "Gunluk Ortalama Islem Adedi": round(toplam_islem / aktif_gun, 1),
            "Gunluk Medyan Islem Adedi": round(toplam_islem / aktif_gun * random.uniform(0.88, 0.95), 1),
            "Gunluk Ortalama OM`ye Yonlendirilen Referans Adedi": round(om_ref / aktif_gun, 1),
            "Gunluk Medyan OM`ye Yonlendirilen Referans Adedi": round(om_ref / aktif_gun * random.uniform(0.88, 0.95), 1),
            "Gunluk Ortalama OM`ye Yonlendirilmeyen Referans Adedi": round(om_disi_ref / aktif_gun, 1),
            "Gunluk Medyan OM`ye Yonlendirilmeyen Referans Adedi": round(om_disi_ref / aktif_gun * random.uniform(0.88, 0.95), 1),
            "Gunluk Ortalama OM`ye Yonlendirilmeyen Islem Adedi": round(toplam_islem / aktif_gun * (1 - om_oran), 1),
            "Gunluk Medyan OM`ye Yonlendirilmeyen Islem Adedi": round(toplam_islem / aktif_gun * (1 - om_oran) * random.uniform(0.88, 0.95), 1),
        })
    sheet2 = pd.DataFrame(rows2)

    # Sheet 3: Sicil_Hiz
    # Her sicil için toplam günlük kapasite belirlenir, portföylere bölüştürülür
    sicil_toplam = {s: random.randint(20000, 29000) for s in SICILLER}
    rows3 = []
    for sicil in SICILLER:
        toplam = sicil_toplam[sicil]
        sicil_rows = sheet1[sheet1["Sicil"] == sicil]
        ic_rows = sicil_rows[sicil_rows["Portfoy Seviyesi"].isin(["ANA", "DESTEK"])]
        pf_listesi = ic_rows["Portfoy"].tolist()
        seviyeler = {r["Portfoy"]: r["Portfoy Seviyesi"] for _, r in ic_rows.iterrows()}

        # ANA portföy toplam sürenin %55-75'ini alır, DESTEK'ler kalanı paylaşır
        ana_pf = next((p for p, s in seviyeler.items() if s == "ANA"), None)
        destek_pf = [p for p, s in seviyeler.items() if s == "DESTEK"]
        if ana_pf:
            ana_pay = int(toplam * random.uniform(0.55, 0.75))
            kalan = toplam - ana_pay
            pf_sureler = {ana_pf: ana_pay}
            if destek_pf:
                agirliklar = [random.uniform(0.5, 1.5) for _ in destek_pf]
                toplam_agirlik = sum(agirliklar)
                for pf, ag in zip(destek_pf, agirliklar):
                    pf_sureler[pf] = int(kalan * ag / toplam_agirlik)
        else:
            esit = toplam // max(len(pf_listesi), 1)
            pf_sureler = {pf: esit for pf in pf_listesi}

        for pf in pf_listesi:
            cal = pf_sureler.get(pf, 0)
            om_oran = random.uniform(0.50, 0.75)
            om_ref_sure = int(cal * om_oran)
            om_disi_sure = cal - om_ref_sure
            # Sicil ref sayısı: portföy toplam ref'i / o portföyde çalışan sicil sayısı
            pf_n_sicil = max(len(sheet1[
                (sheet1["Portfoy"] == pf) &
                (sheet1["Portfoy Seviyesi"].isin(["ANA", "DESTEK"]))
            ]), 1)
            pf_row = sheet2[sheet2["Portfoy"] == pf]
            if not pf_row.empty:
                pf_daily_refs = float(pf_row["Günlük Ortalama Referans Adedi"].values[0])
            else:
                pf_daily_refs = 30.0
            ref_ort = max(1, round(pf_daily_refs / pf_n_sicil * random.uniform(0.8, 1.2)))
            gun = random.randint(15, 22)
            rows3.append({
                "Portfoy": pf,
                "Sicil": sicil,
                "Calistigi Is Gunu Sayisi": gun,
                "Gunluk Ortalama Calisma Suresi": cal,
                "Gunluk Medyan Calisma Suresi": int(cal * random.uniform(0.88, 0.97)),
                "Gunluk Ortalama OM`ye yönlendirilen referanslarda calışma suresi": om_ref_sure,
                "Gunluk Medyan OM`ye yönlendirilen referanslarda calışma suresi": int(om_ref_sure * random.uniform(0.87, 0.96)),
                "Gunluk Ortalama OM`ye yönlendirilmeyen referanslarda calışma suresi": om_disi_sure,
                "Gunluk Medyan OM`ye yönlendirilmeyen referanslarda calışma suresi": int(om_disi_sure * random.uniform(0.87, 0.96)),
                "Gunluk Ortalama Referans Adedi": ref_ort,
                "Gunluk Medyan Referans Adedi": int(ref_ort * random.uniform(0.88, 0.96)),
            })
    sheet3 = pd.DataFrame(rows3)

    # Sheet 4: Portfoy_Aktif_Sicil
    # portfoy_sicil_sure değerlerini Sicil_Hiz'den türet (tutarlılık için)
    rows4 = []
    for pf in TUM_PORTFOYLER:
        pf_hiz = sheet3[sheet3["Portfoy"] == pf]
        n = sheet1[sheet1["Portfoy"] == pf]["Sicil"].nunique()
        if not pf_hiz.empty:
            ort_cal = int(pf_hiz["Gunluk Ortalama Calisma Suresi"].mean())
            med_cal = int(pf_hiz["Gunluk Medyan Calisma Suresi"].mean())
            om_sure = int(pf_hiz["Gunluk Ortalama OM`ye yönlendirilen referanslarda calışma suresi"].mean())
            om_sure_med = int(pf_hiz["Gunluk Medyan OM`ye yönlendirilen referanslarda calışma suresi"].mean())
            disi_sure = int(pf_hiz["Gunluk Ortalama OM`ye yönlendirilmeyen referanslarda calışma suresi"].mean())
            disi_sure_med = int(pf_hiz["Gunluk Medyan OM`ye yönlendirilmeyen referanslarda calışma suresi"].mean())
        else:
            ort_cal = random.randint(3000, 8000)
            med_cal = int(ort_cal * 0.92)
            om_sure = int(ort_cal * 0.6)
            om_sure_med = int(om_sure * 0.92)
            disi_sure = ort_cal - om_sure
            disi_sure_med = int(disi_sure * 0.92)
        rows4.append({
            "Portfoy": pf,
            "Gunluk Ortalama Aktif Sicil": round(n * random.uniform(0.80, 1.0), 1),
            "Gunluk Medyan Aktif Sicil": max(1, n - random.randint(0, 2)),
            "Sicil bazlı günlük ortalama çalışma süresi": ort_cal,
            "Sicil bazlı günlük medyan çalışma süresi": med_cal,
            "Sicil bazlı günlük ortalama OM`ye yonlendırılen referanslarda çalışma süresi": om_sure,
            "Sicil bazlı günlük medyan OM`ye yonlendırılen referanslarda çalışma süresi": om_sure_med,
            "Sicil bazlı günlük ortalama OM`ye yonlendırılmeyen referanslarda çalışma süresi": disi_sure,
            "Sicil bazlı günlük medyan OM`ye yonlendırılmeyen referanslarda çalışma süresi": disi_sure_med,
        })
    sheet4 = pd.DataFrame(rows4)

    # Sheet 5: Istisna
    istisna_rows = []
    for sicil in random.sample(SICILLER, 4):
        ana_pf = sheet1.loc[(sheet1["Sicil"] == sicil) & (sheet1["Portfoy Seviyesi"] == "ANA"), "Portfoy"].values[0]
        for pf in random.sample([p for p in PORTFOYLER_IC if p != ana_pf], random.randint(1, 2)):
            istisna_rows.append({"Sicil": sicil, "Portfoy": pf})
    sheet5 = pd.DataFrame(istisna_rows)

    # Sheet 6: Havuzda_Bekleme (opsiyonel)
    # Son 5 iş günü, saatlik kırılımda portföy bazında bekleme verisi
    import datetime
    rows6 = []
    bugun = datetime.date.today()
    is_gunleri = []
    d = bugun
    while len(is_gunleri) < 22:
        if d.weekday() < 5:
            is_gunleri.append(d)
        d -= datetime.timedelta(days=1)

    SAATLER = [f"{h:02d}:00" for h in range(9, 18)]
    # Bazı portföyler kronik yoğun, bazıları normal — gerçekçi dağılım için
    yogun_pf = random.sample(PORTFOYLER_IC, 4)

    for tarih in is_gunleri:
        for pf in PORTFOYLER_IC:
            pf_row = sheet2[sheet2["Portfoy"] == pf]
            gunluk_ref = float(pf_row["Günlük Ortalama Referans Adedi"].values[0]) if not pf_row.empty else 30.0
            n_sicil = max(len(sheet1[
                (sheet1["Portfoy"] == pf) &
                (sheet1["Portfoy Seviyesi"].isin(["ANA", "DESTEK"]))
            ]), 1)
            yogun = pf in yogun_pf
            for saat in SAATLER:
                # Sabah ve öğle sonrası daha yoğun
                saat_no = int(saat[:2])
                saat_carpan = 1.4 if saat_no in [9, 10, 14] else 0.7 if saat_no >= 16 else 1.0
                gelen = max(1, round(gunluk_ref / len(SAATLER) * saat_carpan * random.uniform(0.7, 1.3)))
                # Yoğun portföylerde daha az ref aynı saatte işleme alınıyor
                baslama_oran = random.uniform(0.45, 0.70) if yogun else random.uniform(0.70, 0.95)
                ayni_saatte = max(0, round(gelen * baslama_oran))
                # İlk temas bekleme süresi — yoğun portföylerde daha uzun
                ort_bekleme = random.randint(600, 1800) if yogun else random.randint(120, 600)
                # Toplam çalışılan ref (iade dönüşleri dahil — gelenin %10-30 fazlası)
                toplam_calisilan = round(gelen * random.uniform(1.1, 1.3))
                rows6.append({
                    "Portfoy": pf,
                    "Tarih": tarih.strftime("%Y-%m-%d"),
                    "Saat": saat,
                    "Gelen_Ref": gelen,
                    "Ayni_Saatte_Baslanan": ayni_saatte,
                    "Ort_Ilk_Temas_Sn": ort_bekleme,
                    "Toplam_Calisilan_Ref": toplam_calisilan,
                    "Aktif_Sicil_Adedi": max(1, round(n_sicil * random.uniform(0.6, 1.0))),
                })
    sheet6 = pd.DataFrame(rows6)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        sheet1.to_excel(writer, sheet_name="Mevcut_Atama", index=False)
        sheet2.to_excel(writer, sheet_name="Portfoy_Is_Yuku", index=False)
        sheet3.to_excel(writer, sheet_name="Sicil_Hiz", index=False)
        sheet4.to_excel(writer, sheet_name="Portfoy_Aktif_Sicil", index=False)
        sheet5.to_excel(writer, sheet_name="Istisna", index=False)
        sheet6.to_excel(writer, sheet_name="Havuzda_Bekleme", index=False)


if __name__ == "__main__":
    create_sample()
    print("Örnek veri oluşturuldu: sample_data/ornek_veri.xlsx")
