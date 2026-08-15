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
    sicil_baz = {s: random.randint(20000, 30000) for s in SICILLER}
    rows3 = []
    for _, row in sheet1.iterrows():
        sicil, pf = row["Sicil"], row["Portfoy"]
        if row["Portfoy Seviyesi"] == "GECİCİ":
            continue
        baz = sicil_baz[sicil]
        gun = random.randint(15, 22)
        ort_cal = int(baz * random.uniform(0.92, 1.08))
        om_ref_sure = random.randint(400, 900)
        om_disi_sure = random.randint(800, 2000)
        ref_ort = random.randint(30, 120)
        rows3.append({
            "Portfoy": pf,
            "Sicil": sicil,
            "Calistigi Is Gunu Sayisi": gun,
            "Gunluk Ortalama Calisma Suresi": ort_cal,
            "Gunluk Medyan Calisma Suresi": int(ort_cal * random.uniform(0.88, 0.97)),
            "Gunluk Ortalama OM`ye yönlendirilen referanslarda calışma suresi": om_ref_sure,
            "Gunluk Medyan OM`ye yönlendirilen referanslarda calışma suresi": int(om_ref_sure * random.uniform(0.87, 0.96)),
            "Gunluk Ortalama OM`ye yönlendirilmeyen referanslarda calışma suresi": om_disi_sure,
            "Gunluk Medyan OM`ye yönlendirilmeyen referanslarda calışma suresi": int(om_disi_sure * random.uniform(0.87, 0.96)),
            "Gunluk Ortalama Referans Adedi": ref_ort,
            "Gunluk Medyan Referans Adedi": int(ref_ort * random.uniform(0.88, 0.96)),
        })
    sheet3 = pd.DataFrame(rows3)

    # Sheet 4: Portfoy_Aktif_Sicil
    rows4 = []
    for pf in TUM_PORTFOYLER:
        n = sheet1[sheet1["Portfoy"] == pf]["Sicil"].nunique()
        # Günlük toplam çalışma süresi per sicil (sn/gün)
        ort_cal = random.randint(20000, 29000)
        # OM oranı: toplam sürenin %40–70'i OM işlerine harcanıyor (günlük toplam, sn/gün/sicil)
        om_oran = random.uniform(0.40, 0.70)
        om_ref_sure = int(ort_cal * om_oran)       # günlük OM çalışma süresi per sicil
        om_disi_sure = int(ort_cal * (1 - om_oran))  # günlük OM dışı çalışma süresi per sicil
        rows4.append({
            "Portfoy": pf,
            "Gunluk Ortalama Aktif Sicil": round(n * random.uniform(0.80, 1.0), 1),
            "Gunluk Medyan Aktif Sicil": max(1, n - random.randint(0, 2)),
            "Sicil bazlı günlük ortalama çalışma süresi": ort_cal,
            "Sicil bazlı günlük medyan çalışma süresi": int(ort_cal * random.uniform(0.88, 0.97)),
            "Sicil bazlı günlük ortalama OM`ye yonlendırılen referanslarda çalışma süresi": om_ref_sure,
            "Sicil bazlı günlük medyan OM`ye yonlendırılen referanslarda çalışma süresi": int(om_ref_sure * random.uniform(0.87, 0.96)),
            "Sicil bazlı günlük ortalama OM`ye yonlendırılmeyen referanslarda çalışma süresi": om_disi_sure,
            "Sicil bazlı günlük medyan OM`ye yonlendırılmeyen referanslarda çalışma süresi": int(om_disi_sure * random.uniform(0.87, 0.96)),
        })
    sheet4 = pd.DataFrame(rows4)

    # Sheet 5: Istisna
    istisna_rows = []
    for sicil in random.sample(SICILLER, 4):
        ana_pf = sheet1.loc[(sheet1["Sicil"] == sicil) & (sheet1["Portfoy Seviyesi"] == "ANA"), "Portfoy"].values[0]
        for pf in random.sample([p for p in PORTFOYLER_IC if p != ana_pf], random.randint(1, 2)):
            istisna_rows.append({"Sicil": sicil, "Portfoy": pf})
    sheet5 = pd.DataFrame(istisna_rows)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        sheet1.to_excel(writer, sheet_name="Mevcut_Atama", index=False)
        sheet2.to_excel(writer, sheet_name="Portfoy_Is_Yuku", index=False)
        sheet3.to_excel(writer, sheet_name="Sicil_Hiz", index=False)
        sheet4.to_excel(writer, sheet_name="Portfoy_Aktif_Sicil", index=False)
        sheet5.to_excel(writer, sheet_name="Istisna", index=False)


if __name__ == "__main__":
    create_sample()
    print("Örnek veri oluşturuldu: sample_data/ornek_veri.xlsx")
