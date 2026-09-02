"""
Simülasyon analizi için önce/sonra örnek veri üretir.

Önce: dağınık DESTEK atamaları, düşük karşılama, bazı portföyler açıkta
Sonra: optimizer sonrası atamalar, daha iyi karşılama,
       bazı siciller ek yetki ekleyip atanmadıkları portföylerde çalışmış
"""

import random
import os
import datetime
import pandas as pd

random.seed(99)

PORTFOYLER = [f"PF-{i:02d}" for i in range(1, 11)]
SICILLER = [str(s) for s in range(10001, 10013)]  # 12 sicil
GUN_SN = 27000  # ~7.5 saat net

SAATLER = [f"{h:02d}:00" for h in range(8, 18)]


def _is_gunu(gun_geri: int) -> datetime.date:
    d = datetime.date.today()
    sayac = 0
    while sayac < gun_geri:
        d -= datetime.timedelta(days=1)
        if d.weekday() < 5:
            sayac += 1
    return d


def _atama_once() -> pd.DataFrame:
    """Optimizasyon öncesi: her sicile 1 ANA + 1-2 rastgele DESTEK."""
    rows = []
    ana_map = {}
    for i, sicil in enumerate(SICILLER):
        ana_pf = PORTFOYLER[i % len(PORTFOYLER)]
        ana_map[sicil] = ana_pf
        rows.append({"Sicil": sicil, "Portfoy": ana_pf, "Portfoy Seviyesi": "ANA",
                     "Baslangic Zamani": None, "Bitis Zamani": None})

    for sicil in SICILLER:
        ana = ana_map[sicil]
        diger = [p for p in PORTFOYLER if p != ana]
        for pf in random.sample(diger, random.randint(1, 2)):
            rows.append({"Sicil": sicil, "Portfoy": pf, "Portfoy Seviyesi": "DESTEK",
                         "Baslangic Zamani": None, "Bitis Zamani": None})
    return pd.DataFrame(rows)


def _atama_sonra() -> pd.DataFrame:
    """Optimizasyon sonrası: daha dengeli DESTEK dağılımı, bazı portföyler daha fazla destek almış."""
    rows = []
    ana_map = {}
    for i, sicil in enumerate(SICILLER):
        ana_pf = PORTFOYLER[i % len(PORTFOYLER)]
        ana_map[sicil] = ana_pf
        rows.append({"Sicil": sicil, "Portfoy": ana_pf, "Portfoy Seviyesi": "ANA",
                     "Baslangic Zamani": None, "Bitis Zamani": None})

    # Optimizer mantığı: yoğun portföylere (PF-03, PF-07, PF-09) daha fazla destek
    yogun = {"PF-03", "PF-07", "PF-09"}
    for sicil in SICILLER:
        ana = ana_map[sicil]
        diger = [p for p in PORTFOYLER if p != ana]
        oncelikli = [p for p in diger if p in yogun]
        normal = [p for p in diger if p not in yogun]
        secilen = oncelikli[:2] + random.sample(normal, max(0, 3 - len(oncelikli[:2])))
        for pf in secilen[:3]:
            rows.append({"Sicil": sicil, "Portfoy": pf, "Portfoy Seviyesi": "DESTEK",
                         "Baslangic Zamani": None, "Bitis Zamani": None})
    return pd.DataFrame(rows)


def _sicil_hiz_gun(atama_df: pd.DataFrame, kalip: str = "once") -> pd.DataFrame:
    """
    Gerçek günlük çalışma süresi ve ref adedi.
    Sonra gününde bazı siciller atanmadıkları portföylerde de çalışıyor (ek yetki).
    """
    rows = []
    ana_destek = atama_df[atama_df["Portfoy Seviyesi"].isin(["ANA", "DESTEK"])]

    for _, row in ana_destek.iterrows():
        sicil = row["Sicil"]
        pf = row["Portfoy"]
        seviye = row["Portfoy Seviyesi"]

        # ANA portföyde daha uzun çalışır
        if seviye == "ANA":
            sure = random.randint(9000, 15000)
        else:
            sure = random.randint(2000, 7000)

        # Önce gününde bazı siciller düşük performans göstersin
        if kalip == "once" and random.random() < 0.25:
            sure = int(sure * random.uniform(0.4, 0.7))

        ref = max(1, round(sure / random.randint(300, 600)))
        rows.append({
            "Portfoy": pf,
            "Sicil": sicil,
            "Calisma_Suresi_Sn": sure,
            "Referans_Adedi": ref,
        })

    # Sonra gününde: 3 sicil ek yetki ekleyip atanmadıkları portföylerde çalışmış
    if kalip == "sonra":
        ek_yetki = [
            ("10003", "PF-05"),   # optimizer PF-05'e atamamış ama sicil girmiş
            ("10007", "PF-02"),
            ("10010", "PF-08"),
        ]
        atanmis = set(zip(ana_destek["Sicil"], ana_destek["Portfoy"]))
        for sicil, pf in ek_yetki:
            if (sicil, pf) not in atanmis:
                sure = random.randint(1800, 4500)
                ref = max(1, round(sure / random.randint(300, 500)))
                rows.append({
                    "Portfoy": pf,
                    "Sicil": sicil,
                    "Calisma_Suresi_Sn": sure,
                    "Referans_Adedi": ref,
                })

    return pd.DataFrame(rows)


def _portfoy_is_yuku_gun(kalip: str = "once") -> pd.DataFrame:
    rows = []
    for pf in PORTFOYLER:
        # Yoğun portföyler daha fazla ref alır
        yogun = pf in {"PF-03", "PF-07", "PF-09"}
        baz = random.randint(55, 90) if yogun else random.randint(25, 55)
        # Sonra günü talep biraz farklı
        carpan = random.uniform(0.9, 1.15) if kalip == "sonra" else 1.0
        rows.append({"Portfoy": pf, "Gelen_Ref": round(baz * carpan)})
    return pd.DataFrame(rows)


def _havuzda_bekleme(piy_df: pd.DataFrame, kalip: str = "once") -> pd.DataFrame:
    tarih = _is_gunu(2 if kalip == "once" else 1)
    gelen_map = dict(zip(piy_df["Portfoy"], piy_df["Gelen_Ref"]))

    rows = []
    yogun_pf = {"PF-03", "PF-07", "PF-09"}

    for pf in PORTFOYLER:
        gunluk_ref = gelen_map.get(pf, 30)
        yogun = pf in yogun_pf
        for saat in SAATLER:
            saat_no = int(saat[:2])
            saat_carpan = 1.4 if saat_no in [9, 10, 14] else 0.7 if saat_no >= 16 else 1.0
            gelen = max(1, round(gunluk_ref / len(SAATLER) * saat_carpan * random.uniform(0.7, 1.3)))

            # Sonra gününde yoğun portföyler daha iyi karşılanıyor (optimizer etkisi)
            if kalip == "sonra" and not yogun:
                baslama_oran = random.uniform(0.75, 0.95)
                ilk_temas = random.randint(80, 400)
            elif kalip == "sonra" and yogun:
                baslama_oran = random.uniform(0.55, 0.75)
                ilk_temas = random.randint(300, 900)
            elif yogun:
                baslama_oran = random.uniform(0.35, 0.55)
                ilk_temas = random.randint(600, 1800)
            else:
                baslama_oran = random.uniform(0.60, 0.80)
                ilk_temas = random.randint(200, 700)

            ayni_saatte = max(0, round(gelen * baslama_oran))
            toplam_calisilan = round(gelen * random.uniform(1.05, 1.2))

            rows.append({
                "Portfoy": pf,
                "Tarih": tarih.strftime("%d.%m.%Y"),
                "Saat": saat,
                "Gelen_Ref": gelen,
                "Ayni_Saatte_Baslanan": ayni_saatte,
                "Ort_Ilk_Temas_Sn": ilk_temas,
                "Toplam_Calisilan_Ref": toplam_calisilan,
                "Aktif_Sicil_Adedi": max(1, round(len(SICILLER) * random.uniform(0.6, 0.9))),
            })
    return pd.DataFrame(rows)


def create_sim_samples(out_dir: str = "sample_data"):
    os.makedirs(out_dir, exist_ok=True)

    for kalip in ("once", "sonra"):
        atama = _atama_once() if kalip == "once" else _atama_sonra()
        hiz = _sicil_hiz_gun(atama, kalip)
        piy = _portfoy_is_yuku_gun(kalip)
        hb = _havuzda_bekleme(piy, kalip)

        path = os.path.join(out_dir, f"simulasyon_{kalip}.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            atama.to_excel(writer, sheet_name="Atama", index=False)
            hiz.to_excel(writer, sheet_name="Sicil_Hiz_Gun", index=False)
            piy.to_excel(writer, sheet_name="Portfoy_Is_Yuku_Gun", index=False)
            hb.to_excel(writer, sheet_name="Havuzda_Bekleme", index=False)

        print(f"Oluşturuldu: {path}")
        print(f"  Atama: {len(atama)} satır")
        print(f"  Sicil_Hiz_Gun: {len(hiz)} satır")
        print(f"  Portfoy_Is_Yuku_Gun: {len(piy)} satır")
        print(f"  Havuzda_Bekleme: {len(hb)} satır")


if __name__ == "__main__":
    create_sim_samples()
